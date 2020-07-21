import io
import json
import glob

from jsonschema import ValidationError
from shapely.geometry import shape, mapping, Polygon, MultiPolygon, GeometryCollection
from shapely.ops import cascaded_union
from shapely.validation import explain_validity, make_valid


def dict_raise_on_duplicates(ordered_pairs):
    """Reject duplicate keys."""
    d = {}
    for k, v in ordered_pairs:
        if k in d:
            raise ValidationError("duplicate key: %r" % (k,))
        else:
            d[k] = v
    return d


for filename in glob.glob('../sources/**/*.geojson', recursive=True):

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
            with open(filename, 'w') as f:
                json.dump(source, f, ensure_ascii=False, separators=(',', ':'), indent=4, sort_keys=True)

        else:
            print("No transformation is possible")
