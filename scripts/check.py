#!/usr/bin/env python

"""
usage: check.py [-h] [-v] path [path ...]

Checks ELI sourcen for validity and common errors

Adding -v increases log verbosity for each occurrence:

    check.py foo.geojson only shows errors
    check.py -v foo.geojson shows warnings too
    check.py -vv foo.geojson shows debug messages too
    etc.

Suggested way of running:

find sources -name \*.geojson | xargs python scripts/check.py -vv

"""

import io
import json
import os
import warnings
from argparse import ArgumentParser

import colorlog
from jsonschema import Draft4Validator, RefResolver, ValidationError
from shapely.geometry import shape
from shapely.validation import explain_validity


def dict_raise_on_duplicates(ordered_pairs):
    """Reject duplicate keys."""
    d = {}
    for k, v in ordered_pairs:
        if k in d:
            raise ValidationError("duplicate key: %r" % (k,))
        else:
            d[k] = v
    return d


parser = ArgumentParser(description="Checks ELI sourcen for validity and common errors")
parser.add_argument("path", nargs="+", help="Path of files to check.")
parser.add_argument(
    "-v",
    "--verbose",
    dest="verbose_count",
    action="count",
    default=0,
    help="increases log verbosity for each occurence.",
)

arguments = parser.parse_args()
logger = colorlog.getLogger()
# Start off at Error, reduce by one level for each -v argument
logger.setLevel(max(4 - arguments.verbose_count, 0) * 10)
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter())
logger.addHandler(handler)

schema = json.load(io.open("schema.json", encoding="utf-8"))
seen_ids = set()

resolver = RefResolver("", None)
validator = Draft4Validator(schema, resolver=resolver)

borkenbuild = False
spacesave = 0

headers = {"User-Agent": "Mozilla/5.0 (compatible; MSIE 6.0; OpenStreetMap Editor Layer Index CI check)"}

