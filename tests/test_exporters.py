"""Compare compatible exports with the original golden files."""

import json
from pathlib import Path

import pytest

from eli.common import JSON
from eli.exporters import LegacyOptions, geojson_text, legacy_text, translation_text, xml_bytes

DATA = Path(__file__).parent / "data/exports"


def inputs(rounded: bool = True) -> list[JSON]:
    with (DATA / "features.json").open(encoding="utf-8") as stream:
        result: list[JSON] = json.load(
            stream, parse_float=(lambda x: round(float(x), 5)) if rounded else float
        )
    return result


def test_original_exporter_golden_files() -> None:
    assert (
        geojson_text(inputs(), "1970-01-01 00:00:00").encode()
        == (DATA / "imagery.geojson").read_bytes()
    )
    assert legacy_text(inputs()).encode() == (DATA / "imagery.json").read_bytes()
    assert xml_bytes(inputs()) == (DATA / "imagery.xml").read_bytes()
    assert translation_text(inputs(False)).encode() == (DATA / "en.yaml").read_bytes()


@pytest.mark.parametrize(
    "options, name",
    [
        (LegacyOptions(True), "bbox.json"),
        (LegacyOptions(True, False, True), "bbox-only.json"),
        (LegacyOptions(tms_only=True), "tms-only.json"),
    ],
)
def test_original_conversion_flags(options: LegacyOptions, name: str) -> None:
    assert legacy_text(inputs(), options).encode() == (DATA / name).read_bytes()


def test_xml_polygon_limits(feature: JSON) -> None:
    ring = [[i / 1000, i / 1000] for i in range(1000)]
    ring.append(ring[0])
    feature["geometry"]["coordinates"] = [ring]
    result = xml_bytes([feature])
    assert b"<bounds " in result
    assert b"<shape>" not in result
    feature["geometry"] = {
        "type": "MultiPolygon",
        "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]] * 101,
    }
    result = xml_bytes([feature])
    assert b"<bounds " in result
    assert b"<shape>" not in result
