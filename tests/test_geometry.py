"""Validate raw GeoJSON coordinates and source-checker diagnostics."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from shapely.geometry import MultiPolygon, Point, Polygon, box

from eli.common import JSON
from eli.libeli.geometry import interior_test_point, validate_polygon_coordinates

RING = [[0, 0], [1, 0], [1, 1], [0, 0]]


def test_pole_of_inaccessibility() -> None:
    assert interior_test_point(box(0, 0, 10, 10)).distance(Point(5, 5)) < 0.01
    large = box(20, 20, 30, 30)
    assert large.contains(interior_test_point(MultiPolygon([box(0, 0, 1, 1), large])))


def test_interior_point_respects_holes_and_concavity() -> None:
    polygon = Polygon(box(0, 0, 10, 10).exterior.coords, holes=[box(3, 3, 7, 7).exterior.coords])
    assert polygon.contains(interior_test_point(polygon))
    concave = Polygon([(0, 0), (8, 0), (8, 1), (1, 1), (1, 8), (0, 8), (0, 0)])
    assert concave.contains(interior_test_point(concave))


@pytest.mark.parametrize("polygon", [Polygon(), Polygon([(0, 0), (1, 1), (0, 1), (1, 0), (0, 0)])])
def test_invalid_test_geometry(polygon: Polygon) -> None:
    with pytest.raises(ValueError):
        interior_test_point(polygon)


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "Polygon", "coordinates": [RING]},
        {"type": "Polygon", "coordinates": [RING, RING]},
        {"type": "MultiPolygon", "coordinates": [[RING], [RING]]},
    ],
)
def test_valid_rings(geometry: JSON) -> None:
    validate_polygon_coordinates(geometry)


@pytest.mark.parametrize(
    "ring",
    [
        [],
        RING[:3],
        RING[:-1] + [[0, 1]],
        [[0, 0], [float("nan"), 0], [1, 1], [0, 0]],
        [[0, 0], [1, float("inf")], [1, 1], [0, 0]],
        [[0, 0], [181, 0], [1, 1], [0, 0]],
        [[0, 0], [1, -91], [1, 1], [0, 0]],
        [[0, 0], [True, 0], [1, 1], [0, 0]],
        [[0, 0], ["1", 0], [1, 1], [0, 0]],
        [[0, 0], [1], [1, 1], [0, 0]],
        [[x, y, 0] for x, y in RING],
        [[x, y, 0, 0] for x, y in RING],
        [[0, 0], [1, 0, float("nan")], [1, 1], [0, 0]],
    ],
)
@pytest.mark.parametrize("location", ["exterior", "interior", "multipolygon"])
def test_invalid_rings(ring: list[list[object]], location: str) -> None:
    geometry: JSON = {"type": "Polygon", "coordinates": [copy.deepcopy(RING)]}
    if location == "exterior":
        geometry["coordinates"] = [ring]
    elif location == "interior":
        geometry["coordinates"].append(ring)
    else:
        geometry = {"type": "MultiPolygon", "coordinates": [[RING], [ring]]}
    with pytest.raises(ValueError):
        validate_polygon_coordinates(geometry)


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "Polygon", "coordinates": []},
        {"type": "MultiPolygon", "coordinates": []},
        {"type": "MultiPolygon", "coordinates": [[]]},
        {"type": "Polygon"},
    ],
)
def test_missing_rings(geometry: JSON) -> None:
    with pytest.raises(ValueError):
        validate_polygon_coordinates(geometry)


@pytest.mark.parametrize(
    "ring, message",
    [
        (RING[:-1] + [[0, 1]], "Polygon rings must be explicitly closed"),
        ([[x, y, 0] for x, y in RING], "Positions must contain exactly longitude and latitude"),
    ],
)
def test_source_check_rejects_invalid_ring(
    tmp_path: Path, ring: list[list[object]], message: str
) -> None:
    """Exercise the same source checker as PR CI."""
    root = Path(__file__).resolve().parents[1]
    source = {
        "type": "Feature",
        "properties": {
            "id": "ring-check",
            "name": "Ring check",
            "type": "tms",
            "country_code": "DE",
            "url": "https://example.com/{zoom}/{x}/{y}.png",
        },
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }
    path = tmp_path / "invalid.geojson"
    path.write_text(json.dumps(source))
    result = subprocess.run(
        [sys.executable, "-m", "eli", "check", str(path)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert message in result.stderr


@pytest.mark.parametrize("ring", [RING[::-1], [RING[0], *RING]])
def test_winding_and_duplicate_vertices_are_offline_errors(ring: list[list[int]]) -> None:
    with pytest.raises(ValueError, match="orientation|duplicate"):
        validate_polygon_coordinates({"type": "Polygon", "coordinates": [ring]}, check_winding=True)


def test_hole_winding_is_checked() -> None:
    with pytest.raises(ValueError, match="orientation"):
        validate_polygon_coordinates(
            {"type": "Polygon", "coordinates": [RING, RING]}, check_winding=True
        )
