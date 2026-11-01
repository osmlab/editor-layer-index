"""Validate TMS capabilities parsing."""

import os

import pytest

from eli.libeli import tmshelper
from eli.libeli.eliutils import BoundingBox


@pytest.fixture(scope="function", name="tilemapresource")
def tilemapresource_fixture() -> tmshelper.TileMapResource:
    data_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "data", "tms", "tilemapresource.xml"
    )
    with open(data_path, encoding="utf-8") as f:
        xml = f.read()
    return tmshelper.TileMapResource(xml)


def test_bounding_box(tilemapresource: tmshelper.TileMapResource) -> None:
    """Test if bounding box is parsed"""
    assert tilemapresource.tile_map is not None
    assert tilemapresource.tile_map.bbox84 == BoundingBox(
        west=-180.0, east=180.0, south=-90.0, north=90.0
    )


def test_min_max_zoom_levels(tilemapresource: tmshelper.TileMapResource) -> None:
    """Test if min / max zoom levels are parsed"""
    assert tilemapresource.get_min_max_zoom_level() == (0, 3)


def test_crs(tilemapresource: tmshelper.TileMapResource) -> None:
    """Test if crs is parsed"""
    assert tilemapresource.tile_map is not None
    assert tilemapresource.tile_map.crs == "EPSG:4326"
