"""Validate raw GeoJSON positions before geometry libraries can repair them."""

import math

from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import polylabel


def interior_test_point(geometry: Polygon | MultiPolygon) -> Point:
    """Approximate the pole of inaccessibility in lon/lat coordinates.

    Use the largest component of a MultiPolygon and respect interior holes.
    The relative tolerance limits work even for large or detailed coverages.
    This selects an interior sample, not a geodesic distance measurement.
    """
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError("Test point requires a nonempty, valid coverage polygon")
    polygon = max(geometry.geoms, key=lambda part: part.area) if isinstance(geometry, MultiPolygon) else geometry
    west, south, east, north = polygon.bounds
    point = polylabel(polygon, tolerance=max(east - west, north - south) / 1000)
    # Very thin polygons can be narrower than the approximation tolerance.
    return point if polygon.contains(point) else polygon.representative_point()


def validate_polygon_coordinates(geometry):
    """Check every exterior/interior ring uses two-dimensional coordinates."""
    polygons = geometry.get("coordinates")
    if geometry.get("type") == "Polygon":
        polygons = [polygons]
    elif geometry.get("type") != "MultiPolygon":
        raise ValueError("Expected Polygon or MultiPolygon geometry")
    if not isinstance(polygons, list) or not polygons:
        raise ValueError("Geometry must contain at least one polygon")
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            raise ValueError("Polygon must contain at least one ring")
        for ring in polygon:
            if not isinstance(ring, list) or len(ring) < 4:
                raise ValueError("Polygon rings must contain at least four positions")
            for position in ring:
                if not isinstance(position, list) or len(position) != 2:
                    raise ValueError("Positions must contain exactly longitude and latitude (2D coordinates)")
                if any(type(value) not in (int, float) or not math.isfinite(value) for value in position):
                    raise ValueError("Position coordinates must be finite numbers")
                if not (-180 <= position[0] <= 180 and -90 <= position[1] <= 90):
                    raise ValueError("Longitude or latitude outside valid bounds")
            if ring[0] != ring[-1]:
                raise ValueError("Polygon rings must be explicitly closed")
