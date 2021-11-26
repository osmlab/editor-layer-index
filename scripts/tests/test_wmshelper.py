import os
from typing import Dict, List
from _pytest.fixtures import SubRequest

import pytest
from libeli import wmshelper
from libeli.eliutils import BoundingBox


@pytest.fixture(scope="function")
def wms_capabilities(request: SubRequest) -> wmshelper.WMSCapabilities:
    wms_version: str = request.param  # type: ignore
    data_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "data", "wms", f"capabilities_{wms_version.replace('.', '_')}.xml"
    )
    with open(data_path) as f:
        xml = f.read()
    return wmshelper.WMSCapabilities(xml)


@pytest.mark.parametrize(
    "wms_capabilities, layer_names",
    [
        (
            "1.3.0",
            [
                "ROADS_RIVERS",
                "ROADS_1M",
                "RIVERS_1M",
                "Clouds",
                "Temperature",
                "Pressure",
                "ozone_image",
                "population",
            ],
        ),
        (
            "1.1.1",
            [
                "ROADS_RIVERS",
                "ROADS_1M",
                "RIVERS_1M",
                "Clouds",
                "Temperature",
                "Pressure",
                "ozone_image",
                "population",
            ],
        ),
        (
            "1.1.0",
            [
                "ROADS_RIVERS",
                "ROADS_1M",
                "RIVERS_1M",
                "Clouds",
                "Temperature",
                "Pressure",
                "ozone_image",
                "population",
            ],
        ),
        (
            "1.0.0",
            ["wmt_graticule", "ROADS_RIVERS", "ROADS_1M", "RIVERS_1M", "Clouds", "Temperature", "Pressure"],
        ),
    ],
    indirect=["wms_capabilities"],
)
def test_layers(wms_capabilities: wmshelper.WMSCapabilities, layer_names: List[str]):
    """Test if layers can be parsed"""
    assert len(wms_capabilities.layers.keys()) == len(layer_names)
    for layer_name in layer_names:
        assert layer_name in wms_capabilities.layers


@pytest.mark.parametrize(
    "wms_capabilities, formats",
    [
        (
            "1.3.0",
            ["image/gif", "image/png", "image/jpeg"],
        ),
        (
            "1.1.1",
            ["image/gif", "image/png", "image/jpeg"],
        ),
        (
            "1.1.0",
            ["image/gif", "image/png", "image/jpeg"],
        ),
        (
            "1.0.0",
            ["SGI", "GIF", "JPEG", "PNG", "WebCGM", "SVG"],
        ),
    ],
    indirect=["wms_capabilities"],
)
def test_server_formats(wms_capabilities: wmshelper.WMSCapabilities, formats: List[str]):
    """Test if formats are correctly parsed"""
    assert len(wms_capabilities.formats) == len(formats)
    for format in formats:
        assert format in wms_capabilities.formats


@pytest.mark.parametrize(
    "crs, bounds, wms_version,expected",
    [
        ("EPSG:4326", BoundingBox(west=-180.0, east=180.0, south=90.0, north=90.0), "1.3.0", "90.0,-180.0,90.0,180.0"),
        ("CRS:84", BoundingBox(west=-180.0, east=180.0, south=90.0, north=90.0), "1.3.0", "-180.0,90.0,180.0,90.0"),
        ("CRS:84", BoundingBox(west=-180.0, east=180.0, south=90.0, north=90.0), "1.1.1", "-180.0,90.0,180.0,90.0"),
        ("EPSG:4326", BoundingBox(west=-180.0, east=180.0, south=90.0, north=90.0), "1.1.1", "-180.0,90.0,180.0,90.0"),
        ("EPSG:4326", BoundingBox(west=-180.0, east=180.0, south=90.0, north=90.0), "1.1.0", "-180.0,90.0,180.0,90.0"),
        ("EPSG:4326", BoundingBox(west=-180.0, east=180.0, south=90.0, north=90.0), "1.0.0", "-180.0,90.0,180.0,90.0"),
        (
            "EPSG:2056",
            BoundingBox(west=5.96, east=10.49, south=45.82, north=47.81),
            "1.3.0",
            "2485071.58,1075346.31,2828515.82,1299941.79",
        ),
        (
            "EPSG:2056",
            BoundingBox(west=5.96, east=10.49, south=45.82, north=47.81),
            "1.1.1",
            "2485071.58,1075346.31,2828515.82,1299941.79",
        ),
    ],
)
def test_get_bbox(crs: str, bounds: BoundingBox, wms_version: str, expected: str):
    """Test bbox ordering and re-projection"""
    assert expected == wmshelper.get_bbox(crs, bounds, wms_version)