tested_sources_count = 0
for filename in arguments.path:

    if not filename.lower()[-8:] == ".geojson":
        logger.debug("{} is not a geojson file, skip".format(filename))
        continue

    if not os.path.exists(filename):
        logger.debug("{} does not exist, skip".format(filename))
        continue

    if ":" in filename:
        raise ValidationError(f"Filename contains invalid \":\" character: {filename}")

    try:
        ## dict_raise_on_duplicates raises error on duplicate keys in geojson
        source = json.load(io.open(filename, encoding="utf-8"), object_pairs_hook=dict_raise_on_duplicates)
    except Exception as e:
        logger.exception(f"Could not parse file: {filename}: {e}")
        raise ValidationError(f"Could not parse file: {filename}: {e}")

    try:

        ## dict_raise_on_duplicates raises error on duplicate keys in geojson
        source = json.load(io.open(filename, encoding="utf-8"), object_pairs_hook=dict_raise_on_duplicates)

        ## jsonschema validate
        validator.validate(source, schema)
        sourceid = source["properties"]["id"]
        if sourceid in seen_ids:
            raise ValidationError("Id %s used multiple times" % sourceid)
        seen_ids.add(sourceid)

        ## {z} instead of {zoom}
        if "{z}" in source["properties"]["url"]:
            raise ValidationError("{z} found instead of {zoom} in tile url")

        ## Check for license url. Too many missing to mark as required in schema.
        if "license_url" not in source["properties"]:
            logger.debug("{} has no license_url".format(filename))

        if "attribution" not in source["properties"]:
            logger.debug("{} has no attribution".format(filename))

        ## Check for big fat embedded icons
        if "icon" in source["properties"]:
            if source["properties"]["icon"].startswith("data:"):
                iconsize = len(source["properties"]["icon"].encode("utf-8"))
                spacesave += iconsize
                warnings.warn(f"{filename} icon should be disembedded to save {round(iconsize/1024.0, 2)} KB")

        ## Validate that url has the tokens we expect
        params = []

        ### tms
        if source["properties"]["type"] == "tms":
            if "max_zoom" in source["properties"]:
                if source["properties"]["max_zoom"] == 20:
                    logger.warning(f"Useless max_zoom parameter in {filename}")
            if "available_projections" in source["properties"]:
                warnings.warn(f"Senseless available_projections parameter in {filename}")
            if "min_zoom" in source["properties"]:
                if source["properties"]["min_zoom"] == 0:
                    logger.warning(f"Useless min_zoom parameter in {filename}")
            params = ["{zoom}", "{x}", "{y}"]

        ### wms: {proj}, {bbox}, {width}, {height}
        elif source["properties"]["type"] == "wms":
            if not "available_projections" in source["properties"]:
                raise ValidationError(f"Missing available_projections parameter in {filename}")
            params = ["{proj}", "{bbox}", "{width}", "{height}"]

        ### wmts:
        if source["properties"]["type"] == "wmts":
            for tms_url_parameter in ["{zoom}", "{x}", "{y}", "{-y}"]:
                if tms_url_parameter in source["properties"]["url"]:
                    raise ValidationError(f"wmts URL should not contain tms parameter {tms_url_parameter} in URL")
            if not "available_projections" in source["properties"]:
                raise ValidationError(f"Missing available_projections parameter in {filename}")
            if (
                "available_projections" in source["properties"]
                and "EPSG:3857" in source["properties"]["available_projections"]
            ):
                logger.warning(f"WMTS source supports EPSG:3857, could this be tms? {filename}")

        missingparams = [x for x in params if x not in source["properties"]["url"].replace("{-y}", "{y}")]
        if missingparams:
            raise ValidationError("Missing parameter in {}: {}".format(filename, missingparams))

        # Check for double brackets
        if "{{" in source["properties"]["url"] or "}}" in source["properties"]["url"]:
            raise ValidationError(f"{filename}: Double {{{{ or }}}} in URL: {source['properties']['url']}")

        # If we're not global we must have a geometry.
        # The geometry itself is validated by jsonschema
        if "world" not in filename:
            if not "type" in source["geometry"]:
                raise ValidationError("{} should have a valid geometry or be global".format(filename))
            if source["geometry"]["type"] not in {"Polygon", "MultiPolygon"}:
                raise ValidationError("{} should have a Polygon or MultiPolygon geometry".format(filename))
            if not "country_code" in source["properties"]:
                raise ValidationError("{} should have a country or be global".format(filename))

            geom = shape(source["geometry"])
             # Check validity of geometries
            if not geom.is_valid:
                raise ValidationError(f"{filename} geometry is not valid: {explain_validity(geom)}")

            min_lon, min_lat, max_lon, max_lat = geom.bounds
            within_bounds = True
            for lon in [min_lon, max_lon]:
                if lon < -180.0 or lon > 180.0:
                    within_bounds = False
            for lat in [min_lat, max_lat]:
                if lat < -90.0 or lat > 90.0:
                    within_bounds = False
            if not within_bounds:
                raise ValidationError(
                    "{} contains invalid coordinates.: Geometry extent: {}"
                    "".format(filename, ",".join(map(str, [min_lon, min_lat, max_lon, max_lat])))
                )
        else:
            if "geometry" not in source:
                raise ValidationError("{} should have null geometry".format(filename))
            elif source["geometry"] != None:
                raise ValidationError("{} should have null geometry but it is {}".format(filename, source["geometry"]))
        tested_sources_count += 1
    except ValidationError as e:
        borkenbuild = True
        logger.exception("Error in {} : {}".format(filename, e))
if spacesave > 0:
    logger.warning("Disembedding all icons would save {} KB".format(round(spacesave / 1024.0, 2)))

print(f"Checked {tested_sources_count} sources.")
if borkenbuild or tested_sources_count == 0:
    raise SystemExit(1)
