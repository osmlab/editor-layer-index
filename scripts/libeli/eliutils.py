import pyproj
from pyproj.transformer import Transformer
from shapely.geometry import shape, Polygon
from shapely.ops import cascaded_union


def parse_eli_geometry(geometry):
    """ELI currently uses a geometry encoding not compatible with geojson.
    Create valid geometries from this format."""
    _geom = shape(geometry)
    geoms = [Polygon(_geom.exterior.coords)]
    for ring in _geom.interiors:
        geoms.append(Polygon(ring.coords))
    return cascaded_union(geoms)


epsg_3857_alias = set(
    [f"EPSG:{epsg}" for epsg in [900913, 3587, 54004, 41001, 102113, 102100, 3785]]
    + ["OSGEO:41001", "ESRI:102113", "ESRI:102100"]
)

# List of not deprecated EPSG codes
valid_epsgs = set(["CRS:84"])
for pj_type in pyproj.enums.PJType:
    valid_epsgs.update(
        map(
            lambda x: f"EPSG:{x}",
            pyproj.get_codes("EPSG", pj_type, allow_deprecated=False),
        )
    )

# EPSG:3857 alias are valid if server does not support EPSG:3857
valid_epsgs.update(epsg_3857_alias)


transformers = {}


def get_transformer(crs_from, crs_to):
    """Cache transformer objects"""
    key = (crs_from, crs_to)
    if key not in transformers:
        transformers[key] = Transformer.from_crs(crs_from, crs_to, always_xy=True)
    return transformers[key]
