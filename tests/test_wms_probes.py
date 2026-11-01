"""Port PR #3089's provider-response and safe-sampling regressions to the CLI."""

import io
from pathlib import Path
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from PIL import Image
from shapely.geometry import Polygon, box, mapping

from eli.common import JSON
from eli.libeli.eliutils import BoundingBox
from eli.live_probes import sample_bounds
from eli.response_diagnostics import describe_response
from eli.strict import StrictChecker
from eli.strict_context import Message, MessageLevel


@pytest.fixture(name="wms_source")
def wms_source_fixture(feature: JSON) -> JSON:
    feature["properties"].update(
        type="wms",
        url="https://example.org/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap"
        "&LAYERS=photo,overlay&STYLES=default,lines&TIME=2026&token=keep-me&FORMAT=image/png"
        "&CRS={proj}&BBOX={bbox}&WIDTH={width}&HEIGHT={height}",
        available_projections=["EPSG:3857", "EPSG:4326", "CRS:84", "EPSG:4026", "EPSG:900913"],
    )
    feature["geometry"] = mapping(box(28, 46, 29, 47))
    return feature


def response_image(
    *, size: tuple[int, int] = (256, 256), transparent: bool = False
) -> requests.Response:
    image = Image.new("RGBA", size, (0, 255, 0, 0) if transparent else "green")
    image.putpixel((0, 0), (255, 0, 0, 0) if transparent else (255, 0, 0, 255))
    output = io.BytesIO()
    image.save(output, "PNG")
    response = requests.Response()
    response.status_code = 200
    response._content = output.getvalue()  # pylint: disable=protected-access
    response.headers["Content-Type"] = "image/png"
    return response


