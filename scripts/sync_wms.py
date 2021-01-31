import argparse
import asyncio
import glob
import io
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from collections import OrderedDict, namedtuple, defaultdict
from io import StringIO
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import aiohttp
import imagehash
import mercantile
import pyproj
from PIL import Image
from shapely.geometry import shape, box, Polygon, Point
from pyproj import Transformer
from pyproj.crs import CRS
import aiofiles
from aiohttp import ClientSession
from shapely.ops import cascaded_union
import magic
from enum import Enum

ZOOM_LEVEL = 14
IMAGE_SIZE = 256


logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser(description="Update WMS URLs and related properties")
parser.add_argument(
    "sources",
    metavar="sources",
    type=str,
    nargs="?",
    help="path to sources directory",
    default="sources",
)

args = parser.parse_args()
sources_directory = args.sources

response_cache = {}
domain_locks = {}
domain_lock = asyncio.Lock()

RequestResult = namedtuple(
    "RequestResultCache", ["status", "text", "exception"], defaults=[None, None, None]
)


ImageHashStatus = Enum("ImageHashStatus", "SUCCESS IMAGE_ERROR NETWORK_ERROR OTHER")


def image_similar(hash_a, hash_b, zoom):
    """ Returns Ture if hash_a is considered similar to hash_b for zoom level zoom"""
    return hash_a - hash_b < 6


# Before adding a new WMS version, it should be checked if every consumer supports it!
supported_wms_versions = ["1.3.0", "1.1.1", "1.1.0", "1.0.0"]


epsg_3857_alias = set(
    [f"EPSG:{epsg}" for epsg in [900913, 3587, 54004, 41001, 102113, 102100, 3785]]
)

# List of not deprecated EPSG codes
valid_epsgs = set(["CRS:84"])
for pj_type in pyproj.enums.PJType:
    valid_epsgs.update(
        map(
            lambda x: f"EPSG:{x}",
            pyproj.get_codes("EPSG", pj_type, allow_deprecated=False),
        )
    )

# EPSG:3857 alias are valid if server does not support EPSG:3857
valid_epsgs.update(epsg_3857_alias)


transformers = {}


def get_transformer(crs_from, crs_to):
    """ Cache transformer objects"""
    key = (crs_from, crs_to)
    if key not in transformers:
        transformers[key] = Transformer.from_crs(crs_from, crs_to, always_xy=True)
    return transformers[key]


def parse_eli_geometry(geometry):
    """ELI currently uses a geometry encoding not compatible with geojson.
    Create valid geometries from this format."""
    _geom = shape(geometry)
    geoms = [Polygon(_geom.exterior.coords)]
    for ring in _geom.interiors:
        geoms.append(Polygon(ring.coords))
    return cascaded_union(geoms)


def max_count(elements):
    """ Return the occurences of the most common element"""
    counts = defaultdict(int)
    for el in elements:
        counts[el] += 1
    return max(counts.items(), key=lambda x: x[1])[1]


def compare_projs(old_projs, new_projs):
    """Compare two collections of projections. Returns True if both collections contain the same elements.

    Parameters
    ----------
    old_projs : collection
    new_projs : collection

    Returns
    -------
    bool

    """
    return set(old_projs) == set(new_projs)


def compare_urls(old_url, new_url):
    """Compare URLs. Returns True if the urls contain the same parameters.
    Parameters
    ----------
    old_url : str
    new_url : str
    Returns
    -------
    bool
    """
    old_parameters = parse_qsl(urlparse(old_url.lower()).query, keep_blank_values=True)
    new_parameters = parse_qsl(urlparse(new_url.lower()).query, keep_blank_values=True)
    # Fail if old url contains duplicated parameters
    if not len(set(old_parameters)) == len(old_parameters):
        return False
    return set(old_parameters) == set(new_parameters)


