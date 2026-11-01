"""Historical catalogue mistakes must fail offline checks before reaching editors."""

import copy
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from shapely.geometry import box, mapping

from eli.check import run
from eli.common import JSON
from eli.consistency import baseline_allows, best_overlaps, metadata_errors, source_fingerprint
from eli.libeli.geometry import validate_polygon_coordinates

HISTORY = json.loads((Path(__file__).parent / "data/regressions/3093.json").read_text())

# A deliberately small test schema exercises the validator and HTTP plumbing.
# CI checks the real generated corpus against the XSD fetched from JOSM.
TEST_SCHEMA = b"""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
    targetNamespace="http://josm.openstreetmap.de/maps-1.0" elementFormDefault="qualified">
    <xs:element name="imagery"><xs:complexType><xs:sequence>
      <xs:element name="zoom" minOccurs="0" type="xs:decimal"/>
    </xs:sequence></xs:complexType></xs:element>
</xs:schema>"""


@pytest.mark.parametrize("case", HISTORY["dates"], ids=lambda case: case["id"])
def test_historical_reversed_dates(
    case: JSON, data_root: Path, source: Path, feature: JSON, caplog: pytest.LogCaptureFixture
) -> None:
    feature["properties"].update(case["before"])
    source.write_text(json.dumps(feature))
    assert run([source], data_root) == 1
    assert "start_date is after end_date" in caplog.text
    feature["properties"].update(case["after"])
    source.write_text(json.dumps(feature))
    assert run([source], data_root) == 0


@pytest.mark.parametrize(
    "start,end,valid",
    [
        ("2024-02-29", "2024-02-29", True),
        ("2023-02-29", "2024", False),
        ("2020-11-31", "2021", False),
        ("0000", "2024", False),
        ("2024-13", "2025", False),
        ("2024-06", "2024", True),
        ("2024", "2024-01", True),
        ("2024-06-30", "2024-06", True),
        ("2025", "2024", False),
        (None, "2024", True),
        ("2024", None, True),
    ],
)
# Fixtures and the three date-case parameters describe independent dimensions.
# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def test_partial_and_calendar_dates(
    data_root: Path, source: Path, feature: JSON, start: str | None, end: str | None, valid: bool
) -> None:
    for key, value in (("start_date", start), ("end_date", end)):
        if value is not None:
            feature["properties"][key] = value
    assert bool(metadata_errors(feature, source, data_root)) is not valid


def test_zoom_defaults_and_explicit_bounds(data_root: Path, source: Path, feature: JSON) -> None:
    feature["properties"].update(min_zoom=21, max_zoom=20)
    assert "min_zoom is greater than max_zoom" in metadata_errors(feature, source, data_root)
    del feature["properties"]["max_zoom"]
    assert "min_zoom is greater than max_zoom" in metadata_errors(feature, source, data_root)
    feature["properties"]["max_zoom"] = 21
    assert not metadata_errors(feature, source, data_root)


def test_bulgarian_source_filed_under_belarus(data_root: Path, feature: JSON) -> None:
    feature["properties"]["country_code"] = "BG"
    filename = HISTORY["country"]["filename"]
    assert metadata_errors(feature, data_root / "sources/europe/by" / filename, data_root) == [
        "country_code BG disagrees with directory by"
    ]
    assert not metadata_errors(feature, data_root / "sources/europe/bg" / filename, data_root)
    feature["properties"]["country_code"] = "ZZ"
    assert not metadata_errors(feature, data_root / "sources/europe/by" / filename, data_root)
    feature["properties"]["country_code"] = "US"
    assert not metadata_errors(feature, data_root / "sources/north-america/pr/x.geojson", data_root)


def test_itu_missing_query_delimiter(data_root: Path, source: Path, feature: JSON) -> None:
    feature["properties"].update(type="wms", available_projections=["EPSG:3857"])
    for version, expected in (("before", 1), ("after", 0)):
        feature["properties"]["url"] = HISTORY["itu"][version]
        source.write_text(json.dumps(feature))
        assert run([source], data_root) == expected


