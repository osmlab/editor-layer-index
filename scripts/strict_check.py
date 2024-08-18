#!/usr/bin/env python

"""
usage: strict_check.py [-h] path [path ...]

Checks new ELI sources for validity and common errors

"""
import io
import json
import os
import re
from argparse import ArgumentParser
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import colorlog
import magic
import mercantile
import requests
import urllib3
import validators
from jsonschema import Draft4Validator, RefResolver, ValidationError
from libeli import eliutils, tmshelper, wmshelper, wmtshelper
from requests.models import Response
from shapely.geometry import Point, Polygon, box
from shapely.geometry.geo import mapping, shape
from shapely.geometry.multipolygon import MultiPolygon
from shapely.ops import unary_union
from shapely.validation import explain_validity, make_valid


class MessageLevel(Enum):
    INFO = 1
    WARNING = 2
    ERROR = 3


@dataclass
class Message:
    level: MessageLevel
    message: str


# Disable InsecureRequestWarning: Unverified HTTPS request is being made to host warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # type: ignore


def dict_raise_on_duplicates(ordered_pairs: List[Tuple[Any, Any]]) -> Dict[Any, Any]:
    """Reject duplicate keys."""
    d: Dict[Any, Any] = {}
    for k, v in ordered_pairs:
        if k in d:
            raise ValidationError("duplicate key: %r" % (k,))
        else:
            d[k] = v
    return d


parser = ArgumentParser(description="Strict checks for ELI sources newly added")
parser.add_argument("path", nargs="+", help="Path of files to check.")

arguments = parser.parse_args()
logger = colorlog.getLogger()
logger.setLevel("INFO")
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter())
logger.addHandler(handler)

schema = json.load(io.open("schema.json", encoding="utf-8"))

resolver = RefResolver("", None)
validator = Draft4Validator(schema, resolver=resolver)

borkenbuild = False
spacesave = 0

headers = {"User-Agent": "Mozilla/5.0 (compatible; MSIE 6.0; OpenStreetMap Editor Layer Index CI check)"}


logger.warning(
    "This is a new and improved check for new or changed imagery sources. "
    "It is currently in beta stage. Please report any issues."
)


def get_http_headers(source: Any) -> Dict[str, str]:
    """Extract http headers from source"""
    custom_headers: Dict[str, str] = {}
    custom_headers.update(headers)
    if "custom-http-headers" in source["properties"]:
        key = source["properties"]["custom-http-headers"]["header-name"]
        value = source["properties"]["custom-http-headers"]["header-value"]
        custom_headers[key] = value
    return custom_headers


def max_area_outside_bbox(
    geom: Polygon | MultiPolygon, bbox: eliutils.BoundingBox | List[eliutils.BoundingBox]
) -> float:
    """Calculate max percentage of area of geometry that is outside of the provided bounding boxes

    Parameters
    ----------
    geom : Polygon | MultiPolygon
        The geometry to check
    bbox : eliutils.BoundingBox | List[eliutils.BoundingBox]
        The BoundingBox to check against

    Returns
    -------
    float
        The maximal percentage of the area of geom that is not within a provided BoundingBox
    """
    if isinstance(bbox, list):
        geoms: List[Polygon] = [box(minx=bb.west, miny=bb.south, maxx=bb.east, maxy=bb.north) for bb in bbox]
        bbox_geom = unary_union(geoms)  # type: ignore
    else:
        bbox_geom: Polygon = box(minx=bbox.west, miny=bbox.south, maxx=bbox.east, maxy=bbox.north)

    geom_outside_bbox = geom.difference(bbox_geom)  # type: ignore
    return geom_outside_bbox.area / geom.area * 100.0  # type: ignore


def get_text_encoded(url: str, headers: Optional[Dict[str, str]]) -> Tuple[Response, Optional[str]]:
    """Fetch url and encode content based on encoding defined in XML when possible

    Parameters
    ----------
    url : str
        The URL to fetch
    headers : Optional[Dict[str, str]]
        Optional HTTP headers

    Returns
    -------
    Tuple[Response, Optional[str]]
        The Respone and encoded content
    """
    r = requests.get(url, headers=headers, verify=False)
    if not r.status_code == 200:
        return r, None
    # Try to encode text with encoding provided in XML
    encoding = eliutils.search_encoding(r.text)
    if encoding is not None:
        try:
            r.encoding = encoding
            return r, r.text
        except:
            pass
    r.encoding = r.apparent_encoding
    return r, r.text


