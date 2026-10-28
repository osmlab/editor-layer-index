# Python lint policy

Python 3.14 is the minimum supported version. Ruff formats Python at 100 columns;
Flake8 and Pylint use the same width. Run all tools against both `src/eli` and `tests`.

## Project-wide choices

- Pylint `missing-function-docstring` (C0116), `import-outside-toplevel` (C0415), and
  `line-too-long` (C0301) are disabled at the user's request. Flake8 still enforces 100 columns.
- `JSON` is a permitted acronym for the public type alias.
- Pylint may inspect `pyproj` C-extension members. `pyproj.database.get_codes` is a
  documented public API; allowing its inspection avoids hiding missing-member checks.

## Scoped protocol design exceptions

These existing protocol adapters mirror external formats and must preserve accumulated
diagnostics, optional-field handling, and export ordering. Splitting them only to satisfy
line, branch, or local-variable counts would obscure those contracts. Each exception is
attached to the specific declaration or nested protocol block; default limits remain
enabled everywhere else. Short message IDs keep inline directives within the line limit.
When extending these routines, prefer extracting genuinely independent policy before
expanding an exception.

- `src/eli/check.py:run`: Independent schema, URL, and geometry checks accumulate diagnostics in one
  source pass. Checks: `too-many-branches`, `too-many-locals`, `too-many-statements`.

- `src/eli/exporters.py:xml_bytes`: Preserve the exact order of optional JOSM fields in the legacy
  XML output. Checks: `too-many-statements`.

- `src/eli/exporters.py:xml_bytes.add_source`: Each optional JOSM field is mapped explicitly to
  preserve legacy XML ordering. Checks: `too-many-branches`, `too-many-locals`, `too-many-
  statements`.

- `src/eli/import_josm.py:run`: Mirror optional JOSM fields while preserving source-property
  insertion order. Checks: `too-many-branches`, `too-many-locals`, `too-many-statements`.

- `src/eli/libeli/tmshelper.py:TMSURL`: This URL value object exposes only the operation required by
  its callers. Checks: `too-few-public-methods`.

- `src/eli/libeli/tmshelper.py:TileMapResource`: This parsed document exposes its data and the one
  required zoom-range operation. Checks: `too-few-public-methods`.

- `src/eli/libeli/tmshelper.py:TileMapResource._parse_xml`: Parse format, bounds, projections, and
  tile sets from the same TMS document. Checks: `too-many-locals`.

- `src/eli/libeli/wmshelper.py:Dimension`: These eight fields are the WMS dimension record, not
  independent responsibilities. Checks: `too-many-instance-attributes`.

- `src/eli/libeli/wmshelper.py:WMSCapabilities`: This parsed capabilities record exposes its fields
  instead of artificial public methods. Checks: `too-few-public-methods`.

- `src/eli/libeli/wmshelper.py:WMSCapabilities._parse_xml`: Keep explicit alternatives for the
  metadata elements used by supported WMS versions. Checks: `too-many-locals`, `too-many-
  statements`.

- `src/eli/libeli/wmshelper.py:WMSURL.get_map_url`: Explicit keyword-only arguments correspond to
  mandatory and optional WMS GetMap fields. Checks: `too-many-arguments`, `too-many-locals`.

- `src/eli/libeli/wmtshelper.py:Layer`: These fields describe one WMTS layer and its supported
  matrix sets and formats. Checks: `too-many-instance-attributes`.

- `src/eli/libeli/wmtshelper.py:is_googlemaps_compatible`: Early returns reject independent
  incompatibilities in the Google Maps tile scheme. Checks: `too-many-return-statements`.

- `src/eli/minzoom.py:MinZoom.process_source`: Tile samples, plot callbacks, and source edits share
  one interactive figure lifecycle. Checks: `too-many-branches`, `too-many-locals`, `too-many-
  statements`.

- `src/eli/strict.py:StrictChecker.check_tms`: TMS metadata and tile probes accumulate independent
  diagnostics for one source. Checks: `too-many-branches`, `too-many-locals`, `too-many-nested-
  blocks`, `too-many-statements`.

- `src/eli/strict.py:StrictChecker.check_wms`: Protocol alternatives must accumulate independent WMS
  diagnostics instead of returning early. Checks: `too-many-branches`, `too-many-locals`, `too-many-
  nested-blocks`, `too-many-statements`.

- `src/eli/strict.py:StrictChecker.run`: Collect metadata and geometry diagnostics before reporting
  and continuing the source batch. Checks: `too-many-branches`, `too-many-locals`, `too-many-
  statements`.

- `src/eli/sync_wms.py:WMSSync`: One sync run owns its separate caches, locks, projection sets, and
  reporting counters. Checks: `too-many-instance-attributes`.

- `src/eli/sync_wms.py:WMSSync.get_image`: A tile probe needs explicit URL, projection, location,
  zoom, session, and diagnostic inputs. Checks: `too-many-arguments`, `too-many-branches`, `too-
  many-locals`, `too-many-statements`.

- `src/eli/sync_wms.py:WMSSync.process_source`: Conservative projection updates share the original
  source and image-comparison baseline. Checks: `too-many-branches`, `too-many-locals`, `too-many-
  return-statements`, `too-many-statements`.

- `src/eli/sync_wms.py:WMSSync.update_wms`: Resolve matching layer styles, WMS version, and
  projection intersections together. Checks: `too-many-branches`, `too-many-locals`, `too-many-
  statements`.

## Failure boundaries

Broad `Exception` handling remains only at three explicit boundaries, with adjacent comments:

- The CLI translates unexpected failures into a nonzero exit status.
- The strict checker records an unexpected failure for a source and continues the batch.
- WMS sync records unexpected per-source failures without discarding other results.

Transport, XML, projection, image-decoding, and GUI-input operations catch their specific
documented exception types. Unit tests prohibit unmocked HTTP requests.

## Verification

```sh
uv run ruff check .
uv run ruff format --check .
uv run flake8 src tests
uv run pylint src/eli tests
uv run mypy .
uv run pyrefly check
uv run pytest
```

Pylance uses the project's `.venv` interpreter and the `[tool.pyright]` settings.
Select Pylance as the diagnostic source when checking its own results independently.