@pytest.mark.parametrize(
    "wms_capabilities, expected",
    [
        (
            "1.3.0",
            {
                "ROADS_RIVERS": ["USGS"],
                "ROADS_1M": ["ATLAS", "USGS"],
                "RIVERS_1M": ["USGS"],
                "Clouds": [],
                "Temperature": [],
                "Pressure": [],
                "ozone_image": [],
                "population": [],
            },
        ),
        (
            "1.1.1",
            {
                "ROADS_RIVERS": ["USGS"],
                "ROADS_1M": ["ATLAS", "USGS"],
                "RIVERS_1M": ["USGS"],
                "Clouds": [],
                "Temperature": [],
                "Pressure": [],
                "ozone_image": [],
                "population": [],
            },
        ),
        (
            "1.1.0",
            {
                "ROADS_RIVERS": ["USGS"],
                "ROADS_1M": ["ATLAS", "USGS"],
                "RIVERS_1M": ["USGS"],
                "Clouds": [],
                "Temperature": [],
                "Pressure": [],
                "ozone_image": [],
                "population": [],
            },
        ),
        (
            "1.0.0",
            {
                "wmt_graticule": ["off", "on"],
                "ROADS_RIVERS": ["USGS Topo"],
                "ROADS_1M": ["Rand McNally", "USGS Topo"],
                "RIVERS_1M": ["USGS Topo"],
                "Clouds": ["default"],
                "Temperature": ["default"],
                "Pressure": ["default"],
            },
        ),
    ],
    indirect=["wms_capabilities"],
)
def test_layer_styles(wms_capabilities: wmshelper.WMSCapabilities, expected: Dict[str, List[str]]):
    """Test if styles of layers are parsed"""
    for layer, expected_styles in expected.items():
        assert len(expected_styles) == len(wms_capabilities.layers[layer].styles)
        for style in expected_styles:
            assert style in wms_capabilities.layers[layer].styles