def test_url(url: str, headers: Optional[Dict[str, str]] = None) -> Tuple[bool, int]:
    """Check if URL returns HTTP code 200

    Parameters
    ----------
    url : str
        The URL to test
    headers : Optional[Dict[str, str]], optional
        Optional HTTP headers, by default None

    Returns
    -------
    bool, int
        True if URL returns HTTP code 200 and HTTP status code
    """
    try:
        r = requests.get(url, headers=headers, verify=False)
        if r.status_code == 200:
            return True, r.status_code
        return False, r.status_code
    except Exception as e:
        logger.exception(f"Could not retrieve url: {url}: {e}")
    return False, -1


def test_image(url: str, headers: Optional[Dict[str, str]] = None) -> Tuple[bool, int, Optional[str]]:
    """Check if URL returns an image

    Parameters
    ----------
    url : str
        The URL to test
    headers : Optional[Dict[str, str]], optional
        Optional HTTP headers, by default None

    Returns
    -------
    bool, int
        True if URL returns an image  and HTTP status code
    """
    try:
        r = requests.get(url, headers=headers, verify=False)
        if not r.status_code == 200:
            return False, r.status_code, None
        filetype: str = magic.from_buffer(r.content, mime=True)  # type: ignore
        # TODO there might be other relevant image mime types
        return filetype in {"image/png", "image/jpeg", "image/webp"}, r.status_code, filetype
    except Exception as e:
        logger.exception(f"Could not retrieve url: {url}: {e}")
    return False, -1, None


