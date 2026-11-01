"""Regressions from real imagery-provider and catalogue failures."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from eli.check import run
from eli.common import JSON
from eli.libeli import wmshelper
from eli.projections import unused_projections, useful_projections
from eli.strict import StrictChecker
from eli.strict_context import Message

WMS_URL = (
    "https://example.org/wms?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0"
    "&LAYERS=0&STYLES=&FORMAT=image/png&CRS={proj}"
    "&WIDTH={width}&HEIGHT={height}&BBOX={bbox}"
)


@pytest.mark.parametrize("value", [None, "none", "false", "null", "", True])
def test_local_geometry_and_policy_errors(
    data_root: Path, source: Path, feature: JSON, value: object
) -> None:
    if value is None:
        feature["geometry"] = None
    else:
        feature["properties"]["privacy_policy_url"] = value
    source.write_text(json.dumps(feature))
    assert run([source], data_root) == 1


def test_global_null_geometry_and_boolean_policy(data_root: Path, feature: JSON) -> None:
    source = data_root / "sources/world/bing.geojson"
    source.parent.mkdir()
    feature["geometry"] = None
    feature["properties"]["type"] = "bing"
    source.write_text(json.dumps(feature))
    assert run([source], data_root) == 0


@pytest.mark.parametrize(
    "codes,url,expected",
    [
        (["EPSG:900913"], None, {"EPSG:900913"}),
        (["EPSG:31297", "EPSG:31287"], None, {"EPSG:31297"}),
        (["EPSG:3359", "EPSG:3404"], None, {"EPSG:3359"}),
        (["CRS:84"], WMS_URL, set()),
        (["CRS:84"], WMS_URL.replace("1.3.0", "1.1.1"), {"CRS:84"}),
        (["CRS:84", "EPSG:3857"], WMS_URL, {"CRS:84"}),
        (["CRS:84", "EPSG:4326"], WMS_URL, {"CRS:84"}),
    ],
)
def test_josm_projection_policy(codes: list[str], url: str | None, expected: set[str]) -> None:
    assert unused_projections(codes, url) == expected
    assert useful_projections(codes).isdisjoint(expected - {"CRS:84"})


@pytest.mark.parametrize("method", ["check_wms", "check_wms_endpoint"])
@pytest.mark.parametrize(
    "error", [requests.ReadTimeout("timeout"), requests.ConnectionError("closed")]
)
def test_transport_failure_does_not_retry_versions(
    data_root: Path,
    feature: JSON,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    error: requests.RequestException,
) -> None:
    feature["properties"].update(url=WMS_URL, type="wms", available_projections=["EPSG:4326"])
    fetch = Mock(side_effect=error)
    monkeypatch.setattr(StrictChecker, "get_text_encoded", fetch)
    messages: list[Message] = []
    getattr(StrictChecker(data_root), method)(feature, messages)
    assert fetch.call_count == 1
    assert any(type(error).__name__ in m.message for m in messages)


@pytest.mark.parametrize(
    "layers", [{}, {"0": Mock(bbox=None, crs={"EPSG:4326", "CRS:84"}, styles={})}]
)
def test_unknown_or_unbounded_layer_does_not_invent_coverage_failure(
    data_root: Path, feature: JSON, monkeypatch: pytest.MonkeyPatch, layers: dict[str, Mock]
) -> None:
    feature["properties"].update(url=WMS_URL, type="wms", available_projections=["EPSG:4326"])
    caps = Mock(
        layers=layers, version="1.3.0", access_constraints=[], fees=[], formats=["image/png"]
    )
    monkeypatch.setattr(wmshelper, "WMSCapabilities", Mock(return_value=caps))
    monkeypatch.setattr(StrictChecker, "get_text_encoded", Mock(return_value=(Mock(), "xml")))
    monkeypatch.setattr(StrictChecker, "check_rendering", Mock())
    messages: list[Message] = []
    StrictChecker(data_root).check_wms(feature, messages)
    assert not any("outside" in m.message for m in messages)
    assert not any("not included" in m.message for m in messages)
    assert bool(layers) or any("not advertised" in m.message for m in messages)


def test_request_failure_is_concise(data_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    checker = StrictChecker(data_root)
    monkeypatch.setattr(
        checker, "get_response", Mock(side_effect=requests.ConnectionError("closed"))
    )
    log = Mock()
    monkeypatch.setattr(checker, "logger", log)
    assert checker.test_url("https://example.org") == (False, -1)
    assert checker.test_image("https://example.org") == (False, -1, None)
    assert log.error.call_count == 2
    log.exception.assert_not_called()


@pytest.mark.parametrize("status", [200, 403, 404, 500])
def test_shared_policy_is_requested_once(
    data_root: Path, monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    fetch = Mock(return_value=Mock(status_code=status))
    monkeypatch.setattr("eli.strict_context.request_get", fetch)
    checker = StrictChecker(data_root)
    for _ in range(6):
        assert checker.test_url("https://example.org/privacy") == (status == 200, status)
    assert fetch.call_count == 1
    # A new run must not reuse old errors or stale successes.
    StrictChecker(data_root).test_url("https://example.org/privacy")
    assert fetch.call_count == 2


def test_failed_request_is_cached_and_headers_separate_requests(
    data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fetch = Mock(side_effect=requests.ReadTimeout("timeout"))
    monkeypatch.setattr("eli.strict_context.request_get", fetch)
    checker = StrictChecker(data_root)
    for _ in range(6):
        assert checker.test_url("https://example.org/privacy") == (False, -1)
    assert fetch.call_count == 1
    checker.test_url("https://example.org/privacy", {"Authorization": "different"})
    assert fetch.call_count == 2
