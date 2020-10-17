import argparse
import io
import json
import glob
import os
from jsonschema import ValidationError
from shapely.geometry import shape, mapping, Polygon, MultiPolygon, GeometryCollection
from shapely.ops import cascaded_union
# make_valid requires shapely >= 1.8.0
from shapely.validation import explain_validity, make_valid


parser = argparse.ArgumentParser(description='Convert invalid Polygons to Polygons and Multièolygons')
parser.add_argument('sources',
                    metavar='sources',
                    type=str,
                    nargs='?',
                    help='relative path to sources directory',
                    default="sources")

args = parser.parse_args()
sources_directory = args.sources


def dict_raise_on_duplicates(ordered_pairs):
    """Reject duplicate keys."""
    d = {}
    for k, v in ordered_pairs:
        if k in d:
            raise ValidationError("duplicate key: %r" % (k,))
        else:
            d[k] = v
    return d


for filename in glob.glob(os.path.join(sources_directory, '**', '*.geojson'), recursive=True):
    print(filename)

    source = json.load(io.open(filename, encoding='utf-8'), object_pairs_hook=dict_raise_on_duplicates)

    if source['geometry'] is None:
        continue
    geom = shape(source['geometry'])

    if not geom.is_valid:
        print("Not valid: {}".format(filename))
        reason = explain_validity(geom)
        print("Reason: {}".format(reason))
        geom = make_valid(geom)

        # Keep only polygons and multipolygons
        if isinstance(geom, GeometryCollection):
            keep = []
            for g in geom.geoms:
                if isinstance(g, Polygon) or isinstance(g, MultiPolygon):
                    keep.append(g)
            geom = cascaded_union(keep)

        if isinstance(geom, Polygon) or isinstance(geom, MultiPolygon):
            source['geometry'] = mapping(geom)
            print("Overwrite: {}".format(filename))
            with open(filename, 'w', encoding='utf-8') as out:
                json.dump(source, out, indent=4, sort_keys=False, ensure_ascii=False)
                out.write("\n")

        else:
            print("No transformation is possible")