def check_wms(source: Dict[str, Any], messages: List[Message]) -> None:
    """Check WMS source

    Parameters
    ----------
    source : Dict[str, Any]
        The source
    messages : List[Message]
        The list to add messages to
    """

    url = source["properties"]["url"]
    wms_url = wmshelper.WMSURL(url)
    source_headers = get_http_headers(source)

    params = ["{proj}", "{bbox}", "{width}", "{height}"]
    missingparams = [p for p in params if p not in url]
    if len(missingparams) > 0:
        messages.append(
            Message(
                level=MessageLevel.ERROR,
                message=f"The following values are missing in the URL: {','.join(missingparams)}",
            )
        )

    try:
        wms_url.is_valid_getmap_url()
    except validators.utils.ValidationFailure as e:
        messages.append(Message(level=MessageLevel.ERROR, message=f"URL validation error {e} for {url}"))

    # Check mandatory WMS GetMap parameters (Table 8, Section 7.3.2, WMS 1.3.0 specification)
    # Normalize parameter names to lower case
    wms_args = {key.lower(): value for key, value in wms_url.get_parameters()}

    # Check if it is actually a ESRI Rest url and not a WMS url
    is_esri = "request" not in wms_args

    # Check if required parameters are missing
    missing_request_parameters: Set[str] = set()
    if is_esri:
        required_parameters = ["f", "bbox", "size", "imageSR", "bboxSR", "format"]
    else:
        required_parameters = [
            "version",
            "request",
            "layers",
            "bbox",
            "width",
            "height",
            "format",
        ]
    for request_parameter in required_parameters:
        if request_parameter.lower() not in wms_args:
            missing_request_parameters.add(request_parameter)

    if not is_esri:
        if "version" in wms_args and wms_args["version"] == "1.3.0":
            if "crs" not in wms_args:
                missing_request_parameters.add("crs")
            if "srs" in wms_args:
                messages.append(
                    Message(
                        level=MessageLevel.ERROR,
                        message=f"WMS {wms_args['version']} URLs should not contain SRS parameter: {url}",
                    )
                )
        elif "version" in wms_args and not wms_args["version"] == "1.3.0":
            if "srs" not in wms_args:
                missing_request_parameters.add("srs")
            if "crs" in wms_args:
                messages.append(
                    Message(
                        level=MessageLevel.ERROR,
                        message=f"WMS {wms_args['version']} URLs should not contain CRS parameter: {url}",
                    )
                )
    if len(missing_request_parameters) > 0:
        missing_request_parameters_str = ",".join(missing_request_parameters)
        messages.append(
            Message(
                level=MessageLevel.ERROR,
                message=f"Parameter '{missing_request_parameters_str}' is missing in URL: {url}.",
            )
        )
        return

    # Nothing more to do for ESRI Rest API
    if is_esri:
        return

    # Styles is mandatory according to the WMS specification, but some WMS servers seems not to care
    if "styles" not in wms_args:
        messages.append(
            Message(
                level=MessageLevel.WARNING,
                message=f"Parameter 'styles' is missing in url. 'STYLES=' can be used to request default style.: {url}",
            )
        )

    # We first send a service=WMS&request=GetCapabilities request to server
    # According to the WMS Specification Section 6.2 Version numbering and negotiation, the server should return
    # the GetCapabilities XML with the highest version the server supports.
    # If this fails, it is tried to explicitly specify a WMS version
    exceptions: List[str] = []
    wms = None
    for wms_version in [None, "1.3.0", "1.1.1", "1.1.0", "1.0.0"]:
        if wms_version is None:
            wms_version_str = "-"
        else:
            wms_version_str = wms_version

        wms_getcapabilities_url = None
        try:
            wms_getcapabilities_url = wms_url.get_capabilities_url(wms_version=wms_version)
            _, xml = get_text_encoded(wms_getcapabilities_url, headers=source_headers)
            if xml is not None:
                wms = wmshelper.WMSCapabilities(xml)
            break
        except Exception as e:
            exceptions.append(f"WMS {wms_version_str}: Error: {e} {wms_getcapabilities_url}")
            continue

    # Check if it was possible to parse the WMS GetCapability response
    # If not, there is nothing left to check
    if wms is None:
        for msg in exceptions:
            messages.append(
                Message(
                    level=MessageLevel.ERROR,
                    message=msg,
                )
            )
        return

    # Log access constraints and fees metadata
    for access_constraint in wms.access_constraints:
        messages.append(
            Message(
                level=MessageLevel.INFO,
                message=f"AccessConstraints: {access_constraint}",
            )
        )
    for fee in wms.fees:
        messages.append(
            Message(
                level=MessageLevel.INFO,
                message=f"Fee: {fee}",
            )
        )

    if source["geometry"] is None:
        geom = None
    else:
        geom = shape(source["geometry"])  # type: ignore

    # Check layers
    if "layers" in wms_args:

        layers = wms_args["layers"].split(",")

        # Check if layers in WMS GetMap URL are advertised by WMS server.
        not_found_layers = [layer_name for layer_name in layers if layer_name not in wms.layers]
        if len(not_found_layers) > 0:
            messages.append(
                Message(
                    level=MessageLevel.ERROR,
                    message=f"Layers '{','.join(not_found_layers)}' not advertised by WMS GetCapabilities request (Some server do not advertise layers, but they are very rare).: {url}",
                )
            )

        # Check source geometry against layer bounding box
        # Regardless of its projection, each layer should advertise an approximated bounding box in lon/lat.
        # See WMS 1.3.0 Specification Section 7.2.4.6.6 EX_GeographicBoundingBox
        if geom is not None and geom.is_valid:  # type: ignore

            bboxs = [
                wms.layers[layer_name].bbox
                for layer_name in layers
                if layer_name in wms.layers and wms.layers[layer_name].bbox
            ]
            bboxs = [bbox for bbox in bboxs if bbox is not None]
            max_area_outside = max_area_outside_bbox(geom, bboxs)  # type: ignore

            # 5% is an arbitrary chosen value and should be adapted as needed
            if max_area_outside > 5.0:
                messages.append(
                    Message(
                        level=MessageLevel.ERROR,
                        message=f"{round(max_area_outside, 2)}% of geometry is outside of the layers bounding box. Geometry should be checked",
                    )
                )

        # Check styles
        if "styles" in wms_args:

            style_parameter = wms_args["styles"]

            # default style needs not to be advertised by the server
            if not (style_parameter == "default" or style_parameter == "" or style_parameter == "," * len(layers)):
                styles = style_parameter.split(",")
                if not len(styles) == len(layers):
                    messages.append(
                        Message(
                            level=MessageLevel.ERROR,
                            message=f"Not the same number of styles and layers. {len(styles)} vs {len(layers)}",
                        )
                    )
                else:
                    for layer_name, style_name in zip(layers, styles):
                        if (
                            len(style_name) > 0
                            and not style_name == "default"
                            and layer_name in wms.layers
                            and style_name not in wms.layers[layer_name].styles
                        ):
                            messages.append(
                                Message(
                                    level=MessageLevel.ERROR,
                                    message=f"Layer '{layer_name}' does not support style '{style_name}'",
                                )
                            )

        # Check CRS
        if "available_projections" not in source["properties"]:
            messages.append(
                Message(
                    level=MessageLevel.ERROR,
                    message=f"Sources of type wms must include the 'available_projections' element.",
                )
            )
        else:

            # A WMS server can include many CRS. Some of them are frequently used by editors. We require them to be included if they are supported by the WMS server.
            crs_should_included_if_available = {"EPSG:4326", "EPSG:3857", "CRS:84"}

            for layer_name in layers:
                if layer_name in wms.layers:

                    # Check for CRS in available_projections that are not advertised by the WMS server
                    not_supported_crs: Set[str] = set()
                    available_projections: List[str] = source["properties"]["available_projections"]

                    for crs in available_projections:
                        if crs.upper() not in wms.layers[layer_name].crs:
                            not_supported_crs.add(crs)

                    if len(not_supported_crs) > 0:
                        supported_crs_str = ",".join(wms.layers[layer_name].crs)
                        not_supported_crs_str = ",".join(not_supported_crs)
                        messages.append(
                            Message(
                                level=MessageLevel.WARNING,
                                message=f"Layer '{layer_name}': CRS '{not_supported_crs_str}' not in: {supported_crs_str}. Some server support CRS which are not advertised.",
                            )
                        )

                    # Check for CRS supported by the WMS server but not in available_projections
                    supported_but_not_included: Set[str] = set()
                    for crs in crs_should_included_if_available:
                        if crs not in available_projections and crs in wms.layers[layer_name].crs:
                            supported_but_not_included.add(crs)

                    if len(supported_but_not_included) > 0:
                        supported_but_not_included_str = ",".join(supported_but_not_included)
                        messages.append(
                            Message(
                                level=MessageLevel.WARNING,
                                message=f"Layer '{layer_name}': CRS '{supported_but_not_included_str}' not included in available_projections but supported by server.",
                            )
                        )

    # Check if server supports a newer WMS version as in url
    if wms_args["version"] < wms.version:
        messages.append(
            Message(
                level=MessageLevel.WARNING,
                message=f"Query requests WMS version '{wms_args['version']}', server supports '{wms.version}'",
            )
        )

    # Check image formats
    request_imagery_format = wms_args["format"]
    wms_advertised_formats_str = "', '".join(wms.formats)
    if request_imagery_format not in wms.formats:
        messages.append(
            Message(
                level=MessageLevel.ERROR,
                message=f"Format '{request_imagery_format}' not in '{wms_advertised_formats_str}': {url}.",
            )
        )

    # For photo sources it is recommended to use jpeg format, if it is available
    if "category" in source["properties"] and "photo" in source["properties"]["category"]:
        if "jpeg" not in request_imagery_format and "jpeg" in wms.formats:
            messages.append(
                Message(
                    level=MessageLevel.WARNING,
                    message=f"Server supports JPEG, but '{request_imagery_format}' is used. "
                    f"JPEG is typically preferred for photo sources, but might not be always "
                    f"the best choice. (Server supports: '{wms_advertised_formats_str}')",
                )
            )