async def get_url(
    url: str, session: ClientSession, with_text=False, with_data=False, headers=None
):
    """Fetch url.

    This function ensures that only one request is sent to a domain at one point in time and that the same url is not
    queried more than once.

    Parameters
    ----------
    url : str
    session: ClientSession
    with_text: bool
    with_data : bool
    headers: dict

    Returns
    -------
    RequestResult

    """
    o = urlparse(url)
    if len(o.netloc) == 0:
        return RequestResult(exception=f"Could not parse URL: {url}")

    async with domain_lock:
        if o.netloc not in domain_locks:
            domain_locks[o.netloc] = asyncio.Lock()
        lock = domain_locks[o.netloc]

    async with lock:
        if url not in response_cache:
            for i in range(3):
                try:
                    logging.debug(f"GET {url}")
                    async with session.request(
                        method="GET", url=url, ssl=False, headers=headers
                    ) as response:
                        status = response.status
                        if with_text:
                            try:
                                text = await response.text()
                            except:
                                text = await response.read()
                            response_cache[url] = RequestResult(
                                status=status, text=text
                            )
                        elif with_data:
                            data = await response.read()
                            response_cache[url] = RequestResult(
                                status=status, text=data
                            )
                        else:
                            response_cache[url] = RequestResult(status=status)
                except asyncio.TimeoutError:
                    response_cache[url] = RequestResult(exception=f"Timeout for: {url}")
                except Exception as e:
                    logging.debug(f"Error for: {url} ({e})")
                    response_cache[url] = RequestResult(
                        exception=f"Exception {e} for: {url}"
                    )
                if RequestResult.exception is None:
                    break
                await asyncio.sleep(5)
        else:
            logging.debug(f"Cached {url}")

        return response_cache[url]


def wms_version_from_url(url):
    """ Extract wms version from url"""
    u = urlparse(url.lower())
    qsl = dict(parse_qsl(u.query))
    if "version" not in qsl:
        return None
    else:
        return qsl["version"]


def _get_bbox(proj, bounds, wms_version):
    """ Build wms bbox parameter for GetMap request"""
    if proj in {"EPSG:4326", "CRS:84"}:
        if proj == "EPSG:4326" and wms_version == "1.3.0":
            bbox = ",".join(map(str, [bounds[1], bounds[0], bounds[3], bounds[2]]))
        else:
            bbox = ",".join(map(str, bounds))
    else:
        try:
            crs_from = CRS.from_string("epsg:4326")
            crs_to = CRS.from_string(proj)
            transformer = get_transformer(crs_from, crs_to)
            bounds = list(transformer.transform(bounds[0], bounds[1])) + list(
                transformer.transform(bounds[2], bounds[3])
            )
        except:
            return None

        # WMS < 1.3.0 assumes x,y coordinate ordering.
        # WMS 1.3.0 expects coordinate ordering defined in CRS.
        #
        if crs_to.axis_info[0].direction == "north" and wms_version == "1.3.0":
            bbox = ",".join(map(str, [bounds[1], bounds[0], bounds[3], bounds[2]]))
        else:
            bbox = ",".join(map(str, bounds))
    return bbox


async def get_image(url, available_projections, lon, lat, zoom, session, messages):
    """Download image (tms tile for coordinate lon,lat on level zoom and calculate image hash

    Parameters
    ----------
    url : str
    available_projections : collection
    lon : float
    lat : float
    zoom : int
    session : ClientSession
    messages : list

    Returns
    -------
    ImageHash or None

    """
    tile = list(mercantile.tiles(lon, lat, lon, lat, zooms=zoom))[0]
    bounds = list(mercantile.bounds(tile))

    img_hash = None
    status = ImageHashStatus.OTHER

    proj = None
    if "EPSG:4326" in available_projections:
        proj = "EPSG:4326"
    elif "EPSG:3857" in available_projections:
        proj = "EPSG:3857"
    else:
        for proj in sorted(available_projections):
            try:
                CRS.from_string(proj)
            except:
                continue
            break
    if proj is None:
        messages.append("No projection left: {}".format(available_projections))
        return status, img_hash

    wms_version = wms_version_from_url(url)
    bbox = _get_bbox(proj, bounds, wms_version)
    if bbox is None:
        messages.append(f"Projection {proj} could not be parsed by pyproj.")
        return status, img_hash

    formatted_url = url.format(
        proj=proj, width=IMAGE_SIZE, height=IMAGE_SIZE, bbox=bbox
    )
    messages.append(f"Image URL: {formatted_url}")
    for i in range(3):
        try:
            # Download image
            async with session.request(
                method="GET", url=formatted_url, ssl=False
            ) as response:
                if response.status == 200:
                    data = await response.read()
                    try:
                        img = Image.open(io.BytesIO(data))
                        img_hash = imagehash.average_hash(img)
                        status = ImageHashStatus.SUCCESS
                        messages.append(f"ImageHash: {img_hash}")
                        return status, img_hash
                    except Exception as e:
                        status = ImageHashStatus.IMAGE_ERROR
                        messages.append(str(e))
                        filetype = magic.from_buffer(data)
                        messages.append(
                            f"Could not open recieved data as image (Recieved filetype: {filetype} {formatted_url})"
                        )
                else:
                    status = ImageHashStatus.NETWORK_ERROR

        except Exception as e:
            status = ImageHashStatus.NETWORK_ERROR
            messages.append(f"Could not download image in try {i}: {e}")
        await asyncio.sleep(5)

    return status, img_hash