@pytest.mark.parametrize(
    "wms_capabilities, expected",
    [
        (
            "1.3.0",
            {
                "ROADS_RIVERS": BoundingBox(west=-71.63, east=-70.78, south=41.75, north=42.90),
                "ROADS_1M": BoundingBox(west=-71.63, east=-70.78, south=41.75, north=42.90),
                "RIVERS_1M": BoundingBox(west=-71.63, east=-70.78, south=41.75, north=42.90),
                "Clouds": BoundingBox(west=-180.0, east=180.0, south=-90.0, north=90.0),
                "Temperature": BoundingBox(west=-180.0, east=180.0, south=-90.0, north=90.0),
                "Pressure": BoundingBox(west=-180.0, east=180.0, south=-90.0, north=90.0),
                "ozone_image": BoundingBox(west=-180.0, east=180.0, south=-90.0, north=90.0),
                "population": BoundingBox(west=-180.0, east=180.0, south=-90.0, north=90.0),
            },
        ),
        (
            "1.1.1",
            {
                "ROADS_RIVERS": BoundingBox(west=-71.63, east=-70.78, south=41.75, north=42.90),
                "ROADS_1M": BoundingBox(west=-71.63, east=-70.78, south=41.75, north=42.90),
                "RIVERS_1M": BoundingBox(west=-71.63, east=-70.78, south=41.75, north=42.90),
                "Clouds": BoundingBox(west=-180.0, east=180.0, south=-90.0, north=90.0),
                "Temperature": BoundingBox(west=-180.0, east=180.0, south=-90.0, north=90.0),
                "Pressure": BoundingBox(west=-180.0, east=180.0, south=-90.0, north=90.0),
                "ozone_image": BoundingBox(west=-180.0, east=180.0, south=-90.0, north=90.0),
                "population": BoundingBox(west=-180.0, east=180.0, south=-90.0, north=90.0),
            },
        ),
        (
            "1.1.0",
            {
                "ROADS_RIVERS": BoundingBox(west=-71.63, east=-70.78, south=41.75, north=42.90),
                "ROADS_1M": BoundingBox(west=-71.63, east=-70.78, south=41.75, north=42.90),
                "RIVERS_1M": BoundingBox(west=-71.63, east=-70.78, south=41.75, north=42.90),
                "Clouds": BoundingBox(west=-180.0, east=180.0, south=-90.0, north=90.0),
                "Temperature": BoundingBox(west=-180.0, east=180.0, south=-90.0, north=90.0),
                "Pressure": BoundingBox(west=-180.0, east=180.0, south=-90.0, north=90.0),
                "ozone_image": BoundingBox(west=-180.0, east=180.0, south=-90.0, north=90.0),
                "population": BoundingBox(west=-180.0, east=180.0, south=-90.0, north=90.0),
            },
        ),
        (
            "1.0.0",
            {
                "wmt_graticule": BoundingBox(west=-180.0, east=180.0, south=-90.0, north=90.0),
                "ROADS_RIVERS": BoundingBox(west=-71.634696, east=-70.789798, south=41.754149, north=42.908459),
                "ROADS_1M": BoundingBox(west=-71.634696, east=-70.789798, south=41.754149, north=42.908459),
                "RIVERS_1M": BoundingBox(west=-71.634696, east=-70.789798, south=41.754149, north=42.908459),
                "Clouds": BoundingBox(west=-180.0, east=180.0, south=-90.0, north=90.0),
                "Temperature": BoundingBox(west=-180.0, east=180.0, south=-90.0, north=90.0),
                "Pressure": BoundingBox(west=-180.0, east=180.0, south=-90.0, north=90.0),
            },
        ),
    ],
    indirect=["wms_capabilities"],
)
def test_layer_boundingbox(wms_capabilities: wmshelper.WMSCapabilities, expected: Dict[str, BoundingBox]):
    """Test bounding box of layers"""
    for layer, bbox in expected.items():
        assert wms_capabilities.layers[layer].bbox == bbox


