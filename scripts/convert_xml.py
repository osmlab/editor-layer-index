import json
import sys
import io
import xml.etree.cElementTree as ET
from shapely.geometry import shape, Polygon, MultiPolygon

root = ET.Element("imagery")

sources = []
for file in sys.argv[1:]:
    with io.open(file, "r") as f:
        sources.append(json.load(f, parse_float=lambda x: round(float(x), 5)))


def add_source(source):
    props = source["properties"]
    entry = ET.SubElement(root, "entry")

    name = ET.SubElement(entry, "name")
    name.text = props["name"]

    name = ET.SubElement(entry, "id")
    name.text = props["id"]

    type = ET.SubElement(entry, "type")
    type.text = props["type"]

    url = ET.SubElement(entry, "url")
    url.text = props["url"]

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

    if "country_code" in props:
        country_code = ET.SubElement(entry, "country-code")
        country_code.text = props["country_code"]

    if "license_url" in props:
        permission_ref = ET.SubElement(entry, "permission-ref")
        permission_ref.text = props["license_url"]

    if "description" in props:
        description = ET.SubElement(entry, "description")
        description.text = props["description"]

    if "min_zoom" in props:
        min_zoom = ET.SubElement(entry, "min-zoom")
        min_zoom.text = str(props["min_zoom"])

    if "max_zoom" in props:
        max_zoom = ET.SubElement(entry, "max-zoom")
        max_zoom.text = str(props["max_zoom"])

    geometry = source.get("geometry")
    if geometry:

        def coord_str(coord):
            return "{0:.6f}".format(coord)

        geom = shape(geometry)

        bounds = ET.SubElement(entry, "bounds")
        minx, miny, maxx, maxy = geom.bounds
        bounds.set("min-lon", coord_str(minx))
        bounds.set("min-lat", coord_str(miny))
        bounds.set("max-lon", coord_str(maxx))
        bounds.set("max-lat", coord_str(maxy))

        if isinstance(geom, Polygon):
            shape_element = ET.SubElement(bounds, "shape")
            for lon, lat in geom.exterior.coords:
                point = ET.SubElement(shape_element, "point")
                point.set("lon", coord_str(lon))
                point.set("lat", coord_str(lat))

        if isinstance(geom, MultiPolygon):
            for poly in geom.geoms:
                shape_element = ET.SubElement(bounds, "shape")
                for lon, lat in poly.exterior.coords:
                    point = ET.SubElement(shape_element, "point")
                    point.set("lon", coord_str(lon))
                    point.set("lat", coord_str(lat))


for source in sources:
    try:
        add_source(source)
    except Exception as e:
        print(f"Failed to convert {source}: {e}")
        pass

tree = ET.ElementTree(root)
with io.open("imagery.xml", mode="wb") as f:
    tree.write(f, encoding="utf-8", xml_declaration=True)
