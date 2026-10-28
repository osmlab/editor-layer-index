"""Validate the bytes consumers receive before replacing or publishing a build."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml
from shapely.geometry import shape
from shapely.validation import explain_validity

from eli.common import JSON, discover, load_json, reject_duplicates, schema_validator
from eli.libeli.geometry import validate_polygon_coordinates

OUTPUTS = ("imagery.geojson", "imagery.json", "imagery.xml", "i18n/en.yaml")
XML_NAMESPACE = "{http://josm.openstreetmap.de/maps-1.0}"


def validate_geometry(geometry: JSON | None) -> None:
    if geometry is None:
        return
    validate_polygon_coordinates(geometry)
    geom = shape(geometry)
    if geom.is_empty or not geom.is_valid:
        raise ValueError(f"Invalid exported geometry: {explain_validity(geom)}")


def _reject_constant(value: str) -> Any:
    raise ValueError(f"Non-finite JSON number: {value}")


def _json(data: bytes) -> Any:
    return json.loads(data, object_pairs_hook=reject_duplicates, parse_constant=_reject_constant)


def _check_ids(actual: list[str], expected: list[str], name: str) -> None:
    if actual != expected or len(set(actual)) != len(actual):
        raise ValueError(f"{name}: source IDs or order do not match the inputs")


def _check_properties(actual: JSON, expected: JSON, name: str) -> None:
    for key in ("id", "name", "type", "url"):
        if actual.get(key) != expected[key]:
            raise ValueError(f"{name}: incorrect {key} for source {expected['id']}")


def _geojson(root: Path, data: bytes, sources: list[JSON]) -> list[JSON]:
    collection = _json(data)
    if collection["type"] != "FeatureCollection" or collection["meta"]["format_version"] != "1.0":
        raise ValueError("imagery.geojson: incorrect collection type or format version")
    features: list[JSON] = collection["features"]
    _check_ids(
        [feature["properties"]["id"] for feature in features],
        [source["properties"]["id"] for source in sources],
        "imagery.geojson",
    )
    validator = schema_validator(root)
    for feature, source in zip(features, sources, strict=True):
        validator.validate(feature)
        _check_properties(feature["properties"], source["properties"], "imagery.geojson")
        rounded = json.loads(json.dumps(source), parse_float=lambda value: round(float(value), 5))
        if feature["geometry"] not in (source["geometry"], rounded["geometry"]):
            raise ValueError(
                f"imagery.geojson: changed geometry for source {source['properties']['id']}"
            )
        rounded["geometry"] = feature["geometry"]
        if feature != rounded:
            raise ValueError(
                f"imagery.geojson: changed feature for source {source['properties']['id']}"
            )
        try:
            validate_geometry(feature["geometry"])
        except ValueError as error:
            raise ValueError(f"imagery.geojson: {source['properties']['id']}: {error}") from error
    return features


def _legacy(data: bytes, features: list[JSON]) -> None:
    entries = _json(data)
    _check_ids(
        [entry["id"] for entry in entries],
        [feature["properties"]["id"] for feature in features],
        "imagery.json",
    )
    for entry, feature in zip(entries, features, strict=True):
        _check_properties(entry, feature["properties"], "imagery.json")
        geometry = feature["geometry"]
        rings = entry.get("extent", {}).get("polygon")
        if geometry is None:
            expected = None
        elif geometry["type"] == "Polygon":
            expected = [geometry["coordinates"][0]]
        else:
            expected = [polygon[0] for polygon in geometry["coordinates"]]
        if rings != expected:
            raise ValueError(f"imagery.json: incorrect extent for source {entry['id']}")


def _xml_geometry(entry: ET.Element, geometry: JSON | None) -> None:
    bounds = entry.find(f"{XML_NAMESPACE}bounds")
    if geometry is None:
        if bounds is not None:
            raise ValueError("imagery.xml: unexpected bounds for global source")
        return
    if bounds is None:
        raise ValueError("imagery.xml: missing source bounds")
    actual = [float(bounds.attrib[key]) for key in ("min-lon", "min-lat", "max-lon", "max-lat")]
    if actual != list(shape(geometry).bounds):
        raise ValueError("imagery.xml: incorrect source bounds")
    polygons = geometry["coordinates"]
    if geometry["type"] == "Polygon":
        polygons = [polygons]
    # JOSM shapes historically omit oversized polygons but always retain bounds.
    include_shapes = len(polygons) <= 100 and all(
        sum(len(ring) for ring in polygon) <= 999 for polygon in polygons
    )
    expected = [polygon[0] for polygon in polygons] if include_shapes else []
    rings = []
    for polygon in bounds.findall(f"{XML_NAMESPACE}shape"):
        ring = [[float(point.attrib[key]) for key in ("lon", "lat")] for point in polygon]
        validate_geometry({"type": "Polygon", "coordinates": [ring]})
        rings.append(ring)
    if rings != expected:
        raise ValueError("imagery.xml: incorrect source shapes")


def _xml(data: bytes, features: list[JSON]) -> None:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise ValueError(f"imagery.xml: {error}") from error
    if root.tag != f"{XML_NAMESPACE}imagery":
        raise ValueError("imagery.xml: incorrect root or namespace")
    entries = list(root)
    _check_ids(
        [entry.findtext(f"{XML_NAMESPACE}id", "") for entry in entries],
        [feature["properties"]["id"] for feature in features],
        "imagery.xml",
    )
    for entry, feature in zip(entries, features, strict=True):
        if entry.tag != f"{XML_NAMESPACE}entry":
            raise ValueError("imagery.xml: unexpected element")
        _check_properties(
            {key: entry.findtext(f"{XML_NAMESPACE}{key}") for key in ("id", "name", "type", "url")},
            feature["properties"],
            "imagery.xml",
        )
        _xml_geometry(entry, feature["geometry"])


def _translations(data: bytes, sources: list[JSON]) -> None:
    document = yaml.safe_load(data)
    entries = document["en"]["imagery"]
    if not isinstance(entries, dict):
        raise ValueError("i18n/en.yaml: expected an imagery mapping")
    translated = [source["properties"] for source in sources if source["properties"].get("i18n")]
    if set(entries) != {props["id"] for props in translated}:
        raise ValueError("i18n/en.yaml: translated source IDs do not match the inputs")
    for props in translated:
        expected = {key: props[key] for key in ("name", "description") if key in props}
        if "attribution" in props:
            expected["attribution"] = {
                key: props["attribution"][key] for key in ("text",) if key in props["attribution"]
            }
        if entries[props["id"]] != expected:
            raise ValueError(f"i18n/en.yaml: incorrect translations for source {props['id']}")


def validate_artifacts(root: Path, rendered: dict[str, bytes], sources: list[JSON]) -> None:
    """Check parsed output contracts against independently loaded source identities."""
    if not sources:
        raise ValueError("No sources found")
    features = _geojson(root, rendered["imagery.geojson"], sources)
    _legacy(rendered["imagery.json"], features)
    _xml(rendered["imagery.xml"], features)
    _translations(rendered["i18n/en.yaml"], sources)


def validate_build(root: Path, generated: Path) -> None:
    """Validate an existing build again at its assembly and publication boundaries."""
    validate_artifacts(
        root,
        {name: (generated / name).read_bytes() for name in OUTPUTS},
        [load_json(path) for path in discover([], root)],
    )
