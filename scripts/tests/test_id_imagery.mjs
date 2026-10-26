import assert from 'node:assert/strict';
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import { test } from 'node:test';
import { convertImagery } from '../id/convert.mjs';

const readJSON = path => JSON.parse(fs.readFileSync(path, 'utf8'));
const manual = readJSON(new URL('../id/manual_imagery.json', import.meta.url));
const feature = (id, properties = {}, geometry = null) => ({
  type: 'Feature', geometry,
  properties: { id, name: id, type: 'tms', url: 'https://example.com/{zoom}/{x}/{y}.jpg', ...properties }
});
const collection = features => ({ type: 'FeatureCollection', features });

test('filtering, WMS projection priority and duplicate names match iD', () => {
  const input = collection([
    feature('osmfr-breton'), feature('US-TIGER-Roads-2019'), feature('EOXAT2024'),
    feature('unsupported', { type: 'wmts' }),
    feature('crs84', { type: 'wms', available_projections: ['CRS:84'] }),
    feature('bad-projection', { type: 'wms', available_projections: ['EPSG:2154'] }),
    feature('wms', { type: 'wms', available_projections: ['EPSG:4326', 'EPSG:3857'] }),
    feature('tms', { name: 'duplicate' }),
    feature('wms-duplicate', { name: 'duplicate', type: 'wms', available_projections: ['EPSG:3857'] }),
    { type: 'Feature', properties: null, geometry: null }
  ]);
  const result = convertImagery(input);
  assert.deepEqual(result, ['tms', 'wms'].map(id => ({
    id, name: id === 'tms' ? 'duplicate' : id, type: id,
    template: 'https://example.com/{zoom}/{x}/{y}.jpg',
    ...(id === 'wms' ? { projection: 'EPSG:3857' } : {})
  })));
  assert.equal(result[1].projection, 'EPSG:3857');
});

test('dates, exterior rings, attribution, zoom defaults and tile exceptions match iD', () => {
  const ring = [[0, 0], [1, 0], [1, 1], [0, 0]];
  const input = collection([
    feature('Mapbox'), feature('mtbmap-no'), feature('mapbox_locator_overlay'),
    feature('polygon', {
      min_zoom: 0, max_zoom: 19, start_date: '2020', end_date: 'invalid',
      attribution: { url: 'https://example.com/terms', text: 'Credits', html: '<b>Credits</b>' },
      best: true, overlay: false, description: 'Photo'
    }, { type: 'Polygon', coordinates: [ring, ring] }),
    feature('multi', { start_date: '2020-02', end_date: '2021-03-04' },
      { type: 'MultiPolygon', coordinates: [[ring], [ring]] })
  ]);
  const result = convertImagery(input);
  const polygon = result.find(im => im.id === 'polygon');
  assert.deepEqual(polygon.polygon, [ring]);
  assert.equal(polygon.startDate, '2020-01-01T00:00:00.000Z');
  assert.equal(polygon.endDate, undefined);
  assert.equal(polygon.terms_html, '<b>Credits</b>');
  assert.equal(polygon.terms_text, 'Credits');
  assert.equal(polygon.terms_url, 'https://example.com/terms');
  assert.deepEqual(polygon.zoomExtent, [0, 19]);
  assert.equal(polygon.best, true);
  assert.equal(polygon.overlay, undefined);
  assert.deepEqual(result.find(im => im.id === 'multi').polygon, [ring, ring]);
  assert.equal(result.find(im => im.id === 'multi').endDate, '2021-03-04T00:00:00.000Z');
  const mapbox = result.find(im => im.id === 'Mapbox');
  assert.equal(mapbox.tileSize, 512);
  assert.equal(mapbox.template, 'https://example.com/{zoom}/{x}/{y}@2x.jpg');
  assert.equal(result.find(im => im.id === 'mtbmap-no').tileSize, 512);
  const locator = result.find(im => im.id === 'mapbox_locator_overlay');
  assert.equal(locator.overzoom, false);
  assert.equal(locator.template, 'https://example.com/{zoom}/{x}/{y}{@2x}.jpg');
});

test('manual overrides replace matching ELI entries without mutating input', () => {
  const input = collection([feature('Mapbox'), feature('other')]);
  const before = structuredClone(input);
  const result = convertImagery(input, manual);
  assert.equal(result.filter(im => im.id === 'Mapbox').length, 1);
  assert.equal(result.find(im => im.id === 'Mapbox').encrypted, true);
  assert.equal(result.find(im => im.id === 'Mapbox').template, manual.find(im => im.id === 'Mapbox').url);
  assert.deepEqual(input, before);
});

test('CLI rejects unknown output versions', () => {
  assert.throws(() => execFileSync(process.execPath,
    ['scripts/convert_id.mjs', '--format-version', '2', 'imagery.geojson'], { stdio: 'pipe' }));
});

test('v2.41.2 filters old imagery at the twenty-year boundary', () => {
  const input = collection([
    feature('old', { end_date: '2000' }),
    feature('boundary', { end_date: '2006-10-26' }),
    feature('recent', { end_date: '2006-10-27' }),
    feature('unknown')
  ]);
  const result = convertImagery(input, [], new Date('2026-10-26T00:00:00Z'));
  assert.deepEqual(result.map(im => im.id), ['recent', 'unknown']);
});

test('CLI honors a reproducible build date across timezones', () => {
  const epoch = String(Date.parse('2026-10-26T00:00:00Z') / 1000);
  const run = TZ => execFileSync(process.execPath, ['scripts/convert_id.mjs', 'imagery.geojson'], {
    env: { ...process.env, SOURCE_DATE_EPOCH: epoch, TZ }, encoding: 'utf8', maxBuffer: 20 * 1024 * 1024
  });
  const actual = run('UTC');
  assert.equal(run('America/New_York'), actual);
  assert.deepEqual(JSON.parse(actual),
    convertImagery(readJSON('imagery.geojson'), manual, new Date(Number(epoch) * 1000)));
});

test('built catalog uses the tagged converter and passes client canaries', () => {
  const input = readJSON('imagery.geojson');
  const actual = readJSON('imagery.id.json');
  const now = process.env.SOURCE_DATE_EPOCH === undefined
    ? new Date() : new Date(Number(process.env.SOURCE_DATE_EPOCH) * 1000);
  assert.deepEqual(actual, convertImagery(input, manual, now));
  assert.ok(actual.length > 0, 'empty index');
  assert.equal(new Set(actual.map(im => im.id)).size, actual.length, 'duplicate IDs');
  for (const im of actual) {
    for (const key of ['id', 'name', 'template']) assert.equal(typeof im[key], 'string', `${im.id}: ${key}`);
    assert.ok(['tms', 'wms', 'bing'].includes(im.type), im.id);
    if (im.type === 'wms') assert.ok(im.projection, im.id);
    if (im.zoomExtent) {
      assert.equal(im.zoomExtent.length, 2);
      assert.ok(im.zoomExtent.every(Number.isFinite), im.id);
      assert.ok(im.zoomExtent[0] <= im.zoomExtent[1], im.id);
    }
  }
  for (const id of ['EsriWorldImagery', 'Mapbox', 'mapbox_locator_overlay']) {
    assert.ok(actual.some(im => im.id === id), `missing canary: ${id}`);
  }
});
