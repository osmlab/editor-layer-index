# Dependency audit — 2026-10-27

Python 3.14 is the minimum and development default. CI also checks Python 3.15.
Latest non-prerelease, non-yanked versions were checked against the official [PyPI JSON API](https://docs.pypi.org/api/json/).
The upgraded environment has no outdated direct or transitive packages (`uv pip list --outdated` returned `[]`).
The lockfile records the complete resolved environment; all entries below were verified against their current releases.

| Dependency | Selected version | Latest stable |
| --- | --- | --- |
| [aiofiles](https://pypi.org/project/aiofiles/) | 25.1.0 | 25.1.0 |
| [aiohttp](https://pypi.org/project/aiohttp/) | 3.14.5 | 3.14.5 |
| [certifi](https://pypi.org/project/certifi/) | 2026.10.23 | 2026.10.23 |
| [colorlog](https://pypi.org/project/colorlog/) | 6.12.0 | 6.12.0 |
| [flake8](https://pypi.org/project/flake8/) | 7.4.1 | 7.4.1 |
| [hatchling](https://pypi.org/project/hatchling/) | 1.32.4 | 1.32.4 |
| [imagehash](https://pypi.org/project/imagehash/) | 4.3.2 | 4.3.2 |
| [jsonschema](https://pypi.org/project/jsonschema/) | 4.26.0 | 4.26.0 |
| [matplotlib](https://pypi.org/project/matplotlib/) | 3.11.2 | 3.11.2 |
| [mercantile](https://pypi.org/project/mercantile/) | 1.2.1 | 1.2.1 |
| [mypy](https://pypi.org/project/mypy/) | 2.4.0 | 2.4.0 |
| [pillow](https://pypi.org/project/pillow/) | 13.0.0 | 13.0.0 |
| [pylint](https://pypi.org/project/pylint/) | 4.1.3 | 4.1.3 |
| [pyproj](https://pypi.org/project/pyproj/) | 3.8.0 | 3.8.0 |
| [pyrefly](https://pypi.org/project/pyrefly/) | 1.4.0 | 1.4.0 |
| [pytest-cov](https://pypi.org/project/pytest-cov/) | 7.1.0 | 7.1.0 |
| [pytest](https://pypi.org/project/pytest/) | 9.1.1 | 9.1.1 |
| [python-magic](https://pypi.org/project/python-magic/) | 0.4.27 | 0.4.27 |
| [PyYAML](https://pypi.org/project/PyYAML/) | 6.0.3 | 6.0.3 |
| [regex](https://pypi.org/project/regex/) | 2026.9.29 | 2026.9.29 |
| [requests](https://pypi.org/project/requests/) | 2.34.2 | 2.34.2 |
| [ruff](https://pypi.org/project/ruff/) | 0.17.3 | 0.17.3 |
| [shapely](https://pypi.org/project/shapely/) | 2.2.0 | 2.2.0 |
| [types-aiofiles](https://pypi.org/project/types-aiofiles/) | 25.1.0.20260518 | 25.1.0.20260518 |
| [types-jsonschema](https://pypi.org/project/types-jsonschema/) | 4.26.0.20261006 | 4.26.0.20261006 |
| [types-PyYAML](https://pypi.org/project/types-PyYAML/) | 6.0.12.20260906 | 6.0.12.20260906 |
| [types-regex](https://pypi.org/project/types-regex/) | 2026.9.29.20261017 | 2026.9.29.20261017 |
| [types-requests](https://pypi.org/project/types-requests/) | 2.33.0.20261006 | 2.33.0.20261006 |
| [types-shapely](https://pypi.org/project/types-shapely/) | 2.1.0.20260728 | 2.1.0.20260728 |
| [urllib3](https://pypi.org/project/urllib3/) | 2.8.0 | 2.8.0 |
| [validators](https://pypi.org/project/validators/) | 0.36.0 | 0.36.0 |

## Typing

The `eli` package ships its inline annotations with a `py.typed` marker in both its wheel and source distribution.
Development dependencies now include the published Shapely and regex stubs, alongside the existing requests, YAML, aiofiles, and jsonschema stubs.
Mypy no longer ignores typing for Shapely, pyproj, ImageHash, python-magic, validators, or colorlog.
Mercantile has neither bundled typing metadata nor a published `types-mercantile` package; its missing-import exception remains scoped to that dependency.

## GitHub Actions

| Action | Latest release selected |
| --- | --- |
| actions/checkout | [v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1) |
| astral-sh/setup-uv | [v10.3.2](https://github.com/astral-sh/setup-uv/releases/tag/v10.3.2) |
| actions/configure-pages | [v6.0.0](https://github.com/actions/configure-pages/releases/tag/v6.0.0) |
| actions/upload-pages-artifact | [v5.0.0](https://github.com/actions/upload-pages-artifact/releases/tag/v5.0.0) |
| actions/github-script | [v9.0.0](https://github.com/actions/github-script/releases/tag/v9.0.0) |
| actions/deploy-pages | [v5.0.1](https://github.com/actions/deploy-pages/releases/tag/v5.0.1) |
| peter-evans/create-pull-request | [v8.1.1](https://github.com/peter-evans/create-pull-request/releases/tag/v8.1.1) |

The updated actions were checked against their release notes and the workflows validated with actionlint.
The github-script code uses its injected `github` client, so it does not use the CommonJS imports removed in v9.

## Browser libraries — audit only

These vendored files are unchanged. Their upgrade is a separate frontend task.

| Library | Vendored version | Current stable version |
| --- | --- | --- |
| D3 | 3.0.8 | [7.9.0](https://www.npmjs.com/package/d3) |
| Leaflet | 1.0.1+ffcfcc1 | [1.9.4](https://www.npmjs.com/package/leaflet) |
| leaflet-pip | Unversioned bundled snapshot | [1.1.0](https://www.npmjs.com/package/leaflet-pip) |

D3 needs changes to callback-based JSON loading, event handler arguments, and `d3.geo.bounds` before a major upgrade.
Leaflet and leaflet-pip need map-preview and point-in-polygon verification together. No browser compatibility is claimed from this audit alone.

## Rechecking

```sh
uv sync --locked
uv pip list --outdated
uv run flake8 src tests
uv run pylint src/eli tests
uv run mypy .
uv run pyrefly check
uv run pytest
uv build
```
