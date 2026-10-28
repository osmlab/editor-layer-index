"""Validate raw GeoJSON coordinates and source-checker diagnostics."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from eli.common import JSON
from eli.libeli.geometry import validate_polygon_coordinates

RING = [[0, 0], [1, 0], [1, 1], [0, 0]]


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
