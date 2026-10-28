"""Provide isolated ELI repositories and source fixtures for tests."""

import json
import shutil
from pathlib import Path
from typing import Never

import pytest
import requests
from aiohttp import ClientSession

from eli.common import JSON


@pytest.fixture(name="data_root")
def data_root_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    shutil.copy2(Path(__file__).resolve().parents[1] / "schema.json", root / "schema.json")
    (root / "sources/europe/de").mkdir(parents=True)
    for name in ("site", "i18n"):
        (root / name).mkdir()
    (root / "index.html").write_text('<script src="site/site.js"></script>')
    (root / "site/site.js").write_text('fetch("imagery.geojson")')
    (root / "sources/europe/de/license.pdf").write_bytes(b"permission document")
    (root / "sources/europe/de/icon.png").write_bytes(b"icon")
    (root / "i18n/fr.yaml").write_text("fr: {}\n")
    (root / "package.json").write_text('{"name":"@openstreetmap/editor-layer-index"}')
    return root


@pytest.fixture(name="feature")
def feature_fixture() -> JSON:
    return {
        "type": "Feature",
        "properties": {
            "id": "test-layer",
            "name": "Ünicode layer",
            "type": "tms",
            "country_code": "DE",
            "url": "https://example.org/{zoom}/{x}/{y}.png",
            "category": "photo",
            "privacy_policy_url": False,
            "license_url": "https://example.org/license",
            "i18n": True,
            "description": "A test",
            "min_zoom": 0,
            "max_zoom": 20,
        },
        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
    }


@pytest.fixture(name="source")
def source_fixture(data_root: Path, feature: JSON) -> Path:
    path = data_root / "sources/europe/de/source with spaces.geojson"
    path.write_text(json.dumps(feature), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def disable_live_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep unit tests deterministic: every HTTP request must be explicitly mocked."""

    def fail_request(*args: object, **kwargs: object) -> Never:
        pytest.fail(f"Unexpected live HTTP request: {args!r}, {kwargs!r}")

    monkeypatch.setattr(requests.sessions.Session, "request", fail_request)
    monkeypatch.setattr(ClientSession, "request", fail_request)
