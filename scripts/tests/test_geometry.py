import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from libeli.geometry import validate_polygon_coordinates


RING = [[0, 0], [1, 0], [1, 1], [0, 0]]


@pytest.mark.parametrize("geometry", [
    {"type": "Polygon", "coordinates": [RING]},
    {"type": "Polygon", "coordinates": [RING, RING]},
    {"type": "MultiPolygon", "coordinates": [[RING], [RING]]},
    {"type": "Polygon", "coordinates": [[[x, y, 0] for x, y in RING]]},
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


def test_source_check_rejects_unclosed_ring(tmp_path):
    """Exercise the same source checker as PR CI; Shapely alone closes this ring."""
    root = Path(__file__).resolve().parents[2]
    source = {
        "type": "Feature",
        "properties": {
            "id": "ring-check", "name": "Ring check", "type": "tms", "country_code": "DE",
            "url": "https://example.com/{zoom}/{x}/{y}.png",
        },
        "geometry": {"type": "Polygon", "coordinates": [RING[:-1] + [[0, 1]]]},
    }
    path = tmp_path / "unclosed.geojson"
    path.write_text(json.dumps(source))
    result = subprocess.run([sys.executable, "scripts/check.py", str(path)], cwd=root, capture_output=True, text=True)
    assert result.returncode == 1
    assert "Polygon rings must be explicitly closed" in result.stderr
