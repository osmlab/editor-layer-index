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