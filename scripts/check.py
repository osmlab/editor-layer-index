#!/usr/bin/env python

"""
usage: check.py [-h] [-v] path [path ...]

Checks ELI sourcen for validity and common errors

Adding -v increases log verbosity for each occurence:

    check.py foo.geojson only shows errors
    check.py -v foo.geojson shows warnings too
    check.py -vv foo.geojson shows debug messages too
    etc.

Suggested way of running:

find sources -name \*.geojson | xargs python scripts/check.py -vv

"""

from argparse import ArgumentParser
from jsonschema import validate, ValidationError, RefResolver, Draft4Validator
from pygeotile.tile import Tile
from shapely.geometry import Point, shape
import colorlog
import httpx
import io
import json
import magic
import os
import random
import re
import spdx_lookup


switches = re.compile("{switch:([^}]*)}")


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
parser.add_argument("--strict", help="enable more strict checks", action="store_true")

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

strict_mode = arguments.strict

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36; OpenStreetMap Editor Layer Index CI check)"
}


def test_tms(data, filename):
    url = data["properties"]["url"]
    try:
        sw = switches.findall(url)[0].split(",")
        noswitches = False
    except IndexError:
        noswitches = True
    minzoom = data["properties"].get("min_zoom", 1)
    maxzoom = data["properties"]["max_zoom"]
    if data["geometry"] == None:
        point = Point(6.1, 49.6)
    else:
        point = shape(data["geometry"]).representative_point()

    # Test maxzoom and all switches
    tile = Tile.for_latitude_longitude(
        latitude=point.y, longitude=point.x, zoom=maxzoom
    )  # Tile Map Service (TMS) X Y and zoom
    if noswitches:
        allswitches = ["foo"]
    else:
        allswitches = switches.findall(url)[0].split(",")
    for s in allswitches:
        myurl = switches.sub(s, url)
        myurl = (
            myurl.replace("{zoom}", str(maxzoom))
            .replace("{x}", str(tile.google[0]))
            .replace("{y}", str(tile.google[1]))
            .replace("{-y}", str(tile.tms[1]))
        )
        try:
            r = httpx.get(myurl, headers=headers)
        except httpx.exceptions.NetworkError:
            raise ValidationError(
                "{}: tile url {} is not reachable: Network error".format(
                    filename, myurl
                )
            )
        if not r.status_code == 200:
            raise ValidationError(
                "{}: tile url {} is not reachable: HTTP code: {}".format(
                    filename, myurl, r.status_code
                )
            )
    # Test minzoom
    tile = Tile.for_latitude_longitude(
        latitude=point.y, longitude=point.x, zoom=minzoom
    )
    myurl = switches.sub(allswitches[0], url)
    myurl = (
        myurl.replace("{zoom}", str(minzoom))
        .replace("{x}", str(tile.google[0]))
        .replace("{y}", str(tile.google[1]))
        .replace("{-y}", str(tile.tms[1]))
    )
    try:
        r = httpx.get(myurl, headers=headers)
    except httpx.exceptions.NetworkError:
        raise ValidationError(
            "{}: tile url {} is not reachable: Network error".format(filename, myurl)
        )
    if not r.status_code == 200 and magic.from_buffer(r.content).startswith(
        ("JPEG", "PNG")
    ):
        raise ValidationError(
            "{}: tile url {} is not reachable: HTTP code: {}".format(
                filename, myurl, r.status_code
            )
        )

    # Test maxzoom + 1
    zoomenhance = maxzoom + 1
    tile = Tile.for_latitude_longitude(
        latitude=point.y, longitude=point.x, zoom=zoomenhance
    )
    myurl = switches.sub(allswitches[0], url)
    myurl = (
        myurl.replace("{zoom}", str(zoomenhance))
        .replace("{x}", str(tile.google[0]))
        .replace("{y}", str(tile.google[1]))
        .replace("{-y}", str(tile.tms[1]))
    )
    try:
        r = httpx.get(myurl, headers=headers)
    except httpx.exceptions.NetworkError:
        raise ValidationError(
            "{}: tile url {} is not reachable: Network error".format(filename, myurl)
        )
    if r.status_code == 200 and magic.from_buffer(r.content).startswith(
        ("JPEG", "PNG")
    ):
        logger.warning(
            "{}: tile url {} is reachable: HTTP code: {}. File type returned: {}. Maybe maxzoom can be increased to {}".format(
                filename,
                myurl,
                r.status_code,
                magic.from_buffer(r.content),
                zoomenhance,
            )
        )
    if minzoom > 1:
        tothemoon = minzoom - 1
        tile = Tile.for_latitude_longitude(
            latitude=point.y, longitude=point.x, zoom=tothemoon
        )
        myurl = switches.sub(allswitches[0], url)
        myurl = (
            myurl.replace("{zoom}", str(tothemoon))
            .replace("{x}", str(tile.google[0]))
            .replace("{y}", str(tile.google[1]))
            .replace("{-y}", str(tile.tms[1]))
        )
        try:
            r = httpx.get(myurl, headers=headers)
        except httpx.exceptions.NetworkError:
            raise ValidationError(
                "{}: tile url {} is not reachable: Network error".format(
                    filename, myurl
                )
            )        if r.status_code == 200 and magic.from_buffer(r.content).startswith(
            ("JPEG", "PNG")
        ):
            logger.warning(
                "{}: tile url {} is reachable: HTTP code: {}. File type returned: {}. Maybe minzoom can be decreased to {}".format(
                    filename,
                    myurl,
                    r.status_code,
                    magic.from_buffer(r.content),
                    tothemoon,
                )
            )