def test_every_crs_preserves_request_options(
    data_root: Path, wms_source: JSON, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    wms_source["properties"]["custom-http-headers"] = {
        "header-name": "X-Test",
        "header-value": "yes",
    }

    def fetch(url: str, **kwargs: object) -> requests.Response:
        calls.append(url)
        assert isinstance(kwargs["headers"], dict) and kwargs["headers"]["X-Test"] == "yes"
        assert kwargs["timeout"] == (5, 20)
        params = parse_qs(urlsplit(url).query)
        for key, value in (
            ("TIME", "2026"),
            ("token", "keep-me"),
            ("STYLES", "default,lines"),
            ("LAYERS", "photo,overlay"),
        ):
            assert params[key] == [value]
        return response_image()

    monkeypatch.setattr("requests.get", fetch)
    messages: list[Message] = []
    StrictChecker(data_root).check_rendering(wms_source, messages)
    assert {parse_qs(urlsplit(url).query)["CRS"][0] for url in calls} == set(
        wms_source["properties"]["available_projections"]
    )
    assert not any(m.level == MessageLevel.ERROR for m in messages)


def test_samples_stay_inside_thin_coverage_with_holes(wms_source: JSON) -> None:
    coverage = Polygon(
        box(28, 46, 28.0001, 47).exterior.coords,
        holes=[box(28.00002, 46.2, 28.00008, 46.8).exterior.coords],
    )
    wms_source["geometry"] = mapping(coverage)
    for bounds in sample_bounds(wms_source):
        assert coverage.contains(box(bounds.west, bounds.south, bounds.east, bounds.north))


@pytest.mark.parametrize("kind", ["timeout", "wrong-size", "corrupt", "projection"])
def test_failed_crs_does_not_skip_other_projections(
    data_root: Path, wms_source: JSON, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    wms_source["properties"]["available_projections"] = ["EPSG:3857", "EPSG:4326"]
    if kind == "projection":
        wms_source["properties"]["available_projections"][0] = "EPSG:0"

    def fetch(url: str, **_kwargs: object) -> requests.Response:
        if "CRS=EPSG:3857" in url:
            if kind == "timeout":
                raise requests.Timeout("timed out")
            if kind == "wrong-size":
                return response_image(size=(32, 32))
            response = response_image()
            response._content = b"\x89PNG\r\n\x1a\ncorrupt"  # pylint: disable=protected-access
            return response
        return response_image()

    monkeypatch.setattr("eli.strict_context.request_get", fetch)
    messages: list[Message] = []
    StrictChecker(data_root).check_rendering(wms_source, messages)
    assert any(m.level == MessageLevel.ERROR for m in messages)
    assert any("4326: actual image request succeeded" in m.message for m in messages)


@pytest.mark.parametrize(
    "status,mime,body,expected",
    [
        (
            499,
            "application/json",
            b'{"error":{"code":499,"message":"Token Required"}}',
            "Token Required",
        ),
        (
            200,
            "image/jpeg",
            b'<ServiceException code="InvalidSRS">Unsupported CRS</ServiceException>',
            "InvalidSRS Unsupported CRS",
        ),
        (
            200,
            "text/xml",
            b'<Exception exceptionCode="LayerNotDefined" locator="LAYERS">'
            b"<ExceptionText>Unknown layer</ExceptionText></Exception>",
            "LayerNotDefined (LAYERS) Unknown layer",
        ),
        (
            405,
            "text/html",
            b"<html><title>Method Not Allowed</title><body>GET rejected</body></html>",
            "Method Not Allowed GET rejected",
        ),
    ],
)
# Provider response fields and pytest fixtures are separate test dimensions.
# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def test_server_error_details(
    data_root: Path,
    wms_source: JSON,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    mime: str,
    body: bytes,
    expected: str,
) -> None:
    response = response_image()
    response.status_code = status
    response.headers["Content-Type"] = mime
    response._content = body  # pylint: disable=protected-access
    monkeypatch.setattr("eli.strict_context.request_get", lambda *_args, **_kwargs: response)
    messages: list[Message] = []
    StrictChecker(data_root).check_rendering(wms_source, messages)
    failure = next(m for m in messages if m.level == MessageLevel.ERROR)
    assert expected in failure.message
    assert f"HTTP {status}" in failure.message
    assert failure.message.count("https://example.org/wms") == 1
    assert "BytesIO" not in failure.message


def test_response_details_are_bounded() -> None:
    response = response_image()
    response.headers["Content-Type"] = "text/html"
    response._content = (  # pylint: disable=protected-access
        b"<html><script>hidden_script()</script><body>" + b"failure " * 1000 + b"</body></html>"
    )  # pylint: disable=protected-access
    details = describe_response(response)
    assert len(details) < 600
    assert "hidden_script" not in details
    assert details.endswith("…")
    response.headers["Content-Type"] = "image/png"
    response._content = b"\x89PNG\x00\x00binary secret"  # pylint: disable=protected-access
    assert "binary secret" not in describe_response(response)


def test_fully_transparent_image_with_varied_rgb_is_inconclusive(
    data_root: Path, wms_source: JSON, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "eli.strict_context.request_get", lambda *_args, **_kwargs: response_image(transparent=True)
    )
    messages: list[Message] = []
    StrictChecker(data_root).check_rendering(wms_source, messages)
    assert not any(m.level == MessageLevel.ERROR for m in messages)
    assert sum("uniform/blank" in m.message for m in messages) == 5


def test_capabilities_timeout_still_probes_images(
    data_root: Path, wms_source: JSON, monkeypatch: pytest.MonkeyPatch
) -> None:
    urls: list[str] = []

    def fetch(url: str, **_kwargs: object) -> requests.Response:
        urls.append(url)
        if "GetCapabilities" in url:
            raise requests.ConnectionError("Capabilities unavailable")
        return response_image()

    monkeypatch.setattr("eli.strict_context.request_get", fetch)
    messages: list[Message] = []
    StrictChecker(data_root).check_wms(wms_source, messages)
    assert sum("GetCapabilities" in url for url in urls) == 1
    assert sum("actual image request succeeded" in m.message for m in messages) == 5


def test_source_is_logged_exactly_once(data_root: Path, caplog: pytest.LogCaptureFixture) -> None:
    checker = StrictChecker(data_root)
    checker.filename = "sources/europe/ch/example.geojson"
    checker.log_messages(
        [
            Message(MessageLevel.ERROR, "CRS rejected"),
            Message(MessageLevel.WARNING, f"{checker.filename}: license unavailable"),
        ]
    )
    assert len(caplog.records) == 2
    assert all(r.message.count(checker.filename) == 1 for r in caplog.records)


def test_global_source_uses_capabilities_bounds(
    data_root: Path, wms_source: JSON, monkeypatch: pytest.MonkeyPatch
) -> None:
    wms_source["geometry"] = None
    coverage = box(28, 46, 29, 47)
    capabilities = Mock(
        layers={
            name: Mock(bbox=BoundingBox(28, 29, 46, 47), crs={"EPSG:4326"})
            for name in ("photo", "overlay")
        }
    )

    def fetch(url: str, **_kwargs: object) -> requests.Response:
        params = parse_qs(urlsplit(url).query)
        if params["CRS"] == ["CRS:84"]:
            west, south, east, north = map(float, params["BBOX"][0].split(","))
            assert coverage.contains(box(west, south, east, north))
        return response_image()

    monkeypatch.setattr("eli.strict_context.request_get", fetch)
    messages: list[Message] = []
    StrictChecker(data_root).check_rendering(wms_source, messages, capabilities)
    assert any("4326: actual image request succeeded (advertised)" in m.message for m in messages)
    assert any(
        "3857: actual image request succeeded (not advertised" in m.message for m in messages
    )


def test_capabilities_http_error_is_described_and_images_still_probed(
    data_root: Path, wms_source: JSON, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fetch(url: str, **_kwargs: object) -> requests.Response:
        response = response_image()
        if "GetCapabilities" in url:
            response.status_code = 499
            response.headers["Content-Type"] = "application/json"
            # pylint: disable-next=protected-access
            response._content = b'{"error":{"code":499,"message":"Token Required"}}'
        return response

    monkeypatch.setattr("eli.strict_context.request_get", fetch)
    messages: list[Message] = []
    StrictChecker(data_root).check_wms(wms_source, messages)
    failures = [m for m in messages if "GetCapabilities" in m.message]
    assert len(failures) == 5
    assert all("HTTP 499" in m.message and "Token Required" in m.message for m in failures)
    assert all(m.code == "capabilities" and m.status == 499 and m.url for m in failures)
    assert sum("actual image request succeeded" in m.message for m in messages) == 5


def test_capabilities_version_retry_recovers(
    data_root: Path, wms_source: JSON, monkeypatch: pytest.MonkeyPatch
) -> None:
    xml = (Path(__file__).parent / "data/wms/capabilities_1_3_0.xml").read_bytes()
    wms_source["properties"]["url"] = wms_source["properties"]["url"].replace(
        "photo,overlay", "ROADS_1M"
    )
    calls: list[str] = []

    def fetch(url: str, **_kwargs: object) -> requests.Response:
        calls.append(url)
        response = response_image()
        if "GetCapabilities" in url:
            response.status_code = 200 if "VERSION=1.3.0" in url else 500
            # pylint: disable-next=protected-access
            response._content = xml if response.status_code == 200 else b"unavailable"
        return response

    monkeypatch.setattr("eli.strict_context.request_get", fetch)
    messages: list[Message] = []
    StrictChecker(data_root).check_wms(wms_source, messages)
    assert sum("GetCapabilities" in url for url in calls) == 2
    assert not any("GetCapabilities" in m.message for m in messages)
    assert sum("actual image request succeeded" in m.message for m in messages) == 5
