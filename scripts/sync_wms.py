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
from libeli import wmshelper
from libeli import eliutils

ZOOM_LEVEL = 14
IMAGE_SIZE = 256

ignored_sources = {}
added_projections = defaultdict(lambda: defaultdict(list))
removed_projections = defaultdict(lambda: defaultdict(list))
processed_sources = set()

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
            for _ in range(3):
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
                await asyncio.sleep(15)
        else:
            logging.debug(f"Cached {url}")

        return response_cache[url]


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
        messages.append(f"No projection left: {available_projections}")
        return status, img_hash

    wms_version = wmshelper.wms_version_from_url(url)
    bbox = wmshelper.get_bbox(proj, bounds, wms_version)
    if bbox is None:
        messages.append(f"Projection {proj} could not be parsed by pyproj.")
        return status, img_hash

    formatted_url = url.format(
        proj=proj, width=IMAGE_SIZE, height=IMAGE_SIZE, bbox=bbox
    )
    messages.append(f"Image URL: {formatted_url}")
    for i in range(2):
        try:
            # Download image
            async with session.request(
                method="GET", url=formatted_url, ssl=False
            ) as response:
                messages.append(f"Try: {i}: HTTP CODE {response.status}")
                for header in response.headers:
                    messages.append(f"{header}: {response.headers[header]}")
                if response.status == 200:
                    data = await response.read()
                    data_length = len(data)
                    if data_length == 0:
                        messages.append(
                            f"Retrieved empty body, treat as NETWORK_ERROR: {data_length}"
                        )
                        status = ImageHashStatus.NETWORK_ERROR
                    else:
                        messages.append(f"len(data): {data_length}")
                        if "Content-Length" in response.headers:
                            advertised_length = int(response.headers["Content-Length"])
                            if not data_length == advertised_length:
                                messages.append(
                                    f"Body not same size as advertised: {data_length} vs {advertised_length}"
                                )
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
                                f"Could not open received data as image (Received filetype: {filetype} Body Length: {data_length} {formatted_url})"
                            )
                else:
                    status = ImageHashStatus.NETWORK_ERROR

                if response.status == 503:  # 503 Service Unavailable
                    await asyncio.sleep(30)

        except Exception as e:
            status = ImageHashStatus.NETWORK_ERROR
            messages.append(f"Could not download image in try {i}: {e}")
        await asyncio.sleep(15)

    return status, img_hash


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
    for k, v in parse_qsl(u.query, keep_blank_values=True):
        wms_args[k.lower()] = v

    layers = wms_args["layers"].split(",")

    # Fetch highest supported WMS GetCapabilities
    wms = None
    for wmsversion in supported_wms_versions:
        # Do not try versions older than in the url
        if wmsversion < wms_args["version"]:
            continue

        try:
            wms_getcapabilites_url = wmshelper.get_getcapabilities_url(
                wms_url, wmsversion
            )
            messages.append(f"WMS url: {wms_getcapabilites_url}")
            resp = await get_url(wms_getcapabilites_url, session, with_text=True)
            if resp.exception is not None:
                messages.append(
                    f"Could not download GetCapabilites URL for {wms_getcapabilites_url}: {resp.exception}"
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

            wms = wmshelper.parse_wms(xml)
            if wms is not None:
                break
        except Exception as e:
            messages.append(f"Could not get GetCapabilites URL for {wmsversion}: {e}")

    if wms is None:
        # Could not request GetCapabilities
        messages.append("Could not contact WMS server")
        return None

    # Abort if a layer is not advertised by WMS server
    # If layer name exists but case does not match update to layer name advertised by server
    layers_advertised = wms["layers"]
    layers_advertised_lower_case = {layer.lower(): layer for layer in layers_advertised}
    updated_layers = []
    for layer in layers:
        layer_lower = layer.lower()
        if layer_lower not in layers_advertised_lower_case:
            messages.append(
                f"Layer {layer} not advertised by server {wms_getcapabilites_url}"
            )
            return None
        else:
            updated_layers.append(layers_advertised_lower_case[layer_lower])
    layers = updated_layers

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
        processed_sources.add(filename)

        category = source["properties"].get("category", None)

        if source["geometry"] is None:
            geom = box(-180, -90, 180, 90)
            pt = Point(7.44, 46.56)
        else:
            geom = eliutils.parse_eli_geometry(source["geometry"])
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
            ignored_sources[filename] = "Not possible to download reference image"
            # We are finished if it was not possible to get the image
            return

        if max_count(str(image_hash)) == 16:

            if (
                "category" in source["properties"]
                and "photo" in source["properties"]["category"]
            ):
                msgs = "\n\t".join(original_img_messages)
                logging.warning(
                    f"{filename}: has category {category} but image hash is {image_hash}:\n\t{msgs}"
                )

            # These image hashes indicate that the downloaded image is not useful to determine
            # if the updated query returns the same image
            error_msgs = "\n\t".join(original_img_messages)
            logging.warning(
                f"{filename}: Image hash {image_hash} not useful ({category}): \n\t{error_msgs}"
            )
            ignored_sources[
                filename
            ] = f"Image hash {image_hash} not useful ({category})"
            return

        # Update wms
        wms_messages = []
        result = await update_wms(old_url, session, wms_messages)
        if result is None:
            error_msgs = "\n\t".join(wms_messages)
            logging.info(f"{filename}: Not possible to update wms url:\n\t{error_msgs}")
            ignored_sources[filename] = "Not possible to update wms url"
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
                f"{filename}: Could not download image with updated url: {new_status}\n\t{error_msgs}"
            )
            ignored_sources[filename] = "Could not download image with updated url"
            return

        # Only sources are updated where the new query returns the same image
        if not image_similar(image_hash, new_image_hash, test_zoom_level):
            error_original_img_messages = "\n\t".join(original_img_messages)
            error_new_img_messages = "\n\t".join(new_img_messages)
            logging.info(
                f"{filename}: ImageHash not the same for: {filename}: {image_hash} - {new_image_hash}: {image_hash - new_image_hash}\n\t{error_original_img_messages} \n\t{error_new_img_messages}"
            )
            ignored_sources[
                filename
            ] = f"ImageHash for reference image and image with updated url differs: {image_hash} - {new_image_hash}: {image_hash - new_image_hash}"
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

                epsg_check_messages_str = "\n\t".join(epsg_check_messages)
                logging.info(
                    f"{filename}: Test if projection {EPSG} works despite not advertised:\n\t{epsg_check_messages_str}"
                )

                if epsg_image_status == ImageHashStatus.NETWORK_ERROR:
                    if EPSG in old_projections and EPSG not in new_projections:
                        new_projections.add(EPSG)
                        added_projections[filename][
                            "Network error, but projection was previously included."
                        ].append(EPSG)

                elif epsg_image_status == ImageHashStatus.SUCCESS:

                    # Relax similarity constraint to account for differences due to reprojection
                    hash_diff = image_hash - epsg_image_hash
                    if image_similar(image_hash, epsg_image_hash, test_zoom_level):
                        new_projections.add(EPSG)
                        added_projections[filename][
                            "Projection returns similar image despite not advertised."
                        ].append(EPSG)
                        logging.info(
                            f"{filename}: Add {EPSG} despite not being advertised: {epsg_image_hash} - {image_hash}: {hash_diff}"
                        )
                    elif epsg_image_hash is not None:
                        logging.info(
                            f"{filename}: Do not add {EPSG} Difference: {epsg_image_hash} - {image_hash}: {hash_diff}"
                        )
                    else:
                        logging.info(
                            f"{filename}: Do not add {EPSG} No image returned."
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
                        f"{filename}: Could not check area of use for projection {epsg}: {e}"
                    )
                    continue
            if len(new_projections) == len(epsg_outside_area_of_use):
                logging.error(
                    f"{filename}: epsg_outside_area_of_use filter removes all EPSG"
                )
            if len(epsg_outside_area_of_use) > 0:

                if len(epsg_outside_area_of_use) <= 10:
                    removed_projections[filename]["EPSG outside area of use"].extend(
                        list(epsg_outside_area_of_use)
                    )
                else:
                    removed_projections[filename]["EPSG outside area of use"].extend(
                        list(epsg_outside_area_of_use)[:10]
                        + ["...", f"+ {len(epsg_outside_area_of_use)-10} more"]
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
            included_alias_projections = new_projections.intersection(
                wmshelper.epsg_3857_alias
            )
            if len(included_alias_projections) > 0:
                removed_projections[filename]["Alias projections"].extend(
                    list(included_alias_projections)
                )
                new_projections -= included_alias_projections
        else:
            # if EPSG:3857 not present but alias, keep only alias with highest number to be consistent
            result_epsg_3857_alias = new_projections & wmshelper.epsg_3857_alias
            result_epsg_3857_alias_sorted = list(
                sorted(
                    result_epsg_3857_alias,
                    key=lambda x: (x.split(":")[0], int(x.split(":")[1])),
                    reverse=True,
                )
            )
            if len(result_epsg_3857_alias_sorted) > 1:
                removed_projections[filename]["Alias projections"].extend(
                    list(result_epsg_3857_alias_sorted[1:])
                )
            new_projections -= set(result_epsg_3857_alias_sorted[1:])

        # Filter deprecated projections
        if len(new_projections - wmshelper.valid_epsgs) > 0:
            removed_projections[filename]["Deprecated projections"].extend(
                list(new_projections - wmshelper.valid_epsgs)
            )
        new_projections.intersection_update(wmshelper.valid_epsgs)

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

            msgs = "\n\t".join(proj_messages)
            logging.info(
                f"{filename} Projection check: {proj}: {proj_status}:\n\t{msgs}"
            )

            if proj_status == ImageHashStatus.IMAGE_ERROR:
                not_supported_projections.add(proj)
                removed_projections[filename][
                    "Projection check: does not return an image"
                ].append(proj)
            elif proj_status == ImageHashStatus.NETWORK_ERROR:
                # If not sucessfull status do not add if not previously addedd
                if proj not in old_projections:
                    removed_projections[filename][
                        "Projection check: network error and previously not included"
                    ].append(proj)
                    not_supported_projections.add(proj)

        if len(not_supported_projections) > 0:
            removed = ",".join(not_supported_projections)
            logging.info(
                f"{filename}: remove projections that are advertised but do not return an image: {removed}"
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
        logging.exception(f"{filename}: Error occured while processing source: {e}")


async def start_processing(sources_directory):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; WMSsync; +https://github.com/osmlab/editor-layer-index)"
    }
    timeout = aiohttp.ClientTimeout(total=600)
    conn = aiohttp.TCPConnector(limit_per_host=1)
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

    print("")
    print("")
    print("Report:")
    print("")
    print(f"Processed {len(processed_sources)} sources")
    print("")
    print(
        f"Ignored sources: ({len(ignored_sources)} / {round(len(ignored_sources)/ len(processed_sources) * 100, 1)}%)"
    )
    for filename in ignored_sources:
        print(f"\t{filename}: {ignored_sources[filename]}")
    print("")
    print("Removed projections:")
    for filename in removed_projections:
        for reason in removed_projections[filename]:
            projs_str = ",".join(removed_projections[filename][reason])
            print(f"\t{filename}: {reason}: {projs_str}")
    print("")
    print("Added projections:")
    for filename in added_projections:
        for reason in added_projections[filename]:
            projs_str = ",".join(added_projections[filename][reason])
            print(f"\t{filename}: {reason}: {projs_str}")


asyncio.run(start_processing(sources_directory))
