"""Offline checks for the requests made by strict PR validation."""

import io
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from PIL import Image
from shapely.geometry import box, mapping


@pytest.fixture
def checker(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "argv", ["strict_check.py", "unused.txt"])
    namespace = runpy.run_path(str(root / "scripts/strict_check.py"))
    yield SimpleNamespace(**namespace)
    namespace["logger"].removeHandler(namespace["handler"])


@pytest.fixture
def source():
    return {
        "properties": {
            "url": "https://example.com/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap"
            "&LAYERS=photo,overlay&STYLES=default,lines&TIME=2026&token=keep-me&FORMAT=image/png"
            "&CRS={proj}&BBOX={bbox}&WIDTH={width}&HEIGHT={height}",
            "available_projections": ["EPSG:3857", "EPSG:4326", "CRS:84", "EPSG:4026", "EPSG:900913"],
            "custom-http-headers": {"header-name": "X-Test", "header-value": "present"},
        },
        "geometry": mapping(box(28, 46, 29, 47)),
    }


def image_response(color="green", size=(256, 256), varied=True):
    image = Image.new("RGBA", size, color)
    if varied:
        image.putpixel((0, 0), (255, 0, 0, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    response = requests.Response()
    response.status_code = 200
    response._content = buffer.getvalue()
    return response


def test_all_configured_crs_preserve_request(checker, source, monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append((parse_qs(urlparse(url).query), kwargs))
        return image_response()

    monkeypatch.setattr(requests, "get", get)
    # 3857 is advertised by only one of the two requested layers.
    capabilities = SimpleNamespace(
        layers={
            "photo": SimpleNamespace(crs={"EPSG:3857", "EPSG:4326"}),
            "overlay": SimpleNamespace(crs={"EPSG:4326"}),
        }
    )
    messages = []
    checker.check_wms_images(source, messages, capabilities)
    assert len(calls) == len(source["properties"]["available_projections"])
    assert {args["CRS"][0] for args, _ in calls} == set(source["properties"]["available_projections"])
    for args, kwargs in calls:
        assert args["TIME"] == ["2026"]
        assert args["token"] == ["keep-me"]
        assert args["STYLES"] == ["default,lines"]
        assert args["LAYERS"] == ["photo,overlay"]
        assert kwargs["headers"]["X-Test"] == "present"
        assert kwargs["timeout"] == 30
    assert all(message.level == checker.MessageLevel.INFO for message in messages)
    assert any("'EPSG:3857' (not advertised" in message.message for message in messages)
    assert any("'EPSG:4326' (advertised)" in message.message for message in messages)


@pytest.mark.parametrize("version, parameter", [("1.3.0", "CRS"), ("1.1.1", "SRS")])
def test_axis_order(checker, source, monkeypatch, version, parameter):
    source["properties"]["url"] = (
        source["properties"]["url"].replace("1.3.0", version).replace("CRS=", parameter + "=")
    )
    source["properties"]["available_projections"] = ["EPSG:4326", "CRS:84"]
    calls = {}

    def get(url, **kwargs):
        args = parse_qs(urlparse(url).query)
        calls[args[parameter][0]] = [float(value) for value in args["BBOX"][0].split(",")]
        return image_response()

    monkeypatch.setattr(requests, "get", get)
    checker.check_wms_images(source, [], None)
    crs84 = calls["CRS:84"]
    assert calls["EPSG:4326"] == (crs84 if version == "1.1.1" else [crs84[1], crs84[0], crs84[3], crs84[2]])
    assert box(28, 46, 29, 47).contains(box(*crs84))


@pytest.mark.parametrize("failure", ["http", "exception_xml", "corrupt", "size", "timeout", "projection"])
def test_failure_does_not_skip_other_crs(checker, source, monkeypatch, failure):
    source["properties"]["available_projections"] = ["EPSG:3857", "EPSG:4326"]
    if failure == "projection":
        source["properties"]["available_projections"][0] = "EPSG:0"
    calls = []

    def get(url, **kwargs):
        args = parse_qs(urlparse(url).query)
        calls.append(args)
        response = image_response()
        if args["CRS"] == ["EPSG:3857"]:
            if failure == "http":
                response.status_code = 503
            elif failure == "exception_xml":
                response._content = (
                    b"<ServiceExceptionReport><ServiceException>InvalidCRS</ServiceException></ServiceExceptionReport>"
                )
            elif failure == "corrupt":
                response._content = b"\x89PNG\r\n\x1a\ncorrupt"
            elif failure == "size":
                response = image_response(size=(32, 32))
            elif failure == "timeout":
                raise requests.Timeout("timed out")
        return response

    monkeypatch.setattr(requests, "get", get)
    messages = []
    checker.check_wms_images(source, messages, None)
    assert any(message.level == checker.MessageLevel.ERROR for message in messages)
    assert any("'EPSG:4326'" in message.message and message.level == checker.MessageLevel.INFO for message in messages)


@pytest.mark.parametrize("color", [(0, 0, 0, 0), "white"])
def test_empty_image_is_inconclusive(checker, source, monkeypatch, color):
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: image_response(color=color, varied=False))
    messages = []
    checker.check_wms_images(source, messages, None)
    assert len(messages) == 5
    assert all(message.level == checker.MessageLevel.WARNING for message in messages)
    assert all("imagery could not be confirmed" in message.message for message in messages)


def test_capabilities_bounds_when_no_coverage(checker, source, monkeypatch):
    source["geometry"] = None
    bounds = checker.eliutils.BoundingBox(west=28, south=46, east=29, north=47)
    capabilities = SimpleNamespace(
        layers={name: SimpleNamespace(crs=set(), bbox=bounds) for name in ["photo", "overlay"]}
    )
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: image_response())
    messages = []
    checker.check_wms_images(source, messages, capabilities)
    assert len(messages) == 5
    assert all("28.500000,46.500000" in message.message for message in messages)


def test_check_wms_invokes_image_checks(checker, source, monkeypatch):
    xml = (Path("scripts/tests/data/wms/capabilities_1_3_0.xml")).read_text()
    source["properties"]["url"] = source["properties"]["url"].replace("photo,overlay", "ROADS_1M")
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        if "GetCapabilities" in url:
            response = requests.Response()
            response.status_code = 200
            response._content = xml.encode()
            response.encoding = "utf-8"
            return response
        return image_response()

    monkeypatch.setattr(requests, "get", get)
    checker.check_wms(source, [])
    assert len([url for url in calls if "GetMap" in url]) == 5


def test_capabilities_failure_still_probes_configured_crs(checker, source, monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        if "GetCapabilities" in url:
            raise requests.ConnectionError("Capabilities unavailable")
        return image_response()

    monkeypatch.setattr(requests, "get", get)
    messages = []
    checker.check_wms(source, messages)
    assert len([url for url in calls if "GetMap" in url]) == 5
    assert len([message for message in messages if "returned a decoded" in message.message]) == 5


@pytest.mark.parametrize(
    "status, content_type, body, expected",
    [
        (499, "application/json", b'{"error":{"code":499,"message":"Token Required","details":[]}}', "Token Required"),
        (
            200,
            "image/jpeg",
            b'<ServiceExceptionReport><ServiceException code="InvalidSRS">Unsupported CRS</ServiceException></ServiceExceptionReport>',
            "InvalidSRS Unsupported CRS",
        ),
        (
            200,
            "text/xml",
            b'<ows:ExceptionReport xmlns:ows="urn:ows"><ows:Exception exceptionCode="LayerNotDefined" locator="LAYERS"><ows:ExceptionText>Unknown layer ortho_s_2018</ows:ExceptionText></ows:Exception></ows:ExceptionReport>',
            "LayerNotDefined (LAYERS) Unknown layer ortho_s_2018",
        ),
        (
            405,
            "text/html",
            b"<html><head><title>Method Not Allowed</title></head><body>GET rejected</body></html>",
            "Method Not Allowed GET rejected",
        ),
    ],
)
def test_server_error_is_reported(checker, source, monkeypatch, status, content_type, body, expected):
    source["properties"]["available_projections"] = ["EPSG:3857"]
    response = requests.Response()
    response.status_code = status
    response.headers["Content-Type"] = content_type
    response._content = body
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response)
    messages = []
    checker.check_wms_images(source, messages, None)
    message = messages[0].message
    assert messages[0].level == checker.MessageLevel.ERROR
    assert expected in message
    assert f"HTTP {status}" in message
    assert content_type in message
    assert message.count("https://example.com/wms") == 1
    assert "BytesIO" not in message


def test_response_details_are_bounded_and_binary_is_not_dumped(checker):
    response = requests.Response()
    response.status_code = 500
    response.headers["Content-Type"] = "text/html"
    response._content = b"<html><script>hidden_script()</script><body>" + b"failure " * 1000 + b"</body></html>"
    details = checker.describe_response(response)
    assert len(details) < 600
    assert "hidden_script" not in details
    assert details.endswith("…")
    response.headers["Content-Type"] = "image/png"
    response._content = b"\x89PNG\x00\x00binary secret"
    assert "binary secret" not in checker.describe_response(response)


def test_capabilities_http_errors_are_not_silent(checker, source, monkeypatch):
    def get(url, **kwargs):
        if "GetCapabilities" in url:
            response = requests.Response()
            response.status_code = 499
            response.headers["Content-Type"] = "application/json"
            response._content = b'{"error":{"code":499,"message":"Token Required"}}'
            return response
        return image_response()

    monkeypatch.setattr(requests, "get", get)
    messages = []
    checker.check_wms(source, messages)
    failures = [message for message in messages if "GetCapabilities" in message.message]
    assert len(failures) == 5
    assert all("HTTP 499" in message.message and "Token Required" in message.message for message in failures)
    assert len([message for message in messages if "returned a decoded" in message.message]) == 5


def test_capabilities_version_retry_recovers(checker, source, monkeypatch):
    xml = Path("scripts/tests/data/wms/capabilities_1_3_0.xml").read_bytes()
    source["properties"]["url"] = source["properties"]["url"].replace("photo,overlay", "ROADS_1M")
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        if "GetCapabilities" in url:
            response = requests.Response()
            response.status_code = 200 if "VERSION=1.3.0" in url else 500
            response._content = xml if response.status_code == 200 else b"unavailable"
            return response
        return image_response()

    monkeypatch.setattr(requests, "get", get)
    messages = []
    checker.check_wms(source, messages)
    assert len([url for url in calls if "GetCapabilities" in url]) == 2
    assert not any("GetCapabilities" in message.message for message in messages)


def test_logged_diagnostics_identify_source_once(checker, caplog):
    filename = "sources/europe/ch/example.geojson"
    messages = [
        checker.Message(checker.MessageLevel.ERROR, "CRS rejected"),
        checker.Message(checker.MessageLevel.WARNING, f"{filename}: license unavailable"),
    ]
    caplog.clear()
    checker.log_messages(filename, messages)
    assert len(caplog.records) == 2
    assert all(record.message.startswith(filename + ": ") for record in caplog.records)
    assert all(record.message.count(filename) == 1 for record in caplog.records)


def test_expected_connection_failure_has_no_traceback(checker, monkeypatch, caplog):
    def get(*args, **kwargs):
        raise requests.ConnectionError("Remote end closed connection without response")

    monkeypatch.setattr(requests, "get", get)
    caplog.clear()
    assert checker.test_url("https://example.com/privacy") == (False, -1)
    assert len(caplog.records) == 1
    assert "ConnectionError" in caplog.records[0].message
    assert "https://example.com/privacy" in caplog.records[0].message
    assert caplog.records[0].exc_info is None


def test_unexpected_checker_failure_is_fatal_and_names_source(checker, tmp_path):
    path = tmp_path / "broken.geojson"
    path.write_text("not JSON")
    result = subprocess.run([sys.executable, "scripts/strict_check.py", str(path)], capture_output=True, text=True)
    assert result.returncode == 1
    assert f"{path}: Unexpected checker failure" in result.stderr