def test_conflicting_query_and_fixed_projection(
    data_root: Path, source: Path, feature: JSON
) -> None:
    feature["properties"].update(
        type="wms", available_projections=["EPSG:3857", "EPSG:4326"], url=HISTORY["itu"]["after"]
    )
    feature["properties"]["url"] += "&crs=EPSG:3857"
    assert any("Conflicting values" in e for e in metadata_errors(feature, source, data_root))
    feature["properties"]["url"] = HISTORY["itu"]["after"].replace("{proj}", "EPSG:3857")
    assert any("fixes the CRS" in e for e in metadata_errors(feature, source, data_root))
    feature["properties"]["url"] = HISTORY["itu"]["after"] + "&foo={proj}"
    assert not metadata_errors(feature, source, data_root)


def test_historical_arcgis_dummy_projection(data_root: Path, source: Path, feature: JSON) -> None:
    feature["properties"].update(
        type="wms", available_projections=["EPSG:3857", "EPSG:4326"], url=HISTORY["arcgis"]["url"]
    )
    assert any("fixes the CRS" in e for e in metadata_errors(feature, source, data_root))
    feature["properties"]["available_projections"] = ["EPSG:3857"]
    assert not metadata_errors(feature, source, data_root)


def best_feature(feature: JSON, identifier: str, bounds: tuple[float, float, float, float]) -> JSON:
    result = copy.deepcopy(feature)
    result["properties"].update(id=identifier, best=True)
    result["geometry"] = mapping(box(*bounds))
    return result


def test_best_overlap_uses_smaller_footprint_and_filters_slivers(feature: JSON) -> None:
    large = best_feature(feature, "large", (0, 0, 10, 10))
    small = best_feature(feature, "small", (1, 1, 2, 2))
    overlaps = best_overlaps([small, large])
    assert len(overlaps) == 1
    assert overlaps[0][:2] == ("large", "small")
    assert overlaps[0][3] == pytest.approx(1)
    assert not best_overlaps([large, best_feature(feature, "border", (10, 0, 11, 1))])
    assert not best_overlaps([large, best_feature(feature, "sliver", (9.99, 0, 11, 1))])
    assert not best_overlaps([large, best_feature(feature, "tiny", (1, 1, 1.001, 1.001))])
    small["properties"]["best"] = False
    assert not best_overlaps([large, small])


def test_best_overlap_is_an_offline_error(
    data_root: Path, source: Path, feature: JSON, caplog: pytest.LogCaptureFixture
) -> None:
    first = best_feature(feature, "first", (1, 1, 2, 2))
    second = best_feature(feature, "second", (1, 1, 2, 2))
    source.write_text(json.dumps(first))
    other = source.with_name("other.geojson")
    other.write_text(json.dumps(second))
    assert run([source, other], data_root) == 1
    assert "Significant best overlap" in caplog.text
    second["geometry"] = mapping(box(2, 1, 3, 2))
    other.write_text(json.dumps(second))
    assert run([source, other], data_root) == 0


def test_existing_best_overlap_cannot_be_enlarged(
    data_root: Path, source: Path, feature: JSON
) -> None:
    first = best_feature(feature, "first", (1, 1, 3, 3))
    second = best_feature(feature, "second", (2, 1, 4, 3))
    source.write_text(json.dumps(first))
    other = source.with_name("other.geojson")
    other.write_text(json.dumps(second))
    baseline = {
        "version": 1,
        "failures": {
            "Significant best overlap: first / second": {
                s["properties"]["id"]: source_fingerprint(s) for s in (first, second)
            }
        },
    }
    (data_root / "validation-baseline.json").write_text(json.dumps(baseline))
    assert run([source, other], data_root) == 0
    second["geometry"] = mapping(box(1, 1, 4, 3))
    other.write_text(json.dumps(second))
    assert run([source, other], data_root) == 1
    second["properties"]["best"] = False
    other.write_text(json.dumps(second))
    assert run([source, other], data_root) == 1
    (data_root / "validation-baseline.json").write_text('{"version":1,"failures":{}}')
    assert run([source, other], data_root) == 0


def test_stale_metadata_baseline_requires_cleanup(
    data_root: Path, source: Path, feature: JSON, caplog: pytest.LogCaptureFixture
) -> None:
    feature["properties"].update(start_date="2025", end_date="2024")
    message = "test-layer: start_date is after end_date"
    baseline = {"version": 1, "failures": {message: {"test-layer": source_fingerprint(feature)}}}
    (data_root / "validation-baseline.json").write_text(json.dumps(baseline))
    source.write_text(json.dumps(feature))
    assert run([source], data_root) == 0
    feature["properties"]["end_date"] = "2025"
    source.write_text(json.dumps(feature))
    assert run([source], data_root) == 1
    assert "Stale validation baseline entry" in caplog.text
    (data_root / "validation-baseline.json").unlink()
    assert run([source], data_root) == 0