def parse_wms(xml):
    """Rudimentary parsing of WMS Layers from GetCapabilites Request
    owslib.wms seems to have problems parsing some weird not relevant metadata.
    This function aims at only parsing relevant layer metadata
    """
    wms = {}
    # Remove prefixes to make parsing easier
    # From https://stackoverflow.com/questions/13412496/python-elementtree-module-how-to-ignore-the-namespace-of-xml-files-to-locate-ma
    try:
        it = ET.iterparse(StringIO(xml))
        for _, el in it:
            _, _, el.tag = el.tag.rpartition("}")
        root = it.root
    except:
        raise RuntimeError("Could not parse XML.")

    root_tag = root.tag.rpartition("}")[-1]
    if root_tag in {"ServiceExceptionReport", "ServiceException"}:
        raise RuntimeError("WMS service exception")

    if root_tag not in {"WMT_MS_Capabilities", "WMS_Capabilities"}:
        raise RuntimeError(
            "No Capabilities Element present: Root tag: {}".format(root_tag)
        )

    if "version" not in root.attrib:
        raise RuntimeError("WMS version cannot be identified.")
    version = root.attrib["version"]
    wms["version"] = version

    layers = {}

    def parse_layer(element, crs=set(), styles={}, bbox=None):
        new_layer = {"CRS": crs, "Styles": {}, "BBOX": bbox}
        new_layer["Styles"].update(styles)
        for tag in ["Name", "Title", "Abstract"]:
            e = element.find("./{}".format(tag))
            if e is not None:
                new_layer[e.tag] = e.text
        for tag in ["CRS", "SRS"]:
            es = element.findall("./{}".format(tag))
            for e in es:
                new_layer["CRS"].add(e.text.upper())
        for tag in ["Style"]:
            es = element.findall("./{}".format(tag))
            for e in es:
                new_style = {}
                for styletag in ["Title", "Name"]:
                    el = e.find("./{}".format(styletag))
                    if el is not None:
                        new_style[styletag] = el.text
                new_layer["Styles"][new_style["Name"]] = new_style
        # WMS Version 1.3.0
        e = element.find("./EX_GeographicBoundingBox")
        if e is not None:
            bbox = [
                float(e.find("./{}".format(orient)).text.replace(",", "."))
                for orient in [
                    "westBoundLongitude",
                    "southBoundLatitude",
                    "eastBoundLongitude",
                    "northBoundLatitude",
                ]
            ]
            new_layer["BBOX"] = bbox
        # WMS Version < 1.3.0
        e = element.find("./LatLonBoundingBox")
        if e is not None:
            bbox = [
                float(e.attrib[orient].replace(",", "."))
                for orient in ["minx", "miny", "maxx", "maxy"]
            ]
            new_layer["BBOX"] = bbox

        if "Name" in new_layer:
            layers[new_layer["Name"]] = new_layer

        for sl in element.findall("./Layer"):
            parse_layer(
                sl, new_layer["CRS"].copy(), new_layer["Styles"], new_layer["BBOX"]
            )

    # Find child layers. CRS and Styles are inherited from parent
    top_layers = root.findall(".//Capability/Layer")
    for top_layer in top_layers:
        parse_layer(top_layer)

    wms["layers"] = layers

    # Parse formats
    formats = []
    for es in root.findall(".//Capability/Request/GetMap/Format"):
        formats.append(es.text)
    wms["formats"] = formats

    # Parse access constraints and fees
    constraints = []
    for es in root.findall(".//AccessConstraints"):
        constraints.append(es.text)
    fees = []
    for es in root.findall(".//Fees"):
        fees.append(es.text)
    wms["Fees"] = fees
    wms["AccessConstraints"] = constraints

    return wms


