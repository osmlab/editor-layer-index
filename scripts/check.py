#!/usr/bin/env python

"""
Usage: check.py [-h] [-v] sources_directory

Checks ELI sources for validity and common errors
Adding -v increases log verbosity for each occurrence:
    check.py sources only shows errors
    check.py -v sources shows warnings too
    check.py -vv sources shows debug messages too
    etc.

Suggested way of running:
python scripts/check.py -vv sources

"""
import glob
import json
import io
from argparse import ArgumentParser
from jsonschema import ValidationError, RefResolver, Draft4Validator
import colorlog
import os
from shapely.geometry import shape, box, Polygon
from shapely.ops import cascaded_union


def dict_raise_on_duplicates(ordered_pairs):
    """Reject duplicate keys."""
    d = {}
    for k, v in ordered_pairs:
        if k in d:
            raise ValidationError("duplicate key: %r" % (k,))
        else:
            d[k] = v
    return d


parser = ArgumentParser(description="Checks ELI sources for validity and common errors")
parser.add_argument(
    "-v",
    "--verbose",
    dest="verbose_count",
    action="count",
    default=0,
    help="increases log verbosity for each occurrence.",
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

broken_build = False
space_save = 0

headers = {
    "User-Agent": "Mozilla/5.0 (compatible; MSIE 6.0; OpenStreetMap Editor Layer Index CI check)"
}


def parse_eli_geometry(geometry):
    """ELI currently uses a geometry encoding not compatible with geojson.
    Create valid geometries from this format."""
    _geom = shape(geometry)
    # Fail if other geometry types than Polygon are encountered
    assert geometry["type"] == "Polygon"
    geoms = [Polygon(_geom.exterior.coords)]
    for ring in _geom.interiors:
        geoms.append(Polygon(ring.coords))
    return cascaded_union(geoms)


for filename in glob.glob(
    os.path.join(arguments.sources, "**", "*.geojson"), recursive=True
):

    if not filename.lower()[-8:] == ".geojson":
        logger.debug("{} is not a geojson file, skip".format(filename))
        continue

    if not os.path.exists(filename):
        logger.debug("{} does not exist, skip".format(filename))
        continue

    try:
        # dict_raise_on_duplicates raises error on duplicate keys in geojson
        source = json.load(
            io.open(filename, encoding="utf-8"),
            object_pairs_hook=dict_raise_on_duplicates,
        )

        # jsonschema validate
        validator.validate(source, schema)
        source_id = source["properties"]["id"]
        if source_id in seen_ids:
            raise ValidationError(f"Id {source_id} used multiple times")
        seen_ids.add(source_id)

        # {z} instead of {zoom}
        if "{z}" in source["properties"]["url"]:
            raise ValidationError("{z} found instead of {zoom} in tile url")

        # Check for license url. Too many missing to mark as required in schema.
        if "license_url" not in source["properties"]:
            logger.debug("{} has no license_url".format(filename))

        if "attribution" not in source["properties"]:
            logger.debug("{} has no attribution".format(filename))

        # Check for big fat embedded icons
        if "icon" in source["properties"]:
            if source["properties"]["icon"].startswith("data:"):
                icon_size = len(source["properties"]["icon"].encode("utf-8"))
                space_save += icon_size
                file_size_kb = round(icon_size / 1024.0, 2)
                logger.debug(
                    f"{filename} icon should be disembedded to save {file_size_kb} KB"
                )

        # Validate that url has the tokens we expect
        params = []

        # tms
        if source["properties"]["type"] == "tms":
            if "max_zoom" not in source["properties"]:
                ValidationError(f"Missing max_zoom parameter in {filename}")
            if "available_projections" in source["properties"]:
                ValidationError(
                    f"Senseless available_projections parameter in {filename}"
                )
            if "min_zoom" in source["properties"]:
                if source["properties"]["min_zoom"] == 0:
                    logger.warning(f"Useless min_zoom parameter in {filename}")
            params = ["{zoom}", "{x}", "{y}"]

        # wms: {proj}, {bbox}, {width}, {height}
        elif source["properties"]["type"] == "wms":
            if "min_zoom" in source["properties"]:
                ValidationError(f"Senseless min_zoom parameter in {filename}")
            if "max_zoom" in source["properties"]:
                ValidationError(f"Senseless max_zoom parameter in {filename}")
            if "available_projections" not in source["properties"]:
                ValidationError(
                    f"Missing available_projections parameter in {filename}"
                )
            params = ["{proj}", "{bbox}", "{width}", "{height}"]

        missing_parameters = [
            x
            for x in params
            if x not in source["properties"]["url"].replace("{-y}", "{y}")
        ]
        if missing_parameters:
            raise ValidationError(
                f"Missing parameter in {filename}: {missing_parameters}"
            )

        # If we're not global we must have a geometry.
        # The geometry itself is validated by json schema
        if "world" not in filename:
            if "type" not in source["geometry"]:
                raise ValidationError(
                    f"{filename} should have a valid geometry or be global"
                )
            if source["geometry"]["type"] != "Polygon":
                raise ValidationError(f"{filename} should have a Polygon geometry")
            if "country_code" not in source["properties"]:
                raise ValidationError(f"{filename} should have a country or be global")

            # Check if coordinates are in the valid EPSG:4326 range
            geom = parse_eli_geometry(source["geometry"])
            max_extent_geom = box(-180.0, -90.0, 180.0, 90.0)
            if not max_extent_geom.contains(geom):
                raise ValidationError(
                    "{} contains invalid coordinates.: Geometry extent: {}"
                    "".format(
                        filename,
                        ",".join(map(lambda x: str(round(x, 12)), geom.bounds)),
                    )
                )
        else:
            if "geometry" not in source:
                ValidationError(f"{filename} should have null geometry")
            elif source["geometry"] is not None:
                ValidationError(
                    "{} should have null geometry but it is {}".format(
                        filename, source["geometry"]
                    )
                )

    except ValidationError as e:
        broken_build = True
        logger.exception(f"Error in {filename} : {e}")

if space_save > 0:
    logger.warning(
        "Disembedding all icons would save {} KB".format(round(space_save / 1024.0, 2))
    )

if broken_build:
    raise SystemExit(1)
