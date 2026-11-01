"""Provider payload, real projection probe, coverage, and exception regressions."""

import io
import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from PIL import Image
from shapely.geometry import box

from eli.build import export_source
from eli.common import JSON, canonical_request_url
from eli.image_validation import image_payload
from eli.known_failures import KnownFailures
from eli.libeli import tmshelper
from eli.libeli.eliutils import BoundingBox
from eli.live_probes import render_url, sample_bounds
from eli.strict import StrictChecker
from eli.strict_context import Message, MessageLevel

WMS_URL = (
    "https://example.org/wms?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0"
    "&LAYERS=0&STYLES=&FORMAT=image/png&CRS={proj}"
    "&WIDTH={width}&HEIGHT={height}&BBOX={bbox}"
)


def png() -> bytes:
    image = Image.new("RGB", (4, 4), "white")
    image.putpixel((0, 0), (0, 0, 0))
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


@pytest.mark.parametrize(
    "data",
    [
        b"<html>Blocked</html>",
        b'{"error":{"code":499}}',
        b"<ServiceException>Invalid CRS</ServiceException>",
    ],
)
def test_error_documents_are_not_images(data: bytes) -> None:
    assert image_payload(data) == (False, False)


def test_images_and_icons_are_decoded() -> None:
    assert image_payload(png()) == (True, False)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"/>'
    assert image_payload(svg, allow_svg=True) == (True, False)
    assert image_payload(svg) == (False, False)
    assert image_payload(png()[:25]) == (False, False)


def test_axis_order_and_arcgis_numeric_crs() -> None:
    bbox = BoundingBox(10, 12, 40, 42)
    assert "BBOX=40,10,42,12" in render_url(WMS_URL, "EPSG:4326", bbox)
    assert "BBOX=10,40,12,42" in render_url(WMS_URL.replace("1.3.0", "1.1.1"), "EPSG:4326", bbox)
    esri = (
        "https://example.org/MapServer/export?f=image&bboxSR={proj}"
        "&bbox={bbox}&size={width},{height}"
    )
    assert "bboxSR=4326&bbox=10,40,12,42" in render_url(esri, "EPSG:4326", bbox)


def test_every_configured_crs_and_both_common_crss_are_probed(
    data_root: Path, feature: JSON, monkeypatch: pytest.MonkeyPatch
) -> None:
    feature["properties"].update(url=WMS_URL, available_projections=["EPSG:31983"])
    fetch = Mock(return_value=Mock(status_code=200, content=png()))
    monkeypatch.setattr("eli.strict_context.request_get", fetch)
    messages: list[Message] = []
    checker = StrictChecker(data_root)
    checker.check_rendering(feature, messages)
    urls = [call.args[0] for call in fetch.call_args_list]
    assert all(
        any(f"CRS={crs}" in url for url in urls) for crs in ["EPSG:31983", "EPSG:4326", "EPSG:3857"]
    )
    assert not any(m.level == MessageLevel.ERROR for m in messages)
    assert sum("not listed" in m.message for m in messages) == 2


def test_configured_projection_failure_is_an_error(
    data_root: Path, feature: JSON, monkeypatch: pytest.MonkeyPatch
) -> None:
    feature["properties"].update(url=WMS_URL, available_projections=["EPSG:3857"])
    monkeypatch.setattr(
        "eli.strict_context.request_get",
        Mock(return_value=Mock(status_code=200, content=b"<html>Error</html>")),
    )
    messages: list[Message] = []
    StrictChecker(data_root).check_rendering(feature, messages)
    assert any(m.level == MessageLevel.ERROR and "3857" in m.message for m in messages)
    assert all(m.level == MessageLevel.INFO for m in messages if "4326" in m.message)


@pytest.mark.parametrize(
    "bbox,expected",
    [
        (BoundingBox(0, 1, 0, 1), 0),
        (BoundingBox(0, 0.5, 0, 1), 50),
        (BoundingBox(2, 3, 2, 3), 100),
        ([BoundingBox(0, 0.5, 0, 1), BoundingBox(0.5, 1, 0, 1)], 0),
    ],
)
def test_coverage_calculations(
    data_root: Path, bbox: BoundingBox | list[BoundingBox], expected: int
) -> None:
    assert StrictChecker(data_root).max_area_outside_bbox(box(0, 0, 1, 1), bbox) == pytest.approx(
        expected
    )


def test_asymmetric_tms_bbox_and_reprojection() -> None:
    xml = (Path(__file__).parent / "data/tms/tilemapresource.xml").read_text()
    xml = (
        xml.replace('minx="-180"', 'minx="10"')
        .replace('miny="-90"', 'miny="40"')
        .replace('maxx="180"', 'maxx="12"')
        .replace('maxy="90"', 'maxy="42"')
    )
    resource = tmshelper.TileMapResource(xml)
    assert resource.tile_map is not None
    assert resource.tile_map.bbox84 == BoundingBox(10, 12, 40, 42)
    metres = (
        xml.replace("EPSG:4326", "EPSG:3857")
        .replace('minx="10"', 'minx="1000000"')
        .replace('miny="40"', 'miny="4000000"')
        .replace('maxx="12"', 'maxx="1200000"')
        .replace('maxy="42"', 'maxy="4200000"')
    )
    resource = tmshelper.TileMapResource(metres)
    assert resource.tile_map is not None and resource.tile_map.bbox84 is not None
    assert resource.tile_map.bbox84.south == pytest.approx(33.78523, abs=0.00001)
    with pytest.raises(ValueError, match="Suspicious"):
        tmshelper.TileMapResource(xml.replace("EPSG:4326", "EPSG:3857"))


