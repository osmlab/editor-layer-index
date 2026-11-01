"""Reject invalid or incomplete consumer artifacts before any output is replaced."""

import copy
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from shapely.geometry import shape

from eli.artifacts import OUTPUTS, validate_build
from eli.build import assemble_site, build
from eli.check import run
from eli.common import JSON, discover, load_json

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "mutation", ["category", "unknown-element", "invalid-zoom", "invalid-country"]
)
def test_josm_output_rejects_schema_regressions(feature: JSON, mutation: str) -> None:
    from eli.artifacts import _xml
    from eli.exporters import xml_bytes

    namespace = "{http://josm.openstreetmap.de/maps-1.0}"
    root = ET.fromstring(xml_bytes([feature]))
    entry = root[0]
    if mutation == "category":
        category = entry.find(namespace + "category")
        assert category is not None
        entry.remove(category)
    elif mutation == "unknown-element":
        ET.SubElement(entry, namespace + "unsupported-element")
    elif mutation == "invalid-zoom":
        zoom = entry.find(namespace + "max-zoom")
        assert zoom is not None
        zoom.text = "999"
    else:
        country = entry.find(namespace + "country-code")
        assert country is not None
        country.text = "ZZ"
    with pytest.raises(ValueError, match="imagery.xml"):
        _xml(ET.tostring(root), [feature])


def test_complete_repository_build(tmp_path: Path) -> None:
    """Exercise the real corpus and parse every format, including precise XML shapes."""
    generated = tmp_path / "generated"
    build(ROOT, generated)
    validate_build(ROOT, generated)
    features = json.loads((generated / "imagery.geojson").read_bytes())["features"]
    assert len(features) == len(discover([], ROOT))
    for feature in features:
        if feature["geometry"] is not None:
            assert shape(feature["geometry"]).is_valid, feature["properties"]["id"]


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "Polygon", "coordinates": [[[0, 0], [0.0000001, 0], [0, 0.0000001], [0, 0]]]},
        {
            "type": "Polygon",
            "coordinates": [
                [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]],
                [[0.5, 0.5], [0.500001, 0.5], [0.5, 0.500001], [0.5, 0.5]],
            ],
        },
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [0, 0],
                    [2, 0],
                    [2, 2],
                    [1.000001, 2],
                    [1.000001, 1],
                    [1, 1],
                    [1, 2],
                    [0, 2],
                    [0, 0],
                ]
            ],
        },
        {
            "type": "MultiPolygon",
            "coordinates": [
                [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                [[[1.000001, 0], [2, 0], [2, 1], [1.000001, 1], [1.000001, 0]]],
            ],
        },
    ],
)
def test_precise_geometry_survives_all_formats(
    data_root: Path, source: Path, feature: JSON, geometry: JSON
) -> None:
    feature["geometry"] = geometry
    source.write_text(json.dumps(feature))
    assert shape(geometry).is_valid
    assert not shape(load_json(source, rounded=True)["geometry"]).is_valid
    generated = data_root / "build"
    build(data_root, generated)
    validate_build(data_root, generated)
    exported = json.loads((generated / "imagery.geojson").read_bytes())["features"][0]
    assert exported["geometry"] == geometry
    namespace = "{http://josm.openstreetmap.de/maps-1.0}"
    document = ET.parse(generated / "imagery.xml")
    ring = document.find(f".//{namespace}shape")
    assert ring is not None
    expected = geometry["coordinates"][0]
    if geometry["type"] == "MultiPolygon":
        expected = expected[0]
    assert [[float(point.attrib[key]) for key in ("lon", "lat")] for point in ring] == expected


def test_invalid_xml_keeps_previous_build(data_root: Path, source: Path, feature: JSON) -> None:
    generated = data_root / "build"
    build(data_root, generated)
    before = {name: (generated / name).read_bytes() for name in OUTPUTS}
    feature["properties"]["name"] = "Invalid\u0001name"
    source.write_text(json.dumps(feature))
    assert run([source], data_root) == 0
    with pytest.raises(ValueError, match="imagery.xml"):
        build(data_root, generated)
    assert before == {name: (generated / name).read_bytes() for name in OUTPUTS}


@pytest.mark.usefixtures("source")
@pytest.mark.parametrize("name", OUTPUTS)
def test_missing_entry_rejected(data_root: Path, name: str) -> None:
    generated = data_root / "build"
    build(data_root, generated)
    path = generated / name
    if name == "imagery.xml":
        document = ET.parse(path)
        document.getroot().remove(document.getroot()[0])
        document.write(path)
    elif name == "i18n/en.yaml":
        path.write_text("en:\n  imagery: {}\n")
    else:
        document_json = json.loads(path.read_bytes())
        if name == "imagery.geojson":
            document_json["features"] = []
        else:
            document_json = []
        path.write_text(json.dumps(document_json))
    with pytest.raises(ValueError, match="IDs"):
        validate_build(data_root, generated)


