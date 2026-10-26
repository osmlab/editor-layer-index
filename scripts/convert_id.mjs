// iD profile v1. Keep the JSON array compatible with dist/data/imagery.min.json.
import fs from 'node:fs';
import { parseArgs } from 'node:util';
import { convertImagery } from './id/convert.mjs';

const { values, positionals } = parseArgs({
  options: { 'format-version': { type: 'string', default: '1' } },
  allowPositionals: true
});
if (values['format-version'] !== '1' || positionals.length !== 1) {
  throw new Error('Usage: node scripts/convert_id.mjs [--format-version 1] imagery.geojson');
}
const sources = JSON.parse(fs.readFileSync(positionals[0], 'utf8'));
const manual = JSON.parse(fs.readFileSync(new URL('./id/manual_imagery.json', import.meta.url), 'utf8'));
const now = process.env.SOURCE_DATE_EPOCH === undefined
  ? new Date() : new Date(Number(process.env.SOURCE_DATE_EPOCH) * 1000);
process.stdout.write(JSON.stringify(convertImagery(sources, manual, now)));