def check_wms_endpoint(source: Dict[str, Any], messages: List[Message]) -> None:
    """Check WMS Endpoint source

    Parameters
    ----------
    source : Dict[str, Any]
        The source
    messages : List[Message]
        The list to add messages to
    """

    url = source["properties"]["url"]
    wms_url = wmshelper.WMSURL(url)

    try:
        validators.url(url)  # type: ignore
    except validators.utils.ValidationFailure as e:
        messages.append(Message(level=MessageLevel.ERROR, message=f"URL validation error: {e} for {url}"))

    source_headers = get_http_headers(source)

    exceptions: List[str] = []
    wms = None
    for wms_version in [None, "1.3.0", "1.1.1", "1.1.0", "1.0.0"]:
        if wms_version is None:
            wms_version_str = "-"
        else:
            wms_version_str = wms_version

        wms_getcapabilities_url = None
        try:
            wms_getcapabilities_url = wms_url.get_capabilities_url(wms_version=wms_version)
            _, xml = get_text_encoded(wms_getcapabilities_url, headers=source_headers)
            if xml is not None:
                wms = wmshelper.WMSCapabilities(xml)
            break
        except Exception as e:
            exceptions.append(f"WMS {wms_version_str}: Error: {e} {wms_getcapabilities_url}")
            continue

    # Check if it was possible to parse the WMS GetCapability response
    if wms is None:
        for msg in exceptions:
            messages.append(
                Message(
                    level=MessageLevel.ERROR,
                    message=msg,
                )
            )