def test_partial_selection_does_not_retire_unchecked_entries(
    data_root: Path, source: Path, feature: JSON, caplog: pytest.LogCaptureFixture
) -> None:
    unrelated = copy.deepcopy(feature)
    unrelated["properties"]["id"] = "unrelated"
    other = source.with_name("unrelated.geojson")
    other.write_text(json.dumps(unrelated))
    baseline = {
        "version": 1,
        "failures": {
            "unrelated: Missing category": {"unrelated": source_fingerprint(unrelated)},
            "Significant best overlap: test-layer / unrelated": {
                s["properties"]["id"]: source_fingerprint(s) for s in (feature, unrelated)
            },
        },
    }
    (data_root / "validation-baseline.json").write_text(json.dumps(baseline))
    assert run([source], data_root) == 0
    assert "Stale validation baseline entry" not in caplog.text
    # Once the whole corpus is assessed, both resolved entries must be removed.
    assert run([source, other], data_root) == 1
    other.unlink()
    caplog.clear()
    assert run([source], data_root) == 1
    assert "Stale validation baseline entry" in caplog.text


def test_baseline_only_accepts_unchanged_sources(feature: JSON) -> None:
    baseline = {"failures": {"problem": {feature["properties"]["id"]: source_fingerprint(feature)}}}
    assert baseline_allows(baseline, "problem", [feature])
    assert not baseline_allows(baseline, "another problem", [feature])
    feature["properties"]["start_date"] = "2025"
    assert not baseline_allows(baseline, "problem", [feature])


def test_historical_zug_duplicate_vertices() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        validate_polygon_coordinates(HISTORY["duplicate_geometry"]["before"])
    validate_polygon_coordinates(HISTORY["duplicate_geometry"]["after"])


@pytest.mark.parametrize("case", HISTORY["tms"])
def test_historical_tms_projection_lists(
    data_root: Path, source: Path, feature: JSON, caplog: pytest.LogCaptureFixture, case: JSON
) -> None:
    feature["properties"]["available_projections"] = case["projections"]
    source.write_text(json.dumps(feature))
    # Legacy projection lists remain warnings, as agreed in the projection lint policy.
    with pytest.warns(UserWarning, match="Senseless available_projections"):
        assert run([source], data_root) == 0
    assert "available_projections only makes sense" in caplog.text
    del feature["properties"]["available_projections"]
    caplog.clear()
    source.write_text(json.dumps(feature))
    assert run([source], data_root) == 0
    assert "available_projections only makes sense" not in caplog.text


def test_historical_missing_category(data_root: Path, source: Path, feature: JSON) -> None:
    case = HISTORY["missing_categories"][0]
    del feature["properties"]["category"]
    source.write_text(json.dumps(feature))
    # JSON Schema historically permits this; source validation must reject it.
    assert run([source], data_root) == 1
    feature["properties"]["category"] = case["category"]
    source.write_text(json.dumps(feature))
    assert run([source], data_root) == 0


def test_published_schema_cli(
    data_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from eli.cli import main  # pylint: disable=import-outside-toplevel

    build = data_root / "build"
    build.mkdir()
    (build / "imagery.xml").write_text('<imagery xmlns="http://josm.openstreetmap.de/maps-1.0"/>')
    fetch = Mock(return_value=Mock(content=TEST_SCHEMA))
    monkeypatch.setattr("eli.common.request_get", fetch)
    assert main(["--root", str(data_root), "validate-josm"]) == 0
    fetch.assert_called_once_with("https://josm.openstreetmap.de/maps-1.0")
    assert "passes JOSM" in capsys.readouterr().out


@pytest.mark.parametrize("child", ["<unknown/>", "<zoom>1e-07</zoom>"])
def test_downloaded_schema_rejects_invalid_xml(child: str) -> None:
    from eli.artifacts import validate_josm_schema

    xml = f'<imagery xmlns="http://josm.openstreetmap.de/maps-1.0">{child}</imagery>'.encode()
    with pytest.raises(ValueError, match="JOSM schema"):
        validate_josm_schema(xml, TEST_SCHEMA)
