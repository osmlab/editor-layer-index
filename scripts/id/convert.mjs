import fs from 'node:fs';
import vm from 'node:vm';

// Execute iD v2.41.2's vendored converter with ELI's I/O. Conversion policy lives
// only in update_imagery.js. The pretty writer is unused; we capture compact JSON.
const upstream = fs.readFileSync(new URL('./update_imagery.js', import.meta.url), 'utf8');
const code = upstream.replace(/^import .*;\n/gm, '')
  .replace('const require = createRequire(import.meta.url);', '');
const script = new vm.Script(code, { filename: 'iD-v2.41.2/update_imagery.js' });

export function convertImagery(collection, manualImagery = [], now = new Date()) {
  if (!Number.isFinite(now.getTime())) throw new Error('Invalid conversion date');
  // The release filters imagery older than 20 years. Freeze its clock so callers
  // can reproduce a build. Use UTC, matching the GitHub Actions build environment.
  class BuildDate extends Date {
    constructor(...args) { super(...(args.length ? args : [now.getTime()])); }
    getFullYear() { return this.getUTCFullYear(); }
    setFullYear(...args) { return this.setUTCFullYear(...args); }
    static now() { return now.getTime(); }
  }
  let output;
  script.runInNewContext({
    Date: BuildDate,
    require: { resolve: () => 'sources' },
    fs: {
      existsSync: () => true,
      readFileSync: path => JSON.stringify(path === 'sources' ? collection : manualImagery),
      writeFileSync: (path, data) => { if (path === 'dist/data/imagery.min.json') output = data; }
    },
    prettyStringify: JSON.stringify
  });
  if (output === undefined) throw new Error('iD converter did not write compact imagery output');
  return JSON.parse(output);
}