def check_wmts(source: Dict[str, Any], messages: List[Message]) -> None:
    """Check WMTS source

    Parameters
    ----------
    source : Dict[str, Any]
        The source
    messages : List[Message]
        The list to add messages to
    """

    url = source["properties"]["url"]
    source_headers = get_http_headers(source)

    try:
        validators.url(url)  # type: ignore
    except validators.utils.ValidationFailure as e:
        messages.append(Message(level=MessageLevel.ERROR, message=f"URL validation error: {e} for {url}"))

    # Fetch WMTS Capabilities
    r, xml = get_text_encoded(url, headers=source_headers)
    if not r.status_code == 200:
        messages.append(Message(level=MessageLevel.ERROR, message=f"Failed to fetch {url}: HTTP code {r.status_code}"))
    if xml is None:
        return

    wmts_capabilities = None
    try:
        wmts_capabilities = wmtshelper.WMTSCapabilities(xml)
    except Exception as e:
        messages.append(
            Message(level=MessageLevel.ERROR, message=f"Failed to parse WMTS Capabilities for URL {url}: {e}")
        )

    if wmts_capabilities is not None:
        # Check if WMTS layers can be represented as TMS
        tms_compatible_layers = wmts_capabilities.tms_compatible_layers()
        for layer in tms_compatible_layers:
            tms_urls = wmts_capabilities.get_tms_compatible_urls(layer)
            # TODO scaling factor for tiles > 256pixel once this is supported
            if len(tms_urls) == 1:
                messages.append(
                    Message(
                        level=MessageLevel.WARNING,
                        message=f"Layer {layer} could be represented as type 'tms' and the URL: {list(tms_urls)[0]}",
                    )
                )
            elif len(tms_urls) > 1:
                messages.append(
                    Message(
                        level=MessageLevel.WARNING,
                        message=f"Layer {layer} could be represented as type 'tms' and one of the URLs: {', '.join(tms_urls)}",
                    )
                )


