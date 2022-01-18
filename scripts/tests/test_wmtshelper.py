import os
from typing import Dict, List, Optional

import pytest
from _pytest.fixtures import SubRequest
from libeli import wmtshelper


@pytest.fixture(scope="function")
def wmts_capabilities(request: SubRequest) -> wmtshelper.WMTSCapabilities:
    wmts_test: str = request.param  # type: ignore

    filename: Optional[str] = None
    if wmts_test == "simple":
        filename = "wmtsGetCapabilities_response_OSM.xml"
    elif wmts_test == "rest":
        filename = "wmtsGetCapabilities_response_RESTful.xml"
    elif wmts_test == "default":
        filename = "wmtsGetCapabilities_response.xml"
    if filename is None:
        raise RuntimeError("Unknown test case.")

    data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data", "wmts", filename)
    with open(data_path) as f:
        xml = f.read()
    return wmtshelper.WMTSCapabilities(xml)


@pytest.mark.parametrize(
    "wmts_capabilities, expected",
    [
        ("default", ["coastlines"]),
        ("rest", ["etopo2", "AdminBoundaries"]),
        ("simple", ["OSM"]),
    ],
    indirect=["wmts_capabilities"],
)
def test_layers(wmts_capabilities: wmtshelper.WMTSCapabilities, expected: List[str]):
    """Test if layers are parsed"""
    assert len(wmts_capabilities.layers) == len(expected)
    for layer in expected:
        assert layer in wmts_capabilities.layers


@pytest.mark.parametrize(
    "wmts_capabilities, expected",
    [
        ("default", {"coastlines": ["urn:ogc:def:crs:OGC:1.3:CRS84"]}),
        ("rest", {"etopo2": ["urn:ogc:def:crs:OGC:1.3:CRS84"], "AdminBoundaries": ["urn:ogc:def:crs:OGC:1.3:CRS84"]}),
        ("simple", {"OSM": ["urn:ogc:def:crs:EPSG::3857"]}),
    ],
    indirect=["wmts_capabilities"],
)
def test_layers_crs(wmts_capabilities: wmtshelper.WMTSCapabilities, expected: Dict[str, List[str]]):
    """Test layer crs"""
    for layer, supported_crs in expected.items():
        layer_crs = wmts_capabilities.supported_crs(layer)
        assert len(supported_crs) == len(layer_crs)
        for crs in supported_crs:
            assert crs in layer_crs


@pytest.mark.parametrize(
    "wmts_capabilities, expected",
    [
        ("default", []),
        ("rest", []),
        ("simple", ["OSM"]),
    ],
    indirect=["wmts_capabilities"],
)
def test_tms_compatible_layers(wmts_capabilities: wmtshelper.WMTSCapabilities, expected: List[str]):
    """Test tms compatible layers"""
    tms_compatible_layers = wmts_capabilities.tms_compatible_layers()
    assert len(tms_compatible_layers) == len(expected)
    for layer in expected:
        assert layer in tms_compatible_layers


@pytest.mark.parametrize(
    "wmts_capabilities, expected",
    [
        ("simple", {"OSM": {"http://tile.openstreetmap.org/{zoom}/{x}/{y}.png"}}),
    ],
    indirect=["wmts_capabilities"],
)
def test_generate_tms_url(wmts_capabilities: wmtshelper.WMTSCapabilities, expected: Dict[str, str]):
    """Test generation of tms url for simpleProfileTile compatible layers"""
    for layer, expected_tms_url in expected.items():
        assert wmts_capabilities.get_tms_compatible_urls(layer) == expected_tms_url
