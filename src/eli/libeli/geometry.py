"""Validate raw GeoJSON positions before geometry libraries can repair them."""

import math

from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import polylabel

from eli.common import JSON


def interior_test_point(geometry: BaseGeometry) -> Point:
    """Approximate the pole of inaccessibility, respecting holes and islands.

    Distances here are only for choosing a safe sample in lon/lat coordinates;
    they are not geodesic measurements. A relative tolerance bounds the work.
    """
    if (
        not isinstance(geometry, (Polygon, MultiPolygon))
        or geometry.is_empty
        or not geometry.is_valid
    ):
        raise ValueError("Test point requires a nonempty, valid coverage polygon")
    polygon = (
        max(geometry.geoms, key=lambda part: part.area)
        if isinstance(geometry, MultiPolygon)
        else geometry
    )
    west, south, east, north = polygon.bounds
    point = polylabel(polygon, tolerance=max(east - west, north - south) / 1000)
    return point if polygon.contains(point) else polygon.representative_point()


def validate_polygon_coordinates(geometry: JSON, *, check_winding: bool = False) -> None:
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
        for ring_index, ring in enumerate(polygon):
            if not isinstance(ring, list) or len(ring) < 4:
                raise ValueError("Polygon rings must contain at least four positions")
            for position in ring:
                validate_position(position)
            if any(a == b for a, b in zip(ring, ring[1:])):
                raise ValueError("Polygon rings must not contain consecutive duplicate positions")
            if ring[0] != ring[-1]:
                raise ValueError("Polygon rings must be explicitly closed")
            if check_winding:
                validate_ring_winding(ring, ring_index == 0)


def validate_ring_winding(ring: list[list[float]], exterior: bool) -> None:
    """Check orientation independently from topological validity."""
    signed_area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:]))
    if (exterior and signed_area < 0) or (not exterior and signed_area > 0):
        raise ValueError("Ring orientation must follow GeoJSON RFC7946 (CCW exterior, CW holes)")


def validate_position(position: object) -> None:
    """Reject malformed coordinates before GEOS can repair them."""
    if not isinstance(position, list) or len(position) != 2:
        raise ValueError("Positions must contain exactly longitude and latitude (2D coordinates)")
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in position):
        raise ValueError("Position coordinates must be finite numbers")
    if not (-180 <= position[0] <= 180 and -90 <= position[1] <= 90):
        raise ValueError("Longitude or latitude outside valid bounds")