@pytest.mark.usefixtures("source")
@pytest.mark.parametrize("name", OUTPUTS)
def test_incorrect_metadata_rejected(data_root: Path, name: str) -> None:
    generated = data_root / "build"
    build(data_root, generated)
    path = generated / name
    path.write_bytes(path.read_bytes().replace("Ünicode layer".encode(), b"Incorrect name"))
    with pytest.raises(ValueError, match="incorrect"):
        validate_build(data_root, generated)


@pytest.mark.usefixtures("source")
@pytest.mark.parametrize("name", ["imagery.geojson", "imagery.json", "imagery.xml"])
def test_duplicate_entry_rejected(data_root: Path, name: str) -> None:
    generated = data_root / "build"
    build(data_root, generated)
    path = generated / name
    if name == "imagery.xml":
        document = ET.parse(path)
        document.getroot().append(copy.deepcopy(document.getroot()[0]))
        document.write(path)
    else:
        document_json = json.loads(path.read_bytes())
        entries = document_json["features"] if name == "imagery.geojson" else document_json
        entries.append(copy.deepcopy(entries[0]))
        path.write_text(json.dumps(document_json))
    with pytest.raises(ValueError, match="IDs"):
        validate_build(data_root, generated)


@pytest.mark.usefixtures("source")
def test_changed_geometry_rejected(data_root: Path) -> None:
    generated = data_root / "build"
    build(data_root, generated)
    path = generated / "imagery.geojson"
    document = json.loads(path.read_bytes())
    document["features"][0]["geometry"] = None
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="changed geometry"):
        validate_build(data_root, generated)


@pytest.mark.usefixtures("source")
def test_changed_translation_structure_rejected(data_root: Path) -> None:
    generated = data_root / "build"
    build(data_root, generated)
    path = generated / "i18n/en.yaml"
    document = yaml.safe_load(path.read_bytes())
    document["en"]["imagery"]["test-layer"]["name"] = {"unexpected": "object"}
    path.write_text(yaml.safe_dump(document))
    with pytest.raises(ValueError, match="incorrect translations"):
        validate_build(data_root, generated)


@pytest.mark.usefixtures("source")
def test_invalid_existing_build_preserves_site(data_root: Path) -> None:
    generated = data_root / "build"
    build(data_root, generated)
    site = generated / "site"
    assemble_site(data_root, generated, site)
    before = {
        path.relative_to(site): path.read_bytes() for path in site.rglob("*") if path.is_file()
    }
    (generated / "imagery.xml").write_bytes(b"<broken")
    with pytest.raises(ValueError, match="imagery.xml"):
        assemble_site(data_root, generated, site)
    assert before == {
        path.relative_to(site): path.read_bytes() for path in site.rglob("*") if path.is_file()
    }


def test_broken_exporter_keeps_previous_build(
    data_root: Path, source: Path, feature: JSON, monkeypatch: pytest.MonkeyPatch
) -> None:
    generated = data_root / "build"
    build(data_root, generated)
    before = {name: (generated / name).read_bytes() for name in OUTPUTS}
    feature["geometry"]["coordinates"] = [[[0, 0], [0.000001, 0], [0, 0.000001], [0, 0]]]
    source.write_text(json.dumps(feature))
    monkeypatch.setattr(
        "eli.build.export_source", Mock(return_value=load_json(source, rounded=True))
    )
    with pytest.raises(
        ValueError, match="Invalid exported geometry|consecutive duplicate positions"
    ):
        build(data_root, generated)
    assert before == {name: (generated / name).read_bytes() for name in OUTPUTS}


@pytest.mark.usefixtures("source")
@pytest.mark.parametrize("change", ["bounds", "shape"])
def test_incorrect_xml_extent_rejected(data_root: Path, change: str) -> None:
    generated = data_root / "build"
    build(data_root, generated)
    path = generated / "imagery.xml"
    document = ET.parse(path)
    namespace = "{http://josm.openstreetmap.de/maps-1.0}"
    bounds = document.find(f".//{namespace}bounds")
    assert bounds is not None
    if change == "bounds":
        bounds.set("min-lon", "-180")
    else:
        bounds.remove(bounds[0])
    document.write(path)
    with pytest.raises(ValueError, match="imagery.xml: incorrect source"):
        validate_build(data_root, generated)


@pytest.mark.usefixtures("source")
def test_incorrect_legacy_extent_rejected(data_root: Path) -> None:
    generated = data_root / "build"
    build(data_root, generated)
    path = generated / "imagery.json"
    document = json.loads(path.read_bytes())
    del document[0]["extent"]["polygon"]
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="imagery.json: incorrect extent"):
        validate_build(data_root, generated)


def test_invalid_original_geometry_is_not_repaired(
    data_root: Path, source: Path, feature: JSON
) -> None:
    feature["geometry"]["coordinates"] = [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]]
    source.write_text(json.dumps(feature))
    with pytest.raises(
        ValueError, match="Invalid exported geometry|consecutive duplicate positions"
    ):
        build(data_root, data_root / "build")
    assert not (data_root / "build").exists()
