import json, sys, io
from jsonschema import validate, ValidationError
import spdx_lookup
import colorlog
import tqdm
from argparse import ArgumentParser


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

parser = ArgumentParser(description='Checks ELI sourcen for validity and common errors')
parser.add_argument('path', nargs='+', help='Path of files to check.')
parser.add_argument("-v", "--verbose", dest="verbose_count",
                        action="count", default=0,
                        help="increases log verbosity for each occurence.")
arguments = parser.parse_args()
logger = colorlog.getLogger()
# Start off at Error, reduce by one level for each -v argument
logger.setLevel(max(4 - arguments.verbose_count, 0) * 10)
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter())
logger.addHandler(handler)

schema = json.load(io.open('schema.json', encoding='utf-8'))
seen_ids = set()

resolver = RefResolver('', None)
validator = Draft4Validator(schema, resolver=resolver)


def dict_raise_on_duplicates(ordered_pairs):
    """Reject duplicate keys."""
    d = {}
    for k, v in ordered_pairs:
        if k in d:
           raise ValidationError("duplicate key: %r" % (k,))
        else:
           d[k] = v
    return d

borkenbuild = False
spacesave = 0

for filename in tqdm.tqdm(arguments.path):
    try:

        ## dict_raise_on_duplicates raises error on duplicate keys in geojson
        source = json.load(io.open(filename, encoding='utf-8'), object_pairs_hook=dict_raise_on_duplicates)

        ## jsonschema validate
        validate(source, schema)
        id = source['properties']['id']
        if id in seen_ids:
            raise ValidationError('Id %s used multiple times' % id)
        seen_ids.add(id)

        ## {z} instead of {zoom}
        if '{z}' in source['properties']['url']:
            raise ValidationError('{z} found instead of {zoom} in tile url')
        if 'license' in source['properties']:
            license = source['properties']['license']
            if not spdx_lookup.by_id(license):
                raise ValidationError('Unknown license %s' % license)

        ## Check for license url. Too many missing to mark as required in schema.
        try:
            license_url = source['properties']['license_url']
        except KeyError:
            logger.debug("Debug: {} has no license_url".format(filename))

        ## Check for big fat embedded icons
        try:
            if source['properties']['icon'].startswith("data:"):
                iconsize = len(source['properties']['icon'].encode('utf-8'))
                spacesave += iconsize
                logger.warning("{} icon should be disembedded to save {} KB".format(filename, round(iconsize/1024.0, 2)))
        except KeyError:
            pass

        ## Validate that url has the tokens we expect
        params = []
        ### tms: {zoom}, {x}, {y} or {-y}
        if source['properties']['type'] == "tms":
            try:
                source['properties']['max_zoom']
            except KeyError:
                logger.warning("Missing max_zoom parameter in {}".format(filename))
            try:
                if source['properties']['min_zoom'] == 0:
                    logger.warning("Useless min_zoom parameter in {}".format(filename))
            except KeyError:
                pass
            params = ["{zoom}", "{x}", "{y}"]
        ### wms: {proj}, {bbox}, {width}, {height}
        elif source['properties']['type'] == "wms":
            params = ["{proj}", "{bbox}", "{width}", "{height}"]
        missingparams = [x for x in params if x not in source['properties']['url'].replace("{-y}", "{y}")]
        if missingparams:
            raise ValidationError("Missing parameter in {}: {}".format(filename, missingparams))

        # If we're not 'default' we must have a geometry.
        # The geometry itself is validated by jsonschema
        try:
            source['properties']['default']
        except KeyError:
            try:
                source['geometry']['type'] == "Polygon"
            except (TypeError, KeyError):
                raise ValidationError("{} should have a valid geometry or be marked default".format(filename))



>>>>>>> Linter improvements: see #428
    except Exception as e:
        borkenbuild = True
        logger.exception("Error in {} : {}".format(filename, e))
if spacesave > 0:
    logger.warning("Disembedding all icons would save {} KB".format(round(spacesave/1024.0, 2)))
if borkenbuild:
    raise SystemExit(1)

