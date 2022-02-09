#!/usr/bin/env python
import json
import sys
import io
import argparse
from shapely.geometry import shape, Polygon, MultiPolygon


def convert_json_source(args, source):
    converted = {}
    extent_obj = {}

    geometry = source.get("geometry")
    if geometry:
        geom = shape(geometry)

        if args.gen_bbox:
            minx, miny, maxx, maxy = geom.bounds
            bbox_obj = {"min_lon": minx, "max_lon": maxx, "min_lat": miny, "max_lat": maxy}
            extent_obj["bbox"] = bbox_obj

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
        "license_url",
        "id",
        "description",
        "country_code",
        "default",
        "best",
        "start_date",
        "end_date",
        "overlay",
        "available_projections",
        "attribution",
        "icon",
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


parser = argparse.ArgumentParser(description="Generate legacy json output format from geojosn format sources")
parser.add_argument("files", metavar="F", nargs="+", help="file(s) to process")
parser.add_argument("-b", dest="gen_bbox", action="store_true", help="generate bounding boxes from polygons")
parser.add_argument("-t", dest="tms_only", action="store_true", help="only include tile servers")
parser.add_argument(
    "-r",
    dest="remove_polygons",
    action="store_true",
    help="remove polygons from output, typically used together with -b",
)

args = parser.parse_args()

features = []
for file in args.files:
    with io.open(file, "r") as f:
        features.append(convert_json_source(args, json.load(f, parse_float=lambda x: round(float(x), 5))))

output = json.dumps(features, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
if sys.version_info.major == 2:
    output = output.encode("utf8")
print(output)
