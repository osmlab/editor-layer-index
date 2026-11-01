"""Exercise CLI behavior, maintenance commands, and publication failure handling."""

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from eli import cli
from eli.artifacts import OUTPUTS
from eli.build import assemble_site, build
from eli.check import run
from eli.common import JSON, discover, request_get
from eli.exporters import LegacyOptions, legacy_text, xml_bytes
from eli.strict import StrictChecker
from eli.sync_wms import WMSSync


def test_discovery_and_check(data_root: Path, source: Path) -> None:
    assert discover(["sources", str(source)], data_root) == [source]
    assert cli.main(["--root", str(data_root), "check"]) == 0


def test_invalid_input_and_cli_errors(data_root: Path, source: Path) -> None:
    source.write_text("{broken")
    assert cli.main(["--root", str(data_root), "check"]) == 1
    source.write_text('{"type":"Feature","type":"Feature"}')
    assert cli.main(["--root", str(data_root), "check"]) == 1
    assert cli.main(["--root", str(data_root), "check", "missing.geojson"]) == 1
    with pytest.raises(SystemExit) as error:
        cli.main(["unknown-command"])
    assert error.value.code == 2


def test_duplicate_ids_across_directories(data_root: Path, source: Path) -> None:
    other = data_root / "sources/other"
    other.mkdir()
    shutil.copy2(source, other / "duplicate.geojson")
    assert run(discover([], data_root), data_root) == 1


def test_empty_sources_fail(data_root: Path) -> None:
    assert cli.main(["--root", str(data_root), "check"]) == 1
    with pytest.raises(ValueError, match="No sources"):
        build(data_root, data_root / "build")


