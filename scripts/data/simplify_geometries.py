import glob
import gzip
import json
import os
from collections import defaultdict
import fiona
from pyproj import Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform, cascaded_union

transformer = Transformer.from_crs("epsg:4326", "epsg:3857", always_xy=True)
transformer_back = Transformer.from_crs("epsg:3857", "epsg:4326", always_xy=True)

countries = defaultdict(list)

for file_name in glob.glob(os.path.join("download_osm_boundaries_com", "*.geojson.gz")):
    with gzip.open(file_name) as f:
        data = json.load(f)

    for feature in data["features"]:
        if "ISO3166-1" in feature["properties"]["all_tags"]:
            isocode = feature["properties"]["all_tags"]["ISO3166-1"]
            geom = shape(feature["geometry"])
            geom_3857 = transform(transformer.transform, geom)
            geom_3857_simplified = geom_3857.buffer(1000).simplify(250).buffer(-1000)
            geom_simplified = transform(
                transformer_back.transform, geom_3857_simplified
            )
            countries[isocode].append(geom_simplified)

schema = {"geometry": "Any", "properties": {"ISO3166-1": "str"}}
with fiona.open(
    "countries.geojson",
    mode="w",
    driver="GeoJSON",
    schema=schema,
    COORDINATE_PRECISION=5,
) as sink:
    for isocode, shapes in countries.items():
        geom = cascaded_union(shapes)
        feature = {"geometry": mapping(geom), "properties": {"ISO3166-1": isocode}}
        sink.write(feature)
