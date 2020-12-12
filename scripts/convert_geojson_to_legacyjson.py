#!/usr/bin/env python
import glob
import json
import os
import sys
import io
import argparse

parser = argparse.ArgumentParser(
    description="Generate legacy json output format from geojson format sources"
)

parser.add_argument(
    "-b",
    dest="gen_bbox",
    action="store_true",
    help="generate bounding boxes from polygons",
)
parser.add_argument(
    "-t", dest="tms_only", action="store_true", help="only include tile servers"
)
parser.add_argument(
    "-r",
    dest="remove_polygons",
    action="store_true",
    help="remove polygons from output, typically used together with -b",
)

parser.add_argument(
    "sources",
    metavar="sources",
    type=str,
    nargs="?",
    help="relative path to sources directory",
    default="sources",
)

arguments = parser.parse_args()


def convert_json_source(args, source):
    converted = {}
    extent_obj = {}

    geometry = source.get("geometry") or {}
    polygon_coords = geometry.get("coordinates") or []
    if polygon_coords:
        if args.gen_bbox:
            # extent_obj['polygon'] = polygon_coords
            # generate bbox from polygon coordinates as a stop gap
            min_lon = 180
            max_lon = -180
            min_lat = 90
            max_lat = -90
            for ring in polygon_coords:
                for coord in ring:
                    if coord[0] < min_lon:
                        min_lon = coord[0]
                    if coord[0] > max_lon:
                        max_lon = coord[0]
                    if coord[1] < min_lat:
                        min_lat = coord[1]
                    if coord[1] > max_lat:
                        max_lat = coord[1]
            bbox_obj = {}
            bbox_obj["min_lon"] = min_lon
            bbox_obj["max_lon"] = max_lon
            bbox_obj["min_lat"] = min_lat
            bbox_obj["max_lat"] = max_lat
            extent_obj["bbox"] = bbox_obj
        if not args.remove_polygons:
            extent_obj["polygon"] = polygon_coords

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


features = []
for filename in glob.glob(
    os.path.join(arguments.sources, "**", "*.geojson"), recursive=True
):
    with open(filename, "r") as f:
        features.append(
            convert_json_source(
                arguments, json.load(f, parse_float=lambda x: round(float(x), 5))
            )
        )


with open("imagery.json", "w", encoding="utf-8") as out:
    json.dump(features, out, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    out.write("\n")
