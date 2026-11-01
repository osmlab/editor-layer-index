# Developing ELI tooling

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and libmagic
(`brew install libmagic` on macOS; `apt-get install libmagic1` on Ubuntu).
Python 3.14 is the minimum and development default; Python 3.14 and 3.15 run in CI.

```sh
uv sync --locked
uv run eli check
uv run eli build --output-dir build
uv run eli site --build-dir build --output-dir build/site
uv run python -m http.server --directory build/site
```

`pyproject.toml` declares dependencies; `uv.lock` locks the complete environment.
Use `uv add`/`uv remove` to change dependencies and `uv lock --upgrade-package NAME`
for targeted updates. CI uses `--locked` to reject stale lockfiles. Do not maintain
separate pip requirements files. The browser frontend needs no Node build step.
The existing `package.json` remains available for Git-installed data consumers.

Commands find the data repository from the current directory or its ancestors.
Use `uv run eli --root /path/to/repository COMMAND` for a different data tree.
Source arguments accept individual GeoJSON files or directories recursively;
omitting them selects all `sources`. Files are deduplicated and sorted by their
relative paths. Validation considers duplicate IDs across the entire selection.
Normal offline PR checks always select the full corpus.

## Commands

| Command | Behavior |
| --- | --- |
| `eli check [paths…]` | Offline schema, ID, URL-template, and geometry checks |
| `eli check --strict [paths…]` | Offline checks followed by strict live-server checks |
| `eli check --strict --changed-from BASE --head HEAD` | Check surviving sources changed since the Git merge base |
| `eli build --output-dir build` | Generate `imagery.geojson`, `imagery.json`, `imagery.xml`, and `i18n/en.yaml` |
| `eli site --output-dir build/site` | Build outputs and assemble the complete public website |
| `eli site --build-dir build --output-dir build/site` | Assemble using an existing build without regenerating it |
| `eli convert-legacy [-b] [-t] [-r] [paths…]` | Write legacy JSON to stdout; preserve bbox, TMS-only, and polygon-removal options |
| `eli sync-wms [paths…]` | Contact imagery servers and rewrite selected WMS sources in place |
| `eli sync-categories --output-dir DIR` | Fetch JOSM categories and write changed source copies into DIR |
| `eli import-josm FILE --output-dir DIR` | Convert JOSM XML to individual source files in DIR |
| `eli geojsonify [paths…]` | Convert legacy source JSON to GeoJSON in place; use only on legacy input |
| `eli unembed-icons [paths…]` | Extract embedded PNGs and rewrite source icon URLs in place |
| `eli audit-urls [paths…]` | Report redirects and potential HTTPS conversions without modifying files |
| `eli minzoom [paths…] --output-dir DIR` | Interactive graphical tile preview; selections rewrite minimum zoom in place |
| `eli translations push` | Regenerate English strings and run `tx push -s` |
| `eli translations pull` | Run `tx pull -a --use-git-timestamps` |

Prefix these commands with `uv run`. `eli --help` and subcommand help describe
arguments. Transifex commands require an independently installed modern `tx`
client and its normal credentials configuration. Live checks retain the existing
imagery-server TLS compatibility policy; synchronous requests have a 30-second
timeout. WMS sync keeps its asynchronous processing and per-host limits.

Builds do not edit sources. Every export renders successfully before previous
outputs are replaced; failed replacements restore previous files. Set
`SOURCE_DATE_EPOCH` to generate a fixed UTC GeoJSON metadata timestamp for
reproducibility. Export field handling, float rounding, XML shape limits and
legacy conversion options follow the previous scripts.

Five-decimal coordinate rounding is retained only when the rounded geometry is
valid. Otherwise exports preserve the original geometry, including sufficient
XML coordinate precision; they do not repair topology or discard collapsed rings.
Before replacing outputs, the build parses all four artifacts, validates the
exported geometries and schema, reconciles source IDs and order, and checks core
metadata, legacy extents and English translation content against the inputs.
Site assembly and Git publication repeat these checks on existing build files.
Invalid artifacts leave previous outputs intact. Tests cover the complete source
corpus, precision-sensitive geometries, malformed XML and corrupted builds.

## Checks

```sh
uv run ruff check .
uv run ruff format --check .
uv run flake8 src tests
uv run pylint src/eli tests
uv run pyrefly check
uv run mypy
uv run pytest --cov=eli --cov-report=term-missing
uv run eli check
uv run eli build
```