def test_projection_lists_are_not_exported_for_tms(source: Path, feature: JSON) -> None:
    feature["properties"]["available_projections"] = ["EPSG:3857"]
    source.write_text(json.dumps(feature))
    assert "available_projections" not in export_source(source, feature)["properties"]
    assert "available_projections" in feature["properties"]


def test_query_order_is_not_a_distinct_source() -> None:
    assert canonical_request_url("https://example.org?a=1&b=2") == canonical_request_url(
        "https://example.org?b=2&a=1"
    )
    assert canonical_request_url("https://example.org?LAYERS=a,b") != canonical_request_url(
        "https://example.org?LAYERS=b,a"
    )


def rule_file(tmp_path: Path, **overrides: object) -> Path:
    rule = {
        "url": "https://example.org/privacy",
        "status": 403,
        "expires": "2099-01-01",
        "reason": "Bot protection in CI",
        "environment": "github-actions",
    } | overrides
    path = tmp_path / "exceptions.json"
    path.write_text(json.dumps([rule]))
    return path


def test_known_failures_are_exact_expiring_and_environment_scoped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rules = KnownFailures(rule_file(tmp_path))
    message = Message(MessageLevel.ERROR, "HTTP code: 403 https://example.org/privacy")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert rules.classify(message) is None
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert rules.classify(message) == "Bot protection in CI"
    for text in [
        "HTTP code: 404 https://example.org/privacy",
        "HTTP code: 403 https://example.org/privacy/other",
    ]:
        assert rules.classify(Message(MessageLevel.ERROR, text)) is None
    assert rules.unused_rules() == []
    cases: list[dict[str, Any]] = [
        {"url": "https://example.org/*"},
        {"status": 200},
        {"expires": "2000-01-01"},
        {"reason": ""},
    ]
    for values in cases:
        with pytest.raises(ValueError):
            KnownFailures(rule_file(tmp_path, **values))


def test_report_keeps_known_failures_visible(
    data_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    checker = StrictChecker(data_root)
    checker.known_failures = KnownFailures(rule_file(tmp_path))
    checker.report_path = tmp_path / "audit.json"
    message = Message(
        MessageLevel.ERROR, "Blocked", code="icon", url="https://example.org/privacy", status=403
    )
    records = checker.classify_diagnostics([message])
    assert message.level == MessageLevel.WARNING
    checker.write_report(records)
    report = json.loads(checker.report_path.read_text(encoding="utf-8"))
    assert report["diagnostics"][0]["known_failure"] == "Bot protection in CI"
    assert report["diagnostics"][0]["level"] == "ERROR"


def test_tile_recovery_checks_different_interior_locations(
    data_root: Path, feature: JSON, monkeypatch: pytest.MonkeyPatch
) -> None:
    samples = sample_bounds(feature)
    assert len(samples) >= 2
    checker = StrictChecker(data_root)
    fetch = Mock(return_value=(True, 200, "image/png"))
    monkeypatch.setattr(checker, "test_image", fetch)
    assert checker.recover_tile(feature, 15, {})
    assert fetch.call_count == 1


@pytest.mark.parametrize("outcome", [(403, 0), (404, 1)])
def test_known_failures_affect_exit_status_only_for_exact_matches(
    data_root: Path,
    source: Path,
    feature: JSON,
    monkeypatch: pytest.MonkeyPatch,
    outcome: tuple[int, int],
) -> None:
    status, expected = outcome
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    feature["properties"]["privacy_policy_url"] = "https://example.org/privacy"
    source.write_text(json.dumps(feature))
    checker = StrictChecker(data_root)
    checker.known_failures = KnownFailures(rule_file(data_root))
    checker.report_path = data_root / "audit.json"
    monkeypatch.setattr(checker, "check_tms", Mock())

    def response(url: str, **_kwargs: object) -> Mock:
        return Mock(status_code=status if url.endswith("/privacy") else 200)

    monkeypatch.setattr(checker, "get_response", response)
    assert checker.run([source], data_root) == expected
    assert checker.report_path.is_file()


def test_root_url_exception_does_not_match_other_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    rules = KnownFailures(rule_file(tmp_path, url="https://example.org/"))
    assert (
        rules.classify(Message(MessageLevel.ERROR, "HTTP code: 403 https://example.org/privacy"))
        is None
    )


def test_icon_redirect_to_html_is_rejected(
    data_root: Path, feature: JSON, monkeypatch: pytest.MonkeyPatch
) -> None:
    feature["properties"]["icon"] = "https://example.org/favicon.ico"
    checker = StrictChecker(data_root)
    monkeypatch.setattr(
        checker,
        "get_response",
        Mock(return_value=Mock(status_code=200, content=b"<html>Homepage</html>")),
    )
    messages: list[Message] = []
    checker.check_icon(feature, messages)
    assert any(m.code == "icon" and m.level == MessageLevel.ERROR for m in messages)