def check_tms(source: Dict[str, Any], messages: List[Message]) -> None:
    """Check TMS source

    Parameters
    ----------
    source : Dict[str, Any]
        The source
    messages : List[Message]
        The list to add messages to
    """

    try:
        url = source["properties"]["url"]
        source_headers = get_http_headers(source)

        if source["geometry"] is None:
            geom = None
        else:
            geom = shape(source["geometry"])

        # Validate URL
        try:
            _url = re.sub(r"switch:?([^}]*)", "switch", url).replace("{", "").replace("}", "")
            validators.url(_url)  # type: ignore
        except validators.utils.ValidationFailure as e:
            messages.append(Message(level=MessageLevel.ERROR, message=f"URL validation error {e} / {url}"))

        # Check URL parameter
        parameters = {}

        # {z} instead of {zoom}
        if "{z}" in source["properties"]["url"]:
            messages.append(
                Message(
                    level=MessageLevel.ERROR, message=f"Parameter {{z}} is used instead of {{zoom}} in tile url: {url}"
                )
            )
            return

        # We can't test sources that have an apikey, that is unknown to ELI
        if "{apikey}" in url:
            messages.append(
                Message(level=MessageLevel.WARNING, message=f"Not possible to check URL, apikey is required: {url}")
            )
            return

        # If URL contains a {switch:a,b,c} parameters, use the first for tests
        match = re.search(r"switch:?([^}]*)", url)
        if match is not None:
            switches = match.group(1).split(",")
            url = url.replace(match.group(0), "switch")
            parameters["switch"] = switches[0]

        # Check zoom levels
        min_zoom = 0
        max_zoom = 22
        if "min_zoom" in source["properties"]:
            min_zoom = int(source["properties"]["min_zoom"])
        if "max_zoom" in source["properties"]:
            max_zoom = int(source["properties"]["max_zoom"])

        # Check if we find a TileMap Resource to check for zoom levels
        # While there is a typical location for metadata, there is no requirement
        # that the metadata need to be located there.
        tms_url = tmshelper.TMSURL(url=url)
        tilemap_resource_url = tms_url.get_tilemap_resource_url()

        if tilemap_resource_url is not None:
            for tilemap_url in [
                tilemap_resource_url,
                tilemap_resource_url + "/tilemapresource.xml",
            ]:
                try:
                    r, xml = get_text_encoded(tilemap_url.format(**parameters), headers=headers)
                    if r.status_code == 200 and xml is not None:
                        try:
                            tilemap_resource = tmshelper.TileMapResource(xml)
                        except Exception:
                            # Not all TMS server provide TileMap resources.
                            continue

                        if tilemap_resource.tile_map is None:
                            continue

                        # Check zoom levels against TileMapResource
                        tilemap_minzoom, tilemap_maxzoom = tilemap_resource.get_min_max_zoom_level()
                        if min_zoom == tilemap_minzoom:
                            messages.append(
                                Message(
                                    level=MessageLevel.WARNING,
                                    message=f"min_zoom level '{min_zoom}' not the same as specified in TileMap: '{tilemap_minzoom}': {tilemap_url}. "
                                    "Caution: this might be intentional as some server timeout for low zoom levels.",
                                )
                            )
                        if not max_zoom == tilemap_maxzoom:
                            messages.append(
                                Message(
                                    level=MessageLevel.WARNING,
                                    message=f"max_zoom level '{max_zoom}' not the same as specified in TileMap: '{tilemap_maxzoom}': {tilemap_url}",
                                )
                            )

                        # Check geometry within bbox
                        if geom is not None and tilemap_resource.tile_map.bbox84 is not None:
                            max_area_outside = max_area_outside_bbox(geom, tilemap_resource.tile_map.bbox84)
                            # 5% is an arbitrary chosen value and should be adapted as needed
                            if max_area_outside > 5.0:
                                messages.append(
                                    Message(
                                        level=MessageLevel.ERROR,
                                        message=f"{round(max_area_outside, 2)}% of geometry is outside of the layers bounding box. Geometry should be checked",
                                    )
                                )
                        break

                except Exception as e:
                    print(f"Error fetching TMS: {e}: {url}")
                    pass

        # Test zoom levels by accessing tiles for a point within the geometry
        if geom is not None:
            centroid: Point = geom.representative_point()  # type: ignore
        else:
            centroid = Point(6.1, 49.6)
        centroid_x: float = centroid.x  # type: ignore
        centroid_y: float = centroid.y  # type: ignore

        zoom_failures: List[Tuple[int, str, int, Optional[str]]] = []
        zoom_success: List[int] = []
        tested_zooms: Set[int] = set()

        def test_zoom(zoom: int) -> None:
            tested_zooms.add(zoom)
            tile: mercantile.Tile = mercantile.tile(centroid_x, centroid_y, zoom)  # type: ignore

            tile_x: int = tile.x  # type: ignore
            tile_y: int = tile.y  # type: ignore

            query_url = url
            if "{-y}" in url:
                y = 2**zoom - 1 - tile_y
                query_url = query_url.replace("{-y}", str(y))
            elif "{!y}" in url:
                y = 2 ** (zoom - 1) - 1 - tile_y
                query_url = query_url.replace("{!y}", str(y))
            else:
                query_url = query_url.replace("{y}", str(tile_y))

            parameters["x"] = tile_x
            parameters["zoom"] = zoom
            query_url = query_url.format(**parameters)

            url_is_good, http_code, mime = test_image(query_url, source_headers)
            if url_is_good:
                zoom_success.append(zoom)
            else:
                zoom_failures.append((zoom, query_url, http_code, mime))

        # Test zoom levels
        for zoom in range(min_zoom, max_zoom + 1):
            test_zoom(zoom)

        tested_str = ",".join(list(map(str, sorted(tested_zooms))))
        sorted_failures = sorted(zoom_failures, key=lambda x: x[0])

        if len(zoom_failures) == 0 and len(zoom_success) > 0:
            messages.append(Message(level=MessageLevel.INFO, message=f"Zoom levels reachable. (Tested: {tested_str})"))
        elif len(zoom_failures) > 0 and len(zoom_success) > 0:

            not_found_str = ",".join(list(map(str, [level for level, _, _, _ in sorted_failures])))
            messages.append(
                Message(
                    level=MessageLevel.WARNING,
                    message=f"Zoom level {not_found_str} not reachable. (Tested: {tested_str}) Tiles might not be present at tested location: {centroid_x},{centroid_y}",
                )
            )

            for level, url, http_code, mime_type in sorted_failures:
                messages.append(
                    Message(
                        level=MessageLevel.WARNING,
                        message=f"URL for zoom level {level} returned HTTP Code {http_code}: {url} MIME type: {mime_type}",
                    )
                )
        else:
            messages.append(
                Message(
                    level=MessageLevel.ERROR,
                    message=f"No zoom level reachable. (Tested: {tested_str}) Tiles might not be present at tested location: {centroid_x},{centroid_y}",
                )
            )
            for level, url, http_code, mime_type in sorted_failures:
                messages.append(
                    Message(
                        level=MessageLevel.WARNING,
                        message=f"URL for zoom level {level} returned HTTP Code {http_code}: {url} MIME type: {mime_type}",
                    )
                )

    except Exception as e:
        messages.append(
            Message(
                level=MessageLevel.ERROR,
                message=f"Failed testing TMS source: Exception: {e}",
            )
        )


