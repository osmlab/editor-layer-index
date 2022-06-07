import os
from typing import Any, Dict, List, Optional

import pytest
from libeli.eliutils import BoundingBox, clean_projections, search_encoding


@pytest.mark.parametrize(
    "epsg_codes,bbox,expected_clean_codes",
    [
        # Filter EPSG:3857 alias
        (["EPSG:900913", "EPSG:3857"], None, ["EPSG:3857"]),
        (["EPSG:900913"], None, ["EPSG:900913"]),
        (["EPSG:900913", "EPSG:3857", "EPSG:102100", "EPSG:3785"], None, ["EPSG:3857"]),
        (
            ["EPSG:2177", "EPSG:2180", "EPSG:3857", "EPSG:4326", "EPSG:900913"],
            None,
            ["EPSG:2177", "EPSG:2180", "EPSG:3857", "EPSG:4326"],
        ),
        # CRS:84 is considered to be valid
        (["CRS:84"], None, ["CRS:84"]),
        # Unknown CRS
        (["AUTO"], None, []),
        # EPSG:21781 area of use does not intersect with bounding box
        (["EPSG:21781", "EPSG:3857"], BoundingBox(west=-5, east=0, south=-5, north=5), ["EPSG:3857"]),
        # EPSG:21781 area of use does intersect with bounding box
        (["EPSG:21781", "EPSG:3857"], BoundingBox(west=0, east=10, south=40, north=50), ["EPSG:21781", "EPSG:3857"]),
        # EPSG:21781 area of use does intersect with bounding box
        (
            ["EPSG:21781", "EPSG:3857"],
            [BoundingBox(west=-5, east=0, south=-5, north=5), BoundingBox(west=0, east=10, south=40, north=50)],
            ["EPSG:21781", "EPSG:3857"],
        ),
        # EPSG:31464 is deprecated
        (["EPSG:31464"], BoundingBox(west=11.788898, east=15.08686, south=50.150604, north=51.72093), []),
    ],
)
def test_clean_projections(
    epsg_codes: List[str], bbox: Optional[BoundingBox | List[BoundingBox]], expected_clean_codes: List[str]
):
    """Test removal of EPSG alias and unknown coordinates"""
    clean_codes = clean_projections(epsg_codes, bbox)
    assert len(clean_codes) == len(expected_clean_codes)
    assert set(clean_codes) == set(expected_clean_codes)


def test_search_encoding():
    data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data", "tms", "tilemapresource.xml")
    with open(data_path, "r") as f:
        xml = f.read()
    assert search_encoding(xml) == "UTF-8"