for filename in arguments.path:

    if not filename.lower()[-8:] == ".geojson":
        logger.debug("{} is not a geojson file, skip".format(filename))
        continue

    if not os.path.exists(filename):
        logger.debug("{} does not exist, skip".format(filename))
        continue

    try:
        if strict_mode:
            logger.warning("Proccessing {} in strict mode".format(filename))

        ## dict_raise_on_duplicates raises error on duplicate keys in geojson
        source = json.load(
            io.open(filename, encoding="utf-8"),
            object_pairs_hook=dict_raise_on_duplicates,
        )

        ## jsonschema validate
        validator.validate(source, schema)
        sourceid = source["properties"]["id"]
        if sourceid in seen_ids:
            raise ValidationError("Id %s used multiple times" % sourceid)
        seen_ids.add(sourceid)

        ## {z} instead of {zoom}
        if "{z}" in source["properties"]["url"]:
            raise ValidationError("{z} found instead of {zoom} in tile url")
        if "license" in source["properties"]:
            license = source["properties"]["license"]
            if not spdx_lookup.by_id(license) and license != "COMMERCIAL":
                raise ValidationError("Unknown license %s" % license)
        else:
            logger.debug("{} has no license property".format(filename))

        ## Check for license url. Too many missing to mark as required in schema.
        if "license_url" not in source["properties"]:
            logger.debug("{} has no license_url".format(filename))

        ## Check if license url exists
        if strict_mode and "license_url" in source["properties"]:
            try:
                r = httpx.get(source["properties"]["license_url"], headers=headers)
                if not r.status_code == 200:
                    raise ValidationError(
                        "{}: license url {} is not reachable: HTTP code: {}".format(
                            filename, source["properties"]["license_url"], r.status_code
                        )
                    )

            except Exception as e:
                raise ValidationError(
                    "{}: license url {} is not reachable: {}".format(
                        filename, source["properties"]["license_url"], str(e)
                    )
                )

        if "attribution" not in source["properties"]:
            logger.debug("{} has no attribution".format(filename))

        ## Check for big fat embedded icons
        if "icon" in source["properties"]:
            if source["properties"]["icon"].startswith("data:"):
                iconsize = len(source["properties"]["icon"].encode("utf-8"))
                spacesave += iconsize
                logger.error(
                    "{} icon should be disembedded to save {} KB".format(
                        filename, round(iconsize / 1024.0, 2)
                    )
                )

        ## Validate that url will work as we expect
        params = []

        ### tms
        if source["properties"]["type"] == "tms":
            if not "max_zoom" in source["properties"]:
                raise ValidationError(
                    "Missing max_zoom parameter in {}".format(filename)
                )
            if "available_projections" in source["properties"]:
                logger.error(
                    "Senseless available_projections parameter in {}".format(filename)
                )
            if "min_zoom" in source["properties"]:
                if source["properties"]["min_zoom"] == 0:
                    logger.warning("Useless min_zoom parameter in {}".format(filename))
            params = ["{zoom}", "{x}", "{y}"]
            test_tms(source, filename)

        ### wms: {proj}, {bbox}, {width}, {height}
        elif source["properties"]["type"] == "wms":
            if "min_zoom" in source["properties"]:
                logger.error("Senseless min_zoom parameter in {}".format(filename))
            if "max_zoom" in source["properties"]:
                logger.error("Senseless max_zoom parameter in {}".format(filename))
            if not "available_projections" in source["properties"]:
                raise ValidationError(
                    "Missing available_projections parameter in {}".format(filename)
                )
            params = ["{proj}", "{bbox}", "{width}", "{height}"]

        missingparams = [
            x
            for x in params
            if x not in source["properties"]["url"].replace("{-y}", "{y}")
        ]
        if missingparams:
            raise ValidationError(
                "Missing parameter in {}: {}".format(filename, missingparams)
            )

        # If we're not global we must have a geometry.
        # The geometry itself is validated by jsonschema
        if "world" not in filename:
            if not "type" in source["geometry"]:
                raise ValidationError(
                    "{} should have a valid geometry or be global".format(filename)
                )
            if source["geometry"]["type"] != "Polygon":
                raise ValidationError(
                    "{} should have a Polygon geometry".format(filename)
                )
            if not "country_code" in source["properties"]:
                raise ValidationError(
                    "{} should have a country or be global".format(filename)
                )
        else:
            if "geometry" not in source:
                ValidationError("{} should have null geometry".format(filename))
            elif source["geometry"] != None:
                ValidationError(
                    "{} should have null geometry but it is {}".format(
                        filename, source["geometry"]
                    )
                )

        ## Privacy policy
        if strict_mode:

            # Check if privacy url is set
            if "privacy_policy_url" not in source["properties"]:
                raise ValidationError(
                    "{} has no privacy_policy_url. Adding privacy policies to sources"
                    " is important to comply with legal requirements in certain countries.".format(
                        filename
                    )
                )

            # Check if privacy url exists
            try:
                r = httpx.get(
                    source["properties"]["privacy_policy_url"], headers=headers
                )
                if not r.status_code == 200:
                    raise ValidationError(
                        "{}: privacy policy url {} is not reachable: HTTP code: {}".format(
                            filename,
                            source["properties"]["privacy_policy_url"],
                            r.status_code,
                        )
                    )

            except Exception as e:
                raise ValidationError(
                    "{}: privacy policy url {} is not reachable: {}".format(
                        filename, source["properties"]["privacy_policy_url"], str(e)
                    )
                )

    except ValidationError as e:
        borkenbuild = True
        logger.exception("Error in {} : {}".format(filename, e))
if spacesave > 0:
    logger.warning(
        "Disembedding all icons would save {} KB".format(round(spacesave / 1024.0, 2))
    )
if borkenbuild:
    raise SystemExit(1)