@pytest.mark.usefixtures("source")
def test_root_independent_of_cwd(data_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(data_root.parent)
    assert cli.main(["--root", str(data_root), "check"]) == 0


def test_strict_success_errors_and_exceptions(
    data_root: Path, source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = Mock(status_code=200)
    monkeypatch.setattr(StrictChecker, "get_response", Mock(return_value=response))
    monkeypatch.setattr(StrictChecker, "check_tms", Mock(return_value=None))
    checker = StrictChecker(data_root)
    assert checker.run([source], data_root) == 0
    monkeypatch.setattr(
        StrictChecker, "check_tms", Mock(side_effect=RuntimeError("unexpected failure"))
    )
    assert checker.run([source], data_root) == 1
    monkeypatch.setattr(StrictChecker, "check_tms", Mock(return_value=None))
    monkeypatch.setattr(
        StrictChecker, "get_response", Mock(side_effect=requests.Timeout("timed out"))
    )
    assert checker.run([source], data_root) == 1


def test_request_timeout_and_tls_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    get = Mock()
    monkeypatch.setattr(requests, "get", get)
    request_get("https://example.org", verify=False)
    get.assert_called_once_with("https://example.org", timeout=(5, 20), verify=False)


def test_context_state_is_not_shared() -> None:
    first, second = WMSSync(), WMSSync()
    first.ignored_sources["x"] = "failure"
    assert not second.ignored_sources
    assert first.response_cache is not second.response_cache
    assert first.domain_lock is not second.domain_lock


def test_build_reproducible_preserves_sources(
    data_root: Path, source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = source.read_bytes()
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "0")
    out = data_root / "build"
    build(data_root, out)
    first = {name: (out / name).read_bytes() for name in OUTPUTS}
    build(data_root, out)
    assert first == {name: (out / name).read_bytes() for name in OUTPUTS}
    assert json.loads(first["imagery.geojson"])["meta"]["generated"] == "1970-01-01 00:00:00"
    assert source.read_bytes() == before


@pytest.mark.usefixtures("source")
def test_failed_generation_keeps_previous_outputs(
    data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = data_root / "build"
    build(data_root, out)
    previous = {name: (out / name).read_bytes() for name in OUTPUTS}
    monkeypatch.setattr("eli.build.xml_bytes", Mock(side_effect=ValueError("conversion failed")))
    with pytest.raises(ValueError, match="conversion failed"):
        build(data_root, out)
    assert previous == {name: (out / name).read_bytes() for name in OUTPUTS}


@pytest.mark.usefixtures("source")
def test_failed_publish_rolls_back_outputs(
    data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    out = data_root / "build"
    build(data_root, out)
    previous = {name: (out / name).read_bytes() for name in OUTPUTS}
    real_replace = os.replace
    calls = 0

    def replace(a: Path, b: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("disk error")
        return real_replace(a, b)

    monkeypatch.setattr("eli.build.os.replace", replace)
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "0")
    with pytest.raises(OSError, match="disk error"):
        build(data_root, out)
    assert previous == {name: (out / name).read_bytes() for name in OUTPUTS}


@pytest.mark.usefixtures("source")
def test_site_preserves_public_paths_and_removes_stale_files(data_root: Path) -> None:
    generated = data_root / "build"
    build(data_root, generated)
    output = generated / "site"
    output.mkdir()
    (output / "obsolete").touch()
    assemble_site(data_root, generated, output)
    for name in (
        *OUTPUTS,
        "index.html",
        "site/site.js",
        "i18n/fr.yaml",
        "sources/europe/de/icon.png",
        "sources/europe/de/license.pdf",
        "package.json",
    ):
        assert (output / name).is_file()
    assert not (output / "obsolete").exists()
    for name in OUTPUTS:
        assert (output / name).read_bytes() == (generated / name).read_bytes()


@pytest.mark.parametrize("name", ["", "sources/output", "site", "i18n", "src", ".git"])
@pytest.mark.usefixtures("source")
def test_build_rejects_input_directories(data_root: Path, name: str) -> None:
    with pytest.raises(ValueError):
        build(data_root, data_root / name)


def test_legacy_conversion_flags_and_xml_limits(feature: JSON) -> None:
    converted = json.loads(legacy_text([feature], LegacyOptions(True, False, True)))[0]
    assert "polygon" not in converted["extent"]
    assert converted["extent"]["bbox"] == {"min_lon": 0, "max_lon": 1, "min_lat": 0, "max_lat": 1}
    wms = copy.deepcopy(feature)
    wms["properties"]["type"] = "wms"
    # Preserve the historical placeholder for excluded WMS entries.
    assert json.loads(legacy_text([wms], LegacyOptions(tms_only=True))) == [{}]
    feature["properties"]["max_zoom"] = 30
    assert b"<max-zoom>24</max-zoom>" in xml_bytes([feature])


def test_imports_do_not_run_commands_or_open_network(data_root: Path) -> None:
    # Import every module in a fresh process with networking and process execution prohibited.
    script = """
import importlib, pkgutil, subprocess, requests, aiohttp
import eli
from unittest.mock import Mock
no_process = Mock(side_effect=AssertionError('process during import'))
subprocess.run = subprocess.call = subprocess.check_output = no_process
requests.get = aiohttp.ClientSession = Mock(side_effect=AssertionError('network during import'))
for info in pkgutil.walk_packages(eli.__path__, eli.__name__ + '.'):
    importlib.import_module(info.name)
"""
    before = sorted(p.relative_to(data_root) for p in data_root.rglob("*"))
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=data_root, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert before == sorted(p.relative_to(data_root) for p in data_root.rglob("*"))


def test_icon_extraction_is_explicit_and_relative(
    data_root: Path, source: Path, feature: JSON
) -> None:
    feature["properties"]["icon"] = "data:image/png;base64,aWNvbg=="
    source.write_text(json.dumps(feature))
    assert cli.main(["--root", str(data_root), "unembed-icons"]) == 0
    assert source.with_suffix(".png").read_bytes() == b"icon"
    assert json.loads(source.read_text())["properties"]["icon"].startswith(
        "https://osmlab.github.io/editor-layer-index/sources/"
    )


def test_strict_forwards_custom_headers(data_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    request = Mock(return_value=Mock(status_code=200, text="UTF-8", apparent_encoding="utf-8"))
    monkeypatch.setattr(StrictChecker, "get_response", request)
    checker = StrictChecker(data_root)
    headers = {"X-Imagery-Key": "test-header"}
    checker.test_url("https://example.org", headers)
    assert request.call_args.kwargs["headers"] == headers
    checker.get_text_encoded("https://example.org", headers)
    assert request.call_args.kwargs["headers"] == headers


def test_josm_import_multiple_entries(tmp_path: Path) -> None:
    from eli.import_josm import run as import_josm

    document = tmp_path / "imagery.xml"
    entries = "".join(
        f"<entry><id>{name}</id><name>{name}</name><type>tms</type>"
        "<url>https://example.org/{zoom}/{x}/{y}</url><country-code>DE</country-code></entry>"
        for name in ("one", "two")
    )
    document.write_text("<imagery>" + entries + "</imagery>")
    target = tmp_path / "imported"
    import_josm(str(document), str(target))
    assert {p.name for p in (target / "de").glob("*.geojson")} == {"one.geojson", "two.geojson"}


def test_category_sync_copies_only_changes(
    data_root: Path, source: Path, feature: JSON, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eli.sync_categories import run as sync_categories

    del feature["properties"]["category"]
    source.write_text(json.dumps(feature))
    before = source.read_bytes()
    response = Mock(
        text=(
            "<imagery><entry><id>test-layer</id><country-code>DE</country"
            "-code><category>photo</category></entry></imagery>"
        )
    )
    monkeypatch.setattr("eli.sync_categories.request_get", Mock(return_value=response))
    target = tmp_path / "categories"
    sync_categories(str(data_root / "sources"), str(target))
    output = target / source.relative_to(data_root / "sources")
    assert json.loads(output.read_text())["properties"]["category"] == "photo"
    assert source.read_bytes() == before


def test_async_sync_failure_returns_error(source: Path) -> None:
    import asyncio

    syncer = WMSSync()
    source.write_text("{invalid")
    asyncio.run(syncer.start_processing([source]))
    assert syncer.failures == 1


def test_geojsonify_maintenance_write(data_root: Path, source: Path) -> None:
    legacy = {
        "id": "legacy",
        "name": "Legacy",
        "type": "tms",
        "url": "https://example.org/{zoom}/{x}/{y}",
        "extent": {"bbox": {"min_lon": 0, "min_lat": 0, "max_lon": 1, "max_lat": 1}},
    }
    source.write_text(json.dumps(legacy))
    assert cli.main(["--root", str(data_root), "geojsonify", str(source)]) == 0
    result = json.loads(source.read_text())
    assert result["type"] == "Feature"
    assert result["properties"]["id"] == "legacy"
    assert result["geometry"]["coordinates"][0][0] == result["geometry"]["coordinates"][0][-1]


@pytest.mark.usefixtures("source")
def test_translation_cli_arguments(data_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    call = Mock(return_value=0)
    monkeypatch.setattr("eli.cli.shutil.which", Mock(return_value="/usr/local/bin/tx"))
    monkeypatch.setattr("eli.cli.subprocess.call", call)
    assert cli.main(["--root", str(data_root), "translations", "push"]) == 0
    call.assert_called_with(["/usr/local/bin/tx", "push", "-s"], cwd=data_root)
    assert (data_root / "i18n/en.yaml").is_file()
    assert cli.main(["--root", str(data_root), "translations", "pull"]) == 0
    call.assert_called_with(
        ["/usr/local/bin/tx", "pull", "-a", "--use-git-timestamps"], cwd=data_root
    )


def test_minzoom_url_generation_without_network_or_plots(tmp_path: Path) -> None:

    from eli.minzoom import MinZoom

    helper = MinZoom(str(tmp_path / "plots"))
    source = {"properties": {"url": "https://example.org/{zoom}/{x}/{y}.png"}}
    import mercantile

    tile = mercantile.Tile(1, 2, 3)
    assert helper.tms_url(tile, source) == "https://example.org/3/1/2.png"
    assert helper.wms_version_from_url("https://example.org?VERSION=1.3.0") == "1.3.0"


def test_invalid_wms_url_raises_validation_error() -> None:
    import validators

    from eli.libeli.wmshelper import WMSURL

    with pytest.raises(validators.ValidationError):
        WMSURL("not-a-url").is_valid_getmap_url()


def test_wms_retry_uses_response_instance_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    from unittest.mock import AsyncMock

    delay = AsyncMock()
    monkeypatch.setattr("eli.sync_wms.asyncio.sleep", delay)
    response = Mock(status=200)
    response.text = AsyncMock(return_value="<xml/>")
    response.read = AsyncMock(return_value=b"<xml/>")
    context = Mock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = Mock()
    session.request.side_effect = [TimeoutError("first request"), context]
    syncer = WMSSync()

    async def check_cached_response() -> None:
        first = await syncer.get_url("https://example.org/wms", session)
        second = await syncer.get_url("https://example.org/wms", session)
        assert first is second
        assert second.exception is None
        assert second.status == 200

    asyncio.run(check_cached_response())
    assert session.request.call_count == 2
    delay.assert_awaited_once_with(15)


def test_strict_null_local_geometry_fails_cleanly(
    data_root: Path, source: Path, feature: JSON, monkeypatch: pytest.MonkeyPatch
) -> None:
    feature["geometry"] = None
    source.write_text(json.dumps(feature))
    monkeypatch.setattr(StrictChecker, "get_response", Mock(return_value=Mock(status_code=200)))
    monkeypatch.setattr(StrictChecker, "check_tms", Mock(return_value=None))
    assert StrictChecker(data_root).run([source], data_root) == 1


def test_image_similarity_returns_builtin_boolean() -> None:
    import imagehash
    import numpy as np

    first = imagehash.ImageHash(np.zeros((8, 8), dtype=bool))
    second = imagehash.ImageHash(np.zeros((8, 8), dtype=bool))
    assert WMSSync().image_similar(first, second) is True


def test_async_exception_handler_preserves_context() -> None:
    from asyncio.events import AbstractEventLoop

    syncer = WMSSync()
    loop = Mock(spec=AbstractEventLoop)
    context = {"message": "Unexpected task failure", "exception": RuntimeError("test failure")}
    syncer.handle_exception(loop, context)
    assert syncer.failures == 1
    loop.default_exception_handler.assert_called_once_with(context)