@pytest.mark.parametrize(
    "wms_capabilities, expected",
    [
        (
            "1.3.0",
            {
                "ROADS_RIVERS": ["CRS:84", "EPSG:26986"],
                "ROADS_1M": ["CRS:84", "EPSG:26986"],
                "RIVERS_1M": ["CRS:84", "EPSG:26986"],
                "Clouds": ["CRS:84"],
                "Temperature": ["CRS:84"],
                "Pressure": ["CRS:84"],
                "ozone_image": ["CRS:84"],
                "population": ["CRS:84"],
            },
        ),
        (
            "1.1.1",
            {
                "ROADS_RIVERS": ["EPSG:4326", "EPSG:26986"],
                "ROADS_1M": ["EPSG:4326", "EPSG:26986"],
                "RIVERS_1M": ["EPSG:4326", "EPSG:26986"],
                "Clouds": ["EPSG:4326"],
                "Temperature": ["EPSG:4326"],
                "Pressure": ["EPSG:4326"],
                "ozone_image": ["EPSG:4326"],
                "population": ["EPSG:4326"],
            },
        ),
        (
            "1.1.0",
            {
                "ROADS_RIVERS": ["EPSG:4326", "EPSG:26986"],
                "ROADS_1M": ["EPSG:4326", "EPSG:26986"],
                "RIVERS_1M": ["EPSG:4326", "EPSG:26986"],
                "Clouds": ["EPSG:4326"],
                "Temperature": ["EPSG:4326"],
                "Pressure": ["EPSG:4326"],
                "ozone_image": ["EPSG:4326"],
                "population": ["EPSG:4326"],
            },
        ),
        (
            "1.0.0",
            {
                "wmt_graticule": ["EPSG:4326"],
                "ROADS_RIVERS": ["EPSG:4326", "EPSG:26986"],
                "ROADS_1M": ["EPSG:4326", "EPSG:26986"],
                "RIVERS_1M": ["EPSG:4326", "EPSG:26986"],
                "Clouds": ["EPSG:4326"],
                "Temperature": ["EPSG:4326"],
                "Pressure": ["EPSG:4326"],
            },
        ),
    ],
    indirect=["wms_capabilities"],
)
def test_layer_crs(wms_capabilities: wmshelper.WMSCapabilities, expected: Dict[str, List[str]]):
    """Test bounding box of layers"""
    for layer, projections in expected.items():
        assert len(projections) == len(wms_capabilities.layers[layer].crs)
        for crs in projections:
            assert crs in wms_capabilities.layers[layer].crs


def test_wms_url():
    wms_url = wmshelper.WMSURL(
        "http://b-maps.com/map.cgi?VERSION=1.3.0&REQUEST=GetMap&CRS=CRS:84&BBOX=-97.105,24.913,-78.794,36.358&WIDTH=560&HEIGHT=350&LAYERS=BUILTUPA_1M,COASTL_1M,POLBNDL_1M&STYLES=0XFF8080,0X101040,BLACK&FORMAT=image/png&BGCOLOR=0xFFFFFF&TRANSPARENT=TRUE&EXCEPTIONS=INIMAGE"
    )

    # Test WMS GetCapabilities request
    assert (
        wms_url.get_capabilities_url(wms_version="1.3.0")
        == "http://b-maps.com/map.cgi?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0"
    )

    # Test WMS GetMap request
    assert (
        wms_url.get_map_url(
            version="1.3.0",
            layers=["BUILTUPA_1M", "COASTL_1M", "POLBNDL_1M"],
            styles=["0XFF8080", "0X101040", "BLACK"],
            crs="CRS:84",
            bounds=BoundingBox(west=-97.105, east=-78.794, south=24.913, north=36.358),
            format="image/png",
            width=560,
            height=350,
            background_color="0xFFFFFF",
            transparent=True,
        )
        == "http://b-maps.com/map.cgi?LAYERS=BUILTUPA_1M,COASTL_1M,POLBNDL_1M&STYLES=0XFF8080,0X101040,BLACK&CRS=CRS:84&BBOX=-97.105,24.913,-78.794,36.358&FORMAT=image/png&WIDTH=560&HEIGHT=350&TRANSPARENT=TRUE&BGCOLOR=0x0XFFFFFF&VERSION=1.3.0&SERVICE=WMS&REQUEST=GetMap"
    )

    assert wms_url.wms_version() == "1.3.0"

    assert wms_url.layers() == ["BUILTUPA_1M", "COASTL_1M", "POLBNDL_1M"]

    assert wms_url.format() == "image/png"

    assert wms_url.styles() == ["0XFF8080", "0X101040", "BLACK"]

    assert wms_url.is_valid_getmap_url()


@pytest.mark.parametrize(
    "wms_version",
    ["1.1.0", "1.1.1", "1.3.0"],
)
def test_wms_exceptions(wms_version: str):
    """Test if ServiceExceptionReport's are parsed correctly"""
    data_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "data", "wms", f"exception_{wms_version.replace('.', '_')}.xml"
    )
    with open(data_path) as f:
        xml = f.read()

    with pytest.raises(wmshelper.ServiceExceptionError):
        wmshelper.WMSCapabilities(xml)
