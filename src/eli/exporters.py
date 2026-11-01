"""Compatible exporters for existing ELI consumers."""

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

import yaml
from shapely import get_num_coordinates, get_num_geometries
from shapely.geometry import MultiPolygon, Polygon, shape

from eli.common import JSON, SOURCE_METADATA_FIELDS


@dataclass(frozen=True)
class LegacyOptions:
    """Select the historical legacy JSON conversion options."""

    gen_bbox: bool = False
    tms_only: bool = False
    remove_polygons: bool = False


def convert_json_source(args: LegacyOptions, source: JSON) -> JSON:
    converted = {}
    extent_obj: JSON = {}
    geometry = source.get("geometry")
    if geometry:
        geom = shape(geometry)
        if args.gen_bbox:
            extent_obj["bbox"] = dict(
                zip(("min_lon", "min_lat", "max_lon", "max_lat"), geom.bounds, strict=True)
            )
        if not args.remove_polygons:
            exterior_rings = []
            if isinstance(geom, Polygon):
                exterior_rings.append(list(geom.exterior.coords))
            elif isinstance(geom, MultiPolygon):
                for poly in geom.geoms:
                    exterior_rings.append(list(poly.exterior.coords))
            extent_obj["polygon"] = exterior_rings
    properties = source.get("properties") or {}
    if args.tms_only and properties["type"] == "wms":
        return {}
    for f in [
        "name",
        "type",
        "url",
        *SOURCE_METADATA_FIELDS,
        "privacy_policy_url",
    ]:
        thing = properties.get(f)
        if thing is not None:
            converted[f] = thing
    for f in ["min_zoom", "max_zoom"]:
        thing = properties.get(f)
        if thing is not None:
            extent_obj[f] = thing
    if extent_obj:
        converted["extent"] = extent_obj
    return converted


# Preserve the exact order of optional JOSM fields in the legacy XML output.
# pylint: disable-next=R0915
def xml_bytes(sources: list[JSON]) -> bytes:
    root = ET.Element("imagery", {"xmlns": "http://josm.openstreetmap.de/maps-1.0"})

    # Each optional JOSM field is mapped explicitly to preserve legacy XML ordering.
    # pylint: disable-next=R0912,R0914,R0915
    def add_source(source: JSON) -> None:
        props = source["properties"]
        entry = ET.SubElement(root, "entry")
        name = ET.SubElement(entry, "name")
        name.text = props["name"]
        identifier_element = ET.SubElement(entry, "id")
        identifier_element.text = props["id"]
        type_element = ET.SubElement(entry, "type")
        type_element.text = props["type"]
        url = ET.SubElement(entry, "url")
        url.text = props["url"]
        category = ET.SubElement(entry, "category")
        if "category" in props:
            category.text = props["category"]
        else:
            category.text = "photo"
        if props.get("overlay"):
            entry.set("overlay", "true")
        if props.get("best"):
            entry.set("eli-best", "true")
        if "available_projections" in props:
            projections = ET.SubElement(entry, "projections")
            for projection in props["available_projections"]:
                code = ET.SubElement(projections, "code")
                code.text = projection
        if "attribution" in props:
            attribution = props["attribution"]
            if attribution.get("text"):
                text = ET.SubElement(entry, "attribution-text")
                if attribution.get("required"):
                    text.set("mandatory", "true")
                text.text = attribution["text"]
            if attribution.get("url"):
                url = ET.SubElement(entry, "attribution-url")
                url.text = attribution["url"]
        if source.get("default", False):
            default = ET.SubElement(entry, "default")
            default.text = "true"
        if "start_date" in props:
            date = ET.SubElement(entry, "date")
            if "end_date" in props and props["start_date"] == props["end_date"]:
                date.text = props["start_date"]
            elif "end_date" in props and props["start_date"] != props["end_date"]:
                date.text = ";".join([props["start_date"], props["end_date"]])
            else:
                date.text = ";".join([props["start_date"], "-"])
        if "icon" in props:
            icon = ET.SubElement(entry, "icon")
            icon.text = props["icon"]
        if "country_code" in props and props["country_code"].upper() not in ["XN", "ZZ"]:
            country_code = ET.SubElement(entry, "country-code")
            country_code.text = props["country_code"]
        if "license_url" in props:
            permission_ref = ET.SubElement(entry, "permission-ref")
            permission_ref.text = props["license_url"]
        if "description" in props:
            description = ET.SubElement(entry, "description")
            description.text = props["description"]
            description.set("lang", "en")
        if "min_zoom" in props:
            min_zoom = ET.SubElement(entry, "min-zoom")
            min_zoom.text = str(props["min_zoom"])
        if "max_zoom" in props:
            max_zoom = ET.SubElement(entry, "max-zoom")
            max_zoom.text = str(min(24, props["max_zoom"]))
        geometry = source.get("geometry")
        if geometry:

            def coord_str(coord: float) -> str:
                rounded = f"{coord:.6f}"
                return rounded if float(rounded) == coord else str(coord)

            geom = shape(geometry)
            bounds = ET.SubElement(entry, "bounds")
            minx, miny, maxx, maxy = geom.bounds
            bounds.set("min-lon", coord_str(minx))
            bounds.set("min-lat", coord_str(miny))
            bounds.set("max-lon", coord_str(maxx))
            bounds.set("max-lat", coord_str(maxy))
            if isinstance(geom, Polygon) and get_num_coordinates(geom) <= 999:
                shape_element = ET.SubElement(bounds, "shape")
                for lon, lat in geom.exterior.coords:
                    point = ET.SubElement(shape_element, "point")
                    point.set("lon", coord_str(lon))
                    point.set("lat", coord_str(lat))
            if isinstance(geom, MultiPolygon) and get_num_geometries(geom) <= 100:
                for poly in geom.geoms:
                    if get_num_coordinates(poly) > 999:
                        return
                for poly in geom.geoms:
                    shape_element = ET.SubElement(bounds, "shape")
                    for lon, lat in poly.exterior.coords:
                        point = ET.SubElement(shape_element, "point")
                        point.set("lon", coord_str(lon))
                        point.set("lat", coord_str(lat))

    for source in sources:
        add_source(source)
    result = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    assert isinstance(result, bytes)
    return result


def translation_text(sources: list[JSON]) -> str:
    data: JSON = {}
    for source in sources:
        props = source["properties"]
        if "i18n" in props and props["i18n"]:
            layer_id = props["id"]
            data[layer_id] = {}
            if "name" in props:
                data[layer_id]["name"] = props["name"]
            if "description" in props:
                data[layer_id]["description"] = props["description"]
            if "attribution" in props:
                attr = props["attribution"]
                data[layer_id]["attribution"] = {}
                if "text" in attr:
                    data[layer_id]["attribution"]["text"] = attr["text"]

    return (
        yaml.safe_dump(
            {"en": {"imagery": data}},
            allow_unicode=True,
            default_flow_style=False,
            default_style="",
            width=99999,
        )
        + "\n"
    )


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"


def geojson_text(sources: list[JSON], generated: str) -> str:
    return json_text(
        {
            "type": "FeatureCollection",
            "meta": {"generated": generated, "format_version": "1.0"},
            "features": sources,
        }
    )


def legacy_text(sources: list[JSON], options: LegacyOptions = LegacyOptions()) -> str:
    return json_text([convert_json_source(options, source) for source in sources])