async def update_wms(wms_url, session: ClientSession, messages):
    """Update wms parameters using WMS GetCapabilities request

    Parameters
    ----------
    wms_url : str
    session : ClientSession
    messages : list

    Returns
    -------
        dict
            Dict with new url and available projections

    """
    wms_args = {}
    u = urlparse(wms_url)
    url_parts = list(u)
    for k, v in parse_qsl(u.query, keep_blank_values=True):
        wms_args[k.lower()] = v

    layers = wms_args["layers"].split(",")

    def get_getcapabilitie_url(wms_version=None):
        get_capabilities_args = {"service": "WMS", "request": "GetCapabilities"}
        if wms_version is not None:
            get_capabilities_args["version"] = wms_version

        # Drop all wms getmap parameters, keep all extra arguments (e.g. such as map or key)
        for key in wms_args:
            if key not in {
                "version",
                "request",
                "layers",
                "bbox",
                "width",
                "height",
                "format",
                "crs",
                "srs",
                "styles",
                "transparent",
                "dpi",
                "map_resolution",
                "format_options",
            }:
                get_capabilities_args[key] = wms_args[key]
        url_parts[4] = urlencode(list(get_capabilities_args.items()))
        return urlunparse(url_parts)

    # Fetch highest supported WMS GetCapabilities
    wms = None
    for wmsversion in supported_wms_versions:
        # Do not try versions older than in the url
        if wmsversion < wms_args["version"]:
            continue

        try:
            wms_getcapabilites_url = get_getcapabilitie_url(wmsversion)
            resp = await get_url(wms_getcapabilites_url, session, with_text=True)
            if resp.exception is not None:
                messages.append(
                    "Could not download GetCapabilites URL for {}: {}".format(
                        wmsversion, resp.exception
                    )
                )
                continue
            xml = resp.text
            if isinstance(xml, bytes):
                # Parse xml encoding to decode
                try:
                    xml_ignored = xml.decode(errors="ignore")
                    str_encoding = re.search('encoding="(.*?)"', xml_ignored).group(1)
                    xml = xml.decode(encoding=str_encoding)
                except Exception as e:
                    raise RuntimeError("Could not parse encoding: {}".format(str(e)))

            wms = parse_wms(xml)
            if wms is not None:
                break
        except Exception as e:
            messages.append(
                "Could not get GetCapabilites URL for {} in try: {}".format(
                    wmsversion, str(e)
                )
            )

    if wms is None:
        # Could not request GetCapabilities
        messages.append("Could not contact WMS server")
        return None

    # Abort if a layer is not advertised by WMS server
    for layer in layers:
        if layer not in wms["layers"]:
            messages.append("Layer {} not advertised by server".format(layer))
            return None

    wms_args["version"] = wms["version"]
    if wms_args["version"] == "1.3.0":
        wms_args.pop("srs", None)
        wms_args["crs"] = "{proj}"
    else:
        wms_args.pop("crs", None)
        wms_args["srs"] = "{proj}"
    if "styles" not in wms_args:
        wms_args["styles"] = ""

    def test_proj(proj):
        if proj == "CRS:84":
            return True
        if "AUTO" in proj:
            return False
        # 'EPSG:102067' is not valid, should be ESRI:102067: https://epsg.io/102067
        if proj == "EPSG:102067":
            return False
        # 'EPSG:102066' is not valid, should be ESRI:102066: https://epsg.io/102066
        if proj == "EPSG:102066":
            return False
        if "EPSG" in proj:
            try:
                CRS.from_string(proj)
                return True
            except:
                return False
        return False

    # For multilayer WMS queries only EPSG codes are valid that are available for all layers
    new_projections = wms["layers"][layers[0]]["CRS"]
    for layer in layers[1:]:
        new_projections.intersection_update(wms["layers"][layer]["CRS"])
    new_projections = set([proj.upper() for proj in new_projections if test_proj(proj)])
    if len(new_projections) == 0:
        if len(layers) > 1:
            messages.append("No common valid projections among layers.")
        else:
            messages.append("No valid projections for layer.")
        return None

    new_wms_parameters = OrderedDict()
    for key in [
        "map",
        "layers",
        "styles",
        "format",
        "transparent",
        "crs",
        "srs",
        "width",
        "height",
        "bbox",
        "version",
        "service",
        "request",
    ]:
        if key in wms_args:
            new_wms_parameters[key] = wms_args[key]
    for key in wms_args:
        if key not in new_wms_parameters:
            new_wms_parameters[key] = wms_args[key]

    baseurl = wms_url.split("?")[0]
    url_parameters = "&".join(
        [
            "{}={}".format(key.upper(), value)
            for key, value in new_wms_parameters.items()
        ]
    )
    new_url = f"{baseurl}?{url_parameters}"

    return {"url": new_url, "available_projections": new_projections}


