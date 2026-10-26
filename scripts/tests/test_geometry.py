import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from libeli.geometry import interior_test_point, validate_polygon_coordinates
from shapely.geometry import MultiPolygon, Point, Polygon, box


def test_pole_of_inaccessibility():
    polygon = box(0, 0, 10, 10)
    assert interior_test_point(polygon).distance(Point(5, 5)) < 0.01


def test_interior_point_respects_holes_and_concavity():
    polygon = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)], holes=[box(3, 3, 7, 7).exterior.coords])
    assert polygon.contains(interior_test_point(polygon))
    concave = Polygon([(0, 0), (8, 0), (8, 1), (1, 1), (1, 8), (0, 8), (0, 0)])
    assert concave.contains(interior_test_point(concave))


def test_interior_point_uses_largest_component():
    large = box(20, 20, 30, 30)
    geometry = MultiPolygon([box(0, 0, 1, 1), large])
    assert large.contains(interior_test_point(geometry))


@pytest.mark.parametrize("polygon", [Polygon(), Polygon([(0, 0), (1, 1), (0, 1), (1, 0), (0, 0)])])
def test_invalid_test_geometry(polygon):
    with pytest.raises(ValueError):
        interior_test_point(polygon)


RING = [[0, 0], [1, 0], [1, 1], [0, 0]]


@pytest.mark.parametrize("geometry", [
    {"type": "Polygon", "coordinates": [RING]},
    {"type": "Polygon", "coordinates": [RING, RING]},
    {"type": "MultiPolygon", "coordinates": [[RING], [RING]]},
])
def test_valid_rings(geometry):
    validate_polygon_coordinates(geometry)


@pytest.mark.parametrize("ring", [
    [], RING[:3], RING[:-1] + [[0, 1]],
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
])
@pytest.mark.parametrize("location", ["exterior", "interior", "multipolygon"])
def test_invalid_rings(ring, location):
    geometry = {"type": "Polygon", "coordinates": [copy.deepcopy(RING)]}
    if location == "exterior":
        geometry["coordinates"] = [ring]
    elif location == "interior":
        geometry["coordinates"].append(ring)
    else:
        geometry = {"type": "MultiPolygon", "coordinates": [[RING], [ring]]}
    with pytest.raises(ValueError):
        validate_polygon_coordinates(geometry)


@pytest.mark.parametrize("geometry", [
    {"type": "Polygon", "coordinates": []},
    {"type": "MultiPolygon", "coordinates": []},
    {"type": "MultiPolygon", "coordinates": [[]]},
    {"type": "Polygon"},
])
def test_missing_rings(geometry):
    with pytest.raises(ValueError):
        validate_polygon_coordinates(geometry)


@pytest.mark.parametrize("ring, message", [
    (RING[:-1] + [[0, 1]], "Polygon rings must be explicitly closed"),
    ([[x, y, 0] for x, y in RING], "Positions must contain exactly longitude and latitude"),
])
def test_source_check_rejects_invalid_ring(tmp_path, ring, message):
    """Exercise the same source checker as PR CI."""
    root = Path(__file__).resolve().parents[2]
    source = {
        "type": "Feature",
        "properties": {
            "id": "ring-check", "name": "Ring check", "type": "tms", "country_code": "DE",
            "url": "https://example.com/{zoom}/{x}/{y}.png",
        },
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }
    path = tmp_path / "invalid.geojson"
    path.write_text(json.dumps(source))
    result = subprocess.run([sys.executable, "scripts/check.py", str(path)], cwd=root, capture_output=True, text=True)
    assert result.returncode == 1
    assert message in result.stderr