Mypy checks both `src/eli` and `tests` in strict mode by default. Explicit whole-workspace checks (`uv run mypy .`), including the VS Code mypy extension, cover the same files.

Unit tests use stored capabilities documents and mocked HTTP responses. Live
strict checks remain a separate required PR job on changed sources. Git paths
are read with NUL delimiters; deleted files are excluded and renamed destinations
are checked. A PR with no changed source files skips live checks successfully.

## Publishing and rollout

The source branch remains `gh-pages`. The push workflow builds once, assembles a
complete site, updates the four generated Git files for existing consumers, and
uploads the same build as a Pages artifact. In particular, iD currently installs
this branch through npm and reads `imagery.geojson` and translation YAML locally.
Keep those generated files and `package.json` in Git. Vespucci and Go Map!! fetch
`imagery.geojson` from Pages; Potlatch 3 fetches `imagery.json`.

The artifact includes the frontend, translations, schema, sources, icons and
permission documents, so existing public paths remain available. Generation-only
commits do not start another deployment. Git updates use normal fast-forward
pushes; a source commit arriving during a build supersedes that run. The deploy
job also checks that its published head is still current. Pages runs share a
concurrency group so newer runs cancel superseded work.

The deployment workflow runs the regression suite before building or publishing,
including on direct pushes and manual dispatches. Artifact validation is part of
the same build commands used by PR checks and deployment.

After merging the tooling changes, set **Settings → Pages → Build and deployment
→ Source → GitHub Actions**, then dispatch the Deploy workflow. Configure the
`github-pages` environment to allow `gh-pages`. The workflow needs `contents:
write` for generated Git files and `pages: write`/`id-token: write` for deployment;
branch rules must permit the existing bot output update. WMS PR creation also
requires repository permission for Actions to create pull requests.

Verify the site, all three imagery URLs, English translations, and a referenced
source icon and permission document. Confirm the files committed by the bot match
the Pages build. Repository settings and a live deployment are rollout steps,
not effects of running the local build.

To roll back publishing, restore `.github/workflows/push.yml` from the parent of
the modernization change and switch the Pages source back to the `gh-pages`
branch at `/`. The previous branch deployment workflow is retained in Git history.

Additional type checks can be run with `uv run pyrefly check`, and with the
Pylance extension in VS Code using the project's `.venv` interpreter. Both use
source-and-test configuration in `pyproject.toml`; Pylance uses standard checking
and mypy remains strict. Shapely and regex stubs are installed with the development
dependencies; the package includes a `py.typed` marker for installed consumers.
Select **Pylance** as the diagnostics source to run its own checker independently
of the extension's optional Pyrefly integration.

Formatting, supported lint exceptions, and the verification commands are documented in
[LINTING.md](LINTING.md). All Python linters and the formatter use a 100-character line width.

### Catalogue lint and live-check policy

`uv run eli check` rejects unclosed rings, consecutive duplicate vertices,
incorrect RFC 7946 winding (including holes), duplicate projection codes, local
null geometry, and string placeholders such as `privacy_policy_url: "none"`.
Use the JSON boolean `false` for a researched absence of a privacy policy.
Geometry fixes must preserve coverage; source lint never repairs geometry silently.

Projection usefulness warnings follow JOSM's `SyncEditorLayerIndex.setupProj`
obsolete-code list. ELI also omits CRS:84 when EPSG:4326 or EPSG:3857 is listed;
a sole CRS:84 remains useful for WMS 1.3. These recommendations are warnings for
legacy catalogue entries, not automatic CRS substitutions. WMS sync uses the same
policy and never invents replacement server support. In particular, advertised
projections and working projections need not be identical.

Strict checks cache responses and transport failures for the duration of one
run. Identical URLs and request options (including headers) share one request;
a new invocation starts fresh. Each source still receives its own diagnostics.
Requests default to a five-second connection timeout and a twenty-second read
inactivity timeout, not a total wall-clock deadline. Connection failures stop
WMS version negotiation; parse/protocol failures may still try other versions.
Coverage is checked only when every selected layer has geographic bounds, so an
unknown layer does not produce a misleading “100% outside” error. HTTP failures
remain failures; caching and quieter logging do not turn 403s into successes.

Ruff's S113 rule guards explicit request timeouts, alongside the existing format,
lint, type, test, and offline-source checks in CI. Deterministic regression tests
cover the provider failures above without contacting external services.