async def process_source(filename, session: ClientSession):

    try:
        async with aiofiles.open(filename, mode="r", encoding="utf-8") as f:
            contents = await f.read()
            source = json.loads(contents)

        # Exclude sources
        # Skip non wms layers
        if not source["properties"]["type"] == "wms":
            return
        # check if it is esri rest and not wms
        if "bboxSR" in source["properties"]["url"]:
            return
        if "available_projections" not in source["properties"]:
            return
        if "header" in source["properties"]["url"]:
            return
        if "geometry" not in source:
            return

        category = source["properties"].get("category", None)

        if source["geometry"] is None:
            geom = box(-180, -90, 180, 90)
            pt = Point(7.44, 46.56)
        else:
            geom = parse_eli_geometry(source["geometry"])
            pt = geom.representative_point()

        test_zoom_level = ZOOM_LEVEL
        if "min_zoom" in source["properties"]:
            test_zoom_level = max(source["properties"]["min_zoom"], test_zoom_level)
        if "max_zoom" in source["properties"]:
            test_zoom_level = min(source["properties"]["max_zoom"], test_zoom_level)

        old_url = source["properties"]["url"]
        old_projections = source["properties"]["available_projections"]

        # Get existing image hash
        original_img_messages = []
        status, image_hash = await get_image(
            url=old_url,
            available_projections=old_projections,
            lon=pt.x,
            lat=pt.y,
            zoom=test_zoom_level,
            session=session,
            messages=original_img_messages,
        )
        if not status == ImageHashStatus.SUCCESS or image_hash is None:
            # We are finished if it was not possible to get the image
            return

        if max_count(str(image_hash)) == 16:

            if (
                "category" in source["properties"]
                and "photo" in source["properties"]["category"]
            ):
                msgs = "\n\t".join(original_img_messages)
                logging.warning(
                    f"{filename} has category {category} but image hash is {image_hash}:\n\t{msgs}"
                )

            # These image hashes indicate that the downloaded image is not useful to determine
            # if the updated query returns the same image
            error_msgs = "\n\t".join(original_img_messages)
            logging.warning(
                f"Image hash {image_hash} not useful for: {filename} ({category}): \n\t{error_msgs}"
            )
            return

        # Update wms
        wms_messages = []
        result = await update_wms(old_url, session, wms_messages)
        if result is None:
            error_msgs = "\n\t".join(wms_messages)
            logging.info(
                f"Not possible to update wms url for {filename}:\n\t{error_msgs}"
            )
            return
        new_url = result["url"]
        new_projections = result["available_projections"]
        del result

        # Download image for updated url
        new_img_messages = []
        new_status, new_image_hash = await get_image(
            url=new_url,
            available_projections=new_projections,
            lon=pt.x,
            lat=pt.y,
            zoom=test_zoom_level,
            session=session,
            messages=new_img_messages,
        )

        if not new_status == ImageHashStatus.SUCCESS or new_image_hash is None:
            error_msgs = "\n\t".join(new_img_messages)
            logging.warning(
                f"Could not download new image: {new_status}\n\t{error_msgs}"
            )
            return

        # Only sources are updated where the new query returns the same image
        if not image_similar(image_hash, new_image_hash, test_zoom_level):
            error_original_img_messages = "\n\t".join(original_img_messages)
            error_new_img_messages = "\n\t".join(new_img_messages)
            logging.info(
                f"Image hash not the same for: {filename}: {image_hash} - {new_image_hash}: {image_hash - new_image_hash}\n\t{error_original_img_messages} \n\t{error_new_img_messages}"
            )
            return

        # Test if selected projections work despite not being advertised
        for EPSG in {"EPSG:3857", "EPSG:4326"}:
            if EPSG not in new_projections:
                epsg_check_messages = []
                epsg_image_status, epsg_image_hash = await get_image(
                    url=new_url,
                    available_projections=[EPSG],
                    lon=pt.x,
                    lat=pt.y,
                    zoom=test_zoom_level,
                    session=session,
                    messages=epsg_check_messages,
                )

                if not epsg_image_status == ImageHashStatus.SUCCESS:
                    continue

                # Relax similarity constraint to account for differences due to reprojection
                hash_diff = image_hash - epsg_image_hash
                # org_hash_msgs = "\n\t".join(original_img_messages)
                # epsg_check_msgs = "\n\t".join(epsg_check_messages)
                if image_similar(image_hash, epsg_image_hash, test_zoom_level):
                    new_projections.add(EPSG)
                    # logging.info(
                    #     f"{filename}: Add {EPSG} despite not being advertised: {epsg_image_hash} - {image_hash}: {hash_diff}\n\t{org_hash_msgs}\n\t{epsg_check_msgs}"
                    # )
                    logging.info(
                        f"{filename}: Add {EPSG} despite not being advertised: {epsg_image_hash} - {image_hash}: {hash_diff}"
                    )
                elif epsg_image_hash is not None:
                    # logging.info(
                    #     f"{filename}: Do not add {EPSG} Difference: {epsg_image_hash} - {image_hash}: {hash_diff}\n\t{org_hash_msgs}\n\t{epsg_check_msgs}"
                    # )
                    logging.info(
                        f"{filename}: Do not add {EPSG} Difference: {epsg_image_hash} - {image_hash}: {hash_diff}"
                    )

        # Servers might support projections that are not used in the area covered by a source
        # Keep only EPSG codes that are used in the area covered by the sources geometry
        if source["geometry"] is not None:
            epsg_outside_area_of_use = set()
            for epsg in new_projections:
                try:
                    if epsg == "CRS:84":
                        continue
                    crs = CRS.from_string(epsg)
                    area_of_use = crs.area_of_use
                    crs_box = box(
                        area_of_use.west,
                        area_of_use.south,
                        area_of_use.east,
                        area_of_use.north,
                    )
                    if not crs_box.intersects(geom):
                        epsg_outside_area_of_use.add(epsg)
                except Exception as e:
                    logging.exception(
                        f"Could not check area of use for projection {epsg}: {e}"
                    )
                    continue
            if len(new_projections) == len(epsg_outside_area_of_use):
                logging.error(
                    f"{filename}: epsg_outside_area_of_use filter removes all EPSG"
                )
            new_projections -= epsg_outside_area_of_use

        # Servers that report a lot of projection may be configured wrongly
        # Check for CRS:84, EPSG:3857, EPSG:4326 and keep existing projections if still advertised
        if len(new_projections) > 15:
            filtered_projs = set()
            for proj in ["CRS:84", "EPSG:3857", "EPSG:4326"]:
                if proj in new_projections:
                    filtered_projs.add(proj)
            for proj in old_projections:
                if proj in new_projections:
                    filtered_projs.add(proj)
            new_projections = filtered_projs

        # Filter alias projections
        if "EPSG:3857" in new_projections:
            new_projections -= epsg_3857_alias
        else:
            # if EPSG:3857 not present but alias, keep only alias with highest number to be consistent
            result_epsg_3857_alias = new_projections & epsg_3857_alias
            result_epsg_3857_alias_sorted = list(
                sorted(
                    result_epsg_3857_alias,
                    key=lambda x: (x.split(":")[0], int(x.split(":")[1])),
                    reverse=True,
                )
            )
            new_projections -= set(result_epsg_3857_alias_sorted[1:])

        # Filter deprecated projections
        new_projections.intersection_update(valid_epsgs)

        # Check if projections are supported by server
        not_supported_projections = set()
        image_hashes = {}
        for proj in new_projections:
            proj_messages = []
            proj_status, proj_image_hash = await get_image(
                url=new_url,
                available_projections=[proj],
                lon=pt.x,
                lat=pt.y,
                zoom=test_zoom_level,
                session=session,
                messages=proj_messages,
            )
            image_hashes[proj] = {
                "status": proj_status,
                "hash": proj_image_hash,
                "logs": proj_messages,
            }

            if proj_status == ImageHashStatus.IMAGE_ERROR:
                not_supported_projections.add(proj)
                # msgs = "\n\t".join(proj_messages)
                # logging.info(f"{filename} {proj}: {proj_status}:\n\t{msgs}")
            # elif proj_status == ImageHashStatus.SUCCESS and max_count(str(proj_image_hash)) == 16 and not max_count(str(image_hash)) == 16:
            #     # Empty images indicate that server does not support this projection correctly
            #     not_supported_projections.add(proj)
            elif proj_status == ImageHashStatus.NETWORK_ERROR:
                # If not sucessfull status do not add if not previously addedd
                if proj not in old_projections:
                    not_supported_projections.add(proj)

        if len(not_supported_projections) > 0:
            removed_projections = ",".join(not_supported_projections)
            logging.info(
                f"{filename}: remove projections that are advertised but do not return an image: {removed_projections}"
            )
            new_projections -= not_supported_projections

        # Check if EPSG:3857 and EPSG:4326 are similar
        if (
            "EPSG:3857" in image_hashes
            and "EPSG:4326" in image_hashes
            and image_hashes["EPSG:3857"]["status"] == ImageHashStatus.SUCCESS
            and image_hashes["EPSG:4326"]["status"] == ImageHashStatus.SUCCESS
        ):
            img_hash_3857 = image_hashes["EPSG:3857"]["hash"]
            img_hash_4326 = image_hashes["EPSG:4326"]["hash"]
            if not image_similar(img_hash_3857, img_hash_4326, test_zoom_level):
                msgs = "\n\t".join(
                    image_hashes["EPSG:3857"]["logs"]
                    + image_hashes["EPSG:4326"]["logs"]
                )
                logging.warning(
                    f"{filename}: ({category}) ImageHash for EPSG:3857 and EPSG:4326 not similiar: {img_hash_3857} - {img_hash_4326}: {img_hash_3857-img_hash_4326}:\n\t{msgs}"
                )

        # Check if only formatting has changed
        url_has_changed = not compare_urls(source["properties"]["url"], new_url)
        projections_have_changed = not compare_projs(
            source["properties"]["available_projections"],
            new_projections,
        )

        if url_has_changed:
            source["properties"]["url"] = new_url
        if projections_have_changed:
            source["properties"]["available_projections"] = list(
                sorted(
                    new_projections,
                    key=lambda x: (x.split(":")[0], int(x.split(":")[1])),
                )
            )

        if url_has_changed or projections_have_changed:
            with open(filename, "w", encoding="utf-8") as out:
                json.dump(source, out, indent=4, sort_keys=False, ensure_ascii=False)
                out.write("\n")
    except Exception as e:
        logging.exception(f"Failed to check source {filename}: {e}")


async def start_processing(sources_directory):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; MSIE 6.0; ELI WMS sync )"}
    timeout = aiohttp.ClientTimeout(total=180)
    conn = aiohttp.TCPConnector(limit_per_host=2)
    async with ClientSession(
        headers=headers, timeout=timeout, connector=conn
    ) as session:
        jobs = []
        files = glob.glob(
            os.path.join(sources_directory, "**", "*.geojson"), recursive=True
        )
        for filename in files:
            jobs.append(process_source(filename, session))
        await asyncio.gather(*jobs)


asyncio.run(start_processing(sources_directory))
