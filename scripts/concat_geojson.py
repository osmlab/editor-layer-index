#!/usr/bin/env python
import argparse
import glob
import json
import os
from datetime import datetime

parser = argparse.ArgumentParser(description="Convert all sources to a single geojson")
parser.add_argument(
    "sources",
    metavar="sources",
    type=str,
    nargs="?",
    help="relative path to sources directory",
    default="sources",
)

arguments = parser.parse_args()

source_features = []
for filename in glob.glob(
    os.path.join(arguments.sources, "**", "*.geojson"), recursive=True
):
    with open(filename, "r") as f:
        # simplify all floats to 5 decimal points
        source_features.append(json.load(f, parse_float=lambda x: round(float(x), 5)))

generated = "{:%Y-%m-%d %H:%M:%S}".format(datetime.utcnow())
version = "1.0"

collection = {
    "type": "FeatureCollection",
    "meta": {"generated": generated, "format_version": version},
    "features": source_features,
}

with open("imagery.geojson", "w", encoding="utf-8") as out:
    json.dump(
        collection, out, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    out.write("\n")