for filename in arguments.path:

    if not filename.lower()[-8:] == ".geojson":
        logger.debug(f"{filename} is not a geojson file, skip")
        continue

    if not os.path.exists(filename):
        logger.debug(f"{filename} does not exist, skip")
        continue

    try:
        logger.info(f"Processing {filename}")

        messages: List[Message] = []

        # dict_raise_on_duplicates raises error on duplicate keys in geojson
        source = json.load(
            io.open(filename, encoding="utf-8"),
            object_pairs_hook=dict_raise_on_duplicates,
        )

        # jsonschema validate
        try:
            validator.validate(source, schema)
        except Exception as e:
            messages.append(
                Message(
                    level=MessageLevel.ERROR,
                    message=f"{filename} JSON validation error: {e}",
                )
            )

        logger.info(f"Type: {source['properties']['type']}")

        # Check geometry
        if "geometry" in source:
            geom = shape(source["geometry"])  # type: ignore

            # Check if geometry is a valid (e.g. no intersection etc.)
            if not geom.is_valid:  # type: ignore
                try:
                    reason = explain_validity(geom)  # type: ignore
                    messages.append(
                        Message(
                            level=MessageLevel.ERROR,
                            message=f"{filename} invalid geometry: {reason}",
                        )
                    )
                    valid_geom = make_valid(geom)  # type: ignore
                    valid_geom = eliutils.orient_geometry_rfc7946(valid_geom)  # type: ignore
                    valid_geom_json = json.dumps(mapping(valid_geom), sort_keys=False, ensure_ascii=False)  # type: ignore
                    messages.append(
                        Message(
                            level=MessageLevel.ERROR,
                            message=f"{filename} please consider using corrected geometry: {valid_geom_json}",
                        )
                    )
                    geom = valid_geom  # type: ignore
                except Exception as e:
                    logger.warning("Geometry check failed: {e}")

            # Check ring orientation to correspond with GeoJSON rfc7946:
            # A linear ring MUST follow the right-hand rule with respect to the
            # area it bounds, i.e., exterior rings are counterclockwise, and
            # holes are clockwise.
            oriented_geom = eliutils.orient_geometry_rfc7946(geom)  # type: ignore  # type: ignore
            if not json.dumps(mapping(geom)) == json.dumps(mapping(oriented_geom)):  # type: ignore
                messages.append(
                    Message(
                        level=MessageLevel.ERROR,
                        message=f"{filename} ring orientation does not correspond to GeoJSON RFC7946",
                    )
                )
                oriented_geom_json = json.dumps(mapping(oriented_geom), sort_keys=False, ensure_ascii=False,)  # type: ignore
                messages.append(
                    Message(
                        level=MessageLevel.ERROR,
                        message=f"{filename} please consider using corrected geometry: {oriented_geom_json}",
                    )
                )

        # Check for license url
        # There can be sources without license_url, but failing this test brings to attention to i
        if "license_url" not in source["properties"]:
            messages.append(
                Message(
                    level=MessageLevel.ERROR,
                    message=f"{filename} has no license_url set",
                )
            )

        # Check if license url exists
        else:
            try:
                r = requests.get(source["properties"]["license_url"], headers=headers, verify=False)
                if not r.status_code == 200:
                    messages.append(
                        Message(
                            level=MessageLevel.ERROR,
                            message=f"{filename}: license url {source['properties']['license_url']} is not reachable: HTTP code: {r.status_code}",
                        )
                    )

            except Exception as e:
                messages.append(
                    Message(
                        level=MessageLevel.ERROR,
                        message=f"{filename}: license url {source['properties']['license_url']} is not reachable: {e}",
                    )
                )

        # Check attribution url exists
        if "attribution" in source["properties"]:
            if "url" in source["properties"]["attribution"]:
                url = source["properties"]["attribution"]["url"]

                if not test_url(url, headers):
                    messages.append(
                        Message(
                            level=MessageLevel.ERROR,
                            message=f"{filename}: could not retrieve attribution url {url}.",
                        )
                    )

        # Check icon url exists
        if "icon" in source["properties"] and source["properties"]["icon"].startswith("http"):
            url = source["properties"]["icon"]
            try:
                r = requests.get(url, headers=headers, verify=False)
                if not r.status_code == 200:
                    messages.append(
                        Message(
                            level=MessageLevel.ERROR,
                            message=f"{filename}: icon url {url} is not reachable: HTTP code: {r.status_code}",
                        )
                    )

            except Exception as e:
                messages.append(
                    Message(
                        level=MessageLevel.ERROR,
                        message=f"{filename}: icon url {url} is not reachable: {e}",
                    )
                )

        # Privacy policy
        # Check if privacy url is set
        if "privacy_policy_url" not in source["properties"]:
            messages.append(
                Message(
                    level=MessageLevel.ERROR,
                    message=f"{filename} has no privacy_policy_url. Adding privacy policies to sources is important to comply with legal requirements in certain countries.",
                )
            )
        else:

            if isinstance(source["properties"]["privacy_policy_url"], str):
                # Check if privacy url exists
                if not test_url(source["properties"]["privacy_policy_url"], headers):
                    messages.append(
                        Message(
                            level=MessageLevel.ERROR,
                            message=f"{filename}: could not retrieve privacy policy url {source['properties']['privacy_policy_url']}.",
                        )
                    )
            elif not isinstance(source["properties"]["privacy_policy_url"], str) and not (
                isinstance(source["properties"]["privacy_policy_url"], bool)
                and not source["properties"]["privacy_policy_url"]
            ):
                # If the privacy_policy_url is not an URL it must be False
                messages.append(
                    Message(
                        level=MessageLevel.ERROR,
                        message=f"{filename}: privacy_policy_url can either be an URL or false, not: '{source['properties']['privacy_policy_url']}'.",
                    )
                )

        # Check for big fat embedded icons
        if "icon" in source["properties"]:
            if source["properties"]["icon"].startswith("data:"):
                iconsize = len(source["properties"]["icon"].encode("utf-8"))
                spacesave += iconsize
                logger.warning(f"{filename} icon should be disembedded to save {round(iconsize / 1024.0, 2)} KB")

        # Check for category
        if "category" not in source["properties"]:
            messages.append(
                Message(
                    level=MessageLevel.ERROR,
                    message=f"{filename}: no category is specified.",
                )
            )

        # If we're not global we must have a geometry.
        # The geometry itself is validated by jsonschema
        if "world" not in filename:
            if "type" not in source["geometry"]:
                messages.append(
                    Message(
                        level=MessageLevel.ERROR,
                        message=f"{filename} should have a valid geometry or be global",
                    )
                )
            if source["geometry"]["type"] not in {"Polygon", "MultiPolygon"}:
                messages.append(
                    Message(
                        level=MessageLevel.ERROR,
                        message=f"{filename} Geometry should be a Polygon or MultiPolygon",
                    )
                )
            if "country_code" not in source["properties"]:
                messages.append(
                    Message(
                        level=MessageLevel.ERROR,
                        message=f"{filename} should have a country_code or be global",
                    )
                )
        else:
            if "geometry" not in source:
                messages.append(
                    Message(
                        level=MessageLevel.ERROR,
                        message=f"{filename} should have null geometry",
                    )
                )
            elif source["geometry"] is not None:
                messages.append(
                    Message(
                        level=MessageLevel.ERROR,
                        message=f"{filename} should have null geometry but it is {source['geometry']}",
                    )
                )

        # Check if URL encodes HTTP headers
        if "user-agent" in source["properties"]["url"].lower():
            messages.append(
                Message(
                    level=MessageLevel.ERROR,
                    message=f"{filename} URL should not encode HTTP headers: {source['properties']['url']}",
                )
            )

        # Check imagery type
        if source["properties"]["type"] == "tms":
            check_tms(source, messages)
        elif source["properties"]["type"] == "wms":
            check_wms(source, messages)
        elif source["properties"]["type"] == "wms_endpoint":
            check_wms_endpoint(source, messages)
        elif source["properties"]["type"] == "wmts":
            check_wmts(source, messages)
        else:
            messages.append(
                Message(
                    level=MessageLevel.WARNING,
                    message=f"{filename}: Imagery type { source['properties']['type']} is currently not checked.",
                )
            )

        for msg in [msg for msg in messages if msg.level == MessageLevel.INFO]:
            logger.info(msg.message)
        for msg in [msg for msg in messages if msg.level == MessageLevel.WARNING]:
            logger.warning(msg.message)
        for msg in [msg for msg in messages if msg.level == MessageLevel.ERROR]:
            logger.error(msg.message)

        if len([msg for msg in messages if msg.level == MessageLevel.ERROR]) > 0:
            raise ValidationError("Errors occurred, see logs above.")
        logger.info(f"Finished processing {filename}")
    except ValidationError as e:
        borkenbuild = True
    except Exception as e:
        logger.exception(f"Failed: {e}")
if spacesave > 0:
    logger.warning(f"Disembedding all icons would save {round(spacesave / 1024.0, 2)} KB")
if borkenbuild:
    raise SystemExit(1)
