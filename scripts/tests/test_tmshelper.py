import os

import pytest
from libeli import tmshelper
from libeli.eliutils import BoundingBox


@pytest.fixture(scope="function")
def tilemapresource() -> tmshelper.TileMapResource:
    data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data", "tms", "tilemapresource.xml")
    with open(data_path) as f:
        xml = f.read()
    return tmshelper.TileMapResource(xml)


def test_bounding_box(tilemapresource: tmshelper.TileMapResource):
    """Test if bounding box is parsed"""
    assert tilemapresource.tile_map is not None
    assert tilemapresource.tile_map.bbox84 == BoundingBox(west=-180.0, east=180.0, south=-180.0, north=90.0)


def test_min_max_zoom_levels(tilemapresource: tmshelper.TileMapResource):
    """Test if min / max zoom levels are parsed"""
    assert tilemapresource.get_min_max_zoom_level() == (0, 3)


def test_crs(tilemapresource: tmshelper.TileMapResource):
    """Test if crs is parsed"""
    assert tilemapresource.tile_map is not None
    assert tilemapresource.tile_map.crs == "EPSG:4326"
