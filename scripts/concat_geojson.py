import argparse
import glob
import json
import os
from datetime import datetime
from shapely.geometry import shape, Polygon, MultiPolygon, mapping

parser = argparse.ArgumentParser(description='Concatenate sources to single FeatureCollection geojson.')
parser.add_argument('sources',
                    metavar='sources',
                    type=str,
                    nargs='?',
                    help='relative path to sources directory',
                    default="sources")

args = parser.parse_args()
sources_directory = args.sources


def convert_to_legacy_geometry(source):
    """ Convert from geojson geometries to legacy Polygon encoding
     - Drop interior rings of Polygons
     - Encode MultiPolygons as interior rings
     """
    if source['geometry'] is not None:
        geom = shape(source['geometry'])
        if isinstance(geom, Polygon):
            # Ignore all interior rings (=holes)
            new_geom = Polygon(shell=geom.exterior)
        elif isinstance(geom, MultiPolygon):
            # Ignore all interior rings (=holes)
            # Encode exterior rings as interior rings
            rings = [g.exterior for g in geom]
            new_geom = Polygon(shell=rings[0], holes=rings[1:])
        else:
            raise RuntimeError("Unsupported geometry type: {}".format(type(geom)))
        source['geometry'] = mapping(new_geom)
    return source


source_features_legacy = []
source_features = []
for filename in glob.glob(os.path.join(sources_directory, '**', '*.geojson'), recursive=True):
    with open(filename, encoding='utf-8') as f:
        source = json.load(f, parse_float=lambda x: round(float(x), 5))
        source_features.append(source)
        legacy_source = convert_to_legacy_geometry(source)
        source_features_legacy.append(legacy_source)

generated = '{:%Y-%m-%d %H:%M:%S}'.format(datetime.utcnow())
version = "1.0"

collection_legacy = {
    "type": "FeatureCollection",
    "meta": {
        "generated": generated,
        "format_version": version
    },
    "features": source_features_legacy
}
