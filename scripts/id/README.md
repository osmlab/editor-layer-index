# iD output profile 1

`make imagery.id.json` produces the compact JSON array used by iD's
`dist/data/imagery.min.json`. `make test-id` checks release-specific behavior,
the CLI output and known-source canaries. Node 22 or later
is required; there are no npm dependencies.

The converter and manual overrides come from the tagged release
[iD v2.41.2](https://github.com/openstreetmap/iD/tree/v2.41.2).
`update_imagery.js` is an unmodified copy of that release's script. `convert.mjs`
loads it with a thin adapter that supplies input and captures the compact output;
there is only one copy of the conversion policy. The adapter replaces imports and
filesystem operations and substitutes `JSON.stringify` for the unused pretty
writer. The ISC license in this directory covers the upstream files.

The manual overrides are part of iD's policy: they replace ELI's Mapbox entries
and contain iD's encrypted templates. They are included to reproduce the complete
iD output for the same ELI input. This is a snapshot of that policy, not a promise
to track every future iD change. Updating it requires reviewing the upstream
converter and manual overrides together, updating the release tag references and
behavioral expectations, and passing `make test-id`.

This release excludes imagery whose end date is at least twenty years old,
preserves HTML attribution, and excludes WMS sources supporting only `CRS:84`.
The adapter uses UTC for the age cutoff, matching CI. Set `SOURCE_DATE_EPOCH` to
Unix seconds to reproduce an earlier build date; otherwise conversion uses the
current time. Changing that environment variable requires forcing a rebuild with
`make -B imagery.id.json`.

General geometry validation belongs to `make check`, which runs before conversion
in both PR and deployment CI. It checks raw exterior/interior rings for minimum
length, closure, finite numbers and geographic bounds before Shapely validates
topology. iD tests retain checks for the conversion from GeoJSON rings to iD's
exterior-only polygon representation.

`--format-version 1` explicitly selects this profile; unknown versions fail.
Future incompatible profiles should have separate converters and tests and
remain buildable alongside profile 1. The current array has no metadata wrapper
because that would break consumers expecting an array.
