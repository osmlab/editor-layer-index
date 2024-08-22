import argparse
import asyncio
import glob
import io
import json
import logging
import os
import ssl
from asyncio.events import AbstractEventLoop
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import (
    Any,
    Coroutine,
    DefaultDict,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
)
from urllib.parse import parse_qsl, urlparse

import aiofiles
import aiohttp
import imagehash
import magic
import mercantile
from aiohttp import ClientSession
from imagehash import ImageHash
from libeli import eliutils, wmshelper
from PIL import Image
from pyproj.crs.crs import CRS
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.geometry.geo import shape  # type: ignore

ZOOM_LEVEL = 14
IMAGE_SIZE = 256

ignored_sources: Dict[str, str] = {}
added_projections: DefaultDict[str, DefaultDict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
removed_projections: DefaultDict[str, DefaultDict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
processed_sources: Set[str] = set()

logging.basicConfig(level=logging.ERROR)

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
sources_directory = str(args.sources)


# We ignore SSL issues as best we can
# See https://github.com/aio-libs/aiohttp/issues/7018
nossl_sslcontext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
nossl_sslcontext.check_hostname = False
nossl_sslcontext.verify_mode = ssl.CERT_NONE
nossl_sslcontext.set_ciphers("ALL")


@dataclass
class RequestResult:
    status: Optional[int] = None
    text: Optional[str] = None
    data: Optional[bytes] = None
    exception: Optional[str] = None


response_cache: Dict[str, RequestResult] = {}
domain_locks: Dict[str, asyncio.Lock] = {}
domain_lock = asyncio.Lock()


class ImageHashStatus(Enum):
    SUCCESS = 1
    IMAGE_ERROR = 2
    NETWORK_ERROR = 3
    OTHER = 4


@dataclass
class ImageResult:
    status: ImageHashStatus
    image_hash: Optional[ImageHash]  # Todo


# Before adding a new WMS version, it should be checked if every consumer supports it!
supported_wms_versions = ["1.3.0", "1.1.1", "1.1.0", "1.0.0"]


def image_similar(hash_a: ImageHash, hash_b: ImageHash, zoom: int) -> bool:  # type: ignore
    """Returns True if hash_a is considered similar to hash_b for zoom level zoom

    Parameters
    ----------
    hash_a : int
        Hash a
    hash_b : int
        Hash b
    zoom : int
        The zoom level

    Returns
    -------
    bool
        True if hash a and hash b are considered similar for zoom level.
    """
    return hash_a - hash_b < 6  # type: ignore


def max_count(elements: Sequence[Any]) -> int:
    """Return the occurrences of the most common element"""
    counts: DefaultDict[str, int] = defaultdict(int)
    for el in elements:
        counts[el] += 1
    return max(counts.items(), key=lambda x: x[1])[1]


def compare_projs(old_projs: Iterable[str], new_projs: Iterable[str]) -> bool:
    """Compare two collections of projections. Returns True if both collections contain the same elements.

    Parameters
    ----------
    old_projs : Sequence[str]
        [description]
    new_projs : Sequence[str]
        [description]

    Returns
    -------
    bool
        [description]
    """
    return set(old_projs) == set(new_projs)


def compare_urls(old_url: str, new_url: str) -> bool:
    """Compare URLs. Returns True if the urls contain the same parameters.
    Parameters

    Parameters
    ----------
    old_url : str
        [description]
    new_url : str
        [description]

    Returns
    -------
    bool
        [description]
    """
    old_parameters = parse_qsl(urlparse(old_url.lower()).query, keep_blank_values=True)
    new_parameters = parse_qsl(urlparse(new_url.lower()).query, keep_blank_values=True)
    # Fail if old url contains duplicated parameters
    if not len(set(old_parameters)) == len(old_parameters):
        return False
    return set(old_parameters) == set(new_parameters)


async def get_url(url: str, session: ClientSession, headers: Any = None) -> RequestResult:
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
                    async with session.request(method="GET", url=url, ssl=nossl_sslcontext, headers=headers) as response:
                        status = response.status

                        text = None
                        try:
                            text = await response.text()
                            encoding = eliutils.search_encoding(text)
                            if encoding is not None:
                                try:
                                    text = await response.text(encoding=encoding)
                                except Exception as e:
                                    logging.error(f"Could not read text with encoding '{encoding}': ´{e}")

                        except:
                            pass
                        data = None
                        try:
                            data = await response.read()
                        except:
                            pass
                        response_cache[url] = RequestResult(status=status, text=text, data=data)
                except asyncio.TimeoutError:
                    response_cache[url] = RequestResult(exception=f"Timeout for: {url}")
                except Exception as e:
                    logging.debug(f"Error for: {url} ({e})")
                    response_cache[url] = RequestResult(exception=f"Exception {e} for: {url}")
                if RequestResult.exception is None:
                    break
                await asyncio.sleep(15)
        else:
            logging.debug(f"Cached {url}")

        return response_cache[url]


async def get_image(
    url: str,
    available_projections: Iterable[str],
    lon: float,
    lat: float,
    zoom: int,
    session: aiohttp.ClientSession,
    messages: List[str],
) -> ImageResult:
    """Download image (tms tile for coordinate lon,lat on level zoom and calculate image hash

    Parameters
    ----------
    url : str
        [description]
    available_projections : Sequence[str]
        [description]
    lon : float
        [description]
    lat : float
        [description]
    zoom : int
        [description]
    session : aiohttp.ClientSession
        [description]
    messages : List[str]
        [description]

    Returns
    -------
    ImageResult
        [description]
    """

    tile: mercantile.Tile = list(mercantile.tiles(lon, lat, lon, lat, zooms=zoom))[0]  # type: ignore
    bounds: mercantile.LngLatBbox = mercantile.bounds(tile)  # type: ignore
    tile_bbox = eliutils.BoundingBox(west=bounds.west, east=bounds.east, north=bounds.north, south=bounds.south)  # type: ignore

    img_hash: Optional[ImageHash] = None
    status: ImageHashStatus = ImageHashStatus.OTHER

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
        return ImageResult(status, img_hash)

    wms_version = wmshelper.WMSURL(url).wms_version()

    # We assume WMS 1.3.0 if wms version is not present in the URL
    if wms_version is None:
        wms_version = "1.3.0"
    wms_bbox = wmshelper.get_bbox(proj, tile_bbox, wms_version)
    if wms_bbox is None:
        messages.append(f"Projection {proj} could not be parsed by pyproj.")
        return ImageResult(status, img_hash)

    try:
        formatted_url = url.format(proj=proj, width=IMAGE_SIZE, height=IMAGE_SIZE, bbox=wms_bbox)
    except Exception as e:
        logging.error(f"Invalid URL {url}: {e}")
        return ImageResult(status, img_hash)
    messages.append(f"Image URL: {formatted_url}")
    for i in range(2):
        try:
            # Download image
            async with session.request(method="GET", url=formatted_url, ssl=nossl_sslcontext) as response:
                messages.append(f"Try: {i}: HTTP CODE {response.status}")
                for header in response.headers:
                    messages.append(f"{header}: {response.headers[header]}")
                if response.status == 200:
                    data = await response.read()
                    data_length = len(data)
                    if data_length == 0:
                        messages.append(f"Retrieved empty body, treat as NETWORK_ERROR: {data_length}")
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
                            img_hash = imagehash.average_hash(img)  # type: ignore
                            status = ImageHashStatus.SUCCESS
                            messages.append(f"ImageHash: {img_hash}")
                            return ImageResult(status, img_hash)
                        except Exception as e:
                            status = ImageHashStatus.IMAGE_ERROR
                            messages.append(str(e))
                            filetype: str = magic.from_buffer(data)  # type: ignore
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

    return ImageResult(status, img_hash)


async def update_wms(url: str, session: ClientSession, messages: List[str]) -> Optional[Tuple[str, Set[str]]]:
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

    wms_url = wmshelper.WMSURL(url)
    layers = wms_url.layers()
    messages.append(f"Advertised layers: {','.join(layers)} for url {url}")

    old_wms_version = wms_url.wms_version()
    if old_wms_version is None:
        old_wms_version = "1.3.0"

    # Fetch highest supported WMS GetCapabilities
    wms_capabilities = None
    wms_getcapabilities_url = None
    for wms_version in supported_wms_versions:

        # Do not try versions older than in the url
        if wms_version < old_wms_version:
            continue

        try:
            wms_getcapabilities_url = wms_url.get_capabilities_url(wms_version=wms_version)
            messages.append(f"WMS url: {wms_getcapabilities_url}")
            resp = await get_url(wms_getcapabilities_url, session)

            if not resp.status == 200 or resp.text is None:
                messages.append(
                    f"Could not download GetCapabilities URL for {wms_getcapabilities_url}: HTTP Code: {resp.status} {resp.exception}"
                )
                continue

            xml = resp.text
            wms_capabilities = wmshelper.WMSCapabilities(xml)
            if wms_capabilities is not None:
                break
        except Exception as e:
            messages.append(f"Could not get GetCapabilities URL for {wms_version}: {e}")

    if wms_capabilities is None:
        # Could not request GetCapabilities
        messages.append("Could not contact WMS server. Check logs.")
        return None

    # Abort if a layer is not advertised by WMS server
    # If layer name exists but case does not match update to layer name advertised by server
    layers_advertised = wms_capabilities.layers
    layers_advertised_lower_case = {layer.lower(): layer for layer in layers_advertised}
    updated_layers: List[str] = []
    for layer in layers:
        layer_lower = layer.lower()
        if layer_lower not in layers_advertised_lower_case:
            messages.append(f"Layer {layer} not advertised by server {wms_getcapabilities_url}")
            return None
        else:
            updated_layers.append(layers_advertised_lower_case[layer_lower])

    # Use jpeg if format was not specified. But this should not happen in the first place.
    format = wms_url.format()
    if format is None:
        format = "image/jpeg"

    transparent = wms_url.is_transparent()
    # Keep transparent if format is png or gif, remove otherwise
    if transparent and not ("png" in format.lower() or "gif" in format.lower()):
        transparent = None

    new_url = wms_url.get_map_url(
        version=wms_capabilities.version,
        layers=updated_layers,
        styles=wms_url.styles(),
        crs="{proj}",
        bounds="{bbox}",
        format=format,
        width="{width}",
        height="{height}",
        transparent=transparent,
    )

    # Each layer can support different projections. GetMap queries among different layers are only possible
    # for projections supported by all layers
    new_projections = wms_capabilities.layers[updated_layers[0]].crs
    for layer in updated_layers[1:]:
        new_projections.intersection_update(wms_capabilities.layers[layer].crs)

    layer_bbox = [wms_capabilities.layers[layer].bbox for layer in updated_layers]
    layer_bbox = [layer for layer in layer_bbox if layer is not None]

    # Some server report invalid projections.
    # Remove invalid projections or projections used outside of the area of the layers
    new_projections = eliutils.clean_projections(new_projections, layer_bbox)

    if len(new_projections) == 0:
        if len(updated_layers) > 1:
            messages.append("No common valid projections among layers.")
        else:
            messages.append("No valid projections for layer.")
        return None

    return new_url, new_projections


async def process_source(filename: str, session: ClientSession):
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
            geom: MultiPolygon | Polygon = box(-180, -90, 180, 90)
            pt: Point = Point(7.44, 46.56)
        else:
            geom = shape(source["geometry"])
            pt: Point = geom.representative_point()  # type: ignore

        test_zoom_level = ZOOM_LEVEL
        if "min_zoom" in source["properties"]:
            test_zoom_level = max(source["properties"]["min_zoom"], test_zoom_level)
        if "max_zoom" in source["properties"]:
            test_zoom_level = min(source["properties"]["max_zoom"], test_zoom_level)

        old_url = source["properties"]["url"]
        old_projections = source["properties"]["available_projections"]

        # Get existing image hash
        original_img_messages: List[str] = []
        original_image_result = await get_image(
            url=old_url,
            available_projections=old_projections,
            lon=pt.x,  # type: ignore
            lat=pt.y,  # type: ignore
            zoom=test_zoom_level,
            session=session,
            messages=original_img_messages,
        )
        if not original_image_result.status == ImageHashStatus.SUCCESS or original_image_result.image_hash is None:  # type: ignore
            ignored_sources[filename] = "Not possible to download reference image"
            # We are finished if it was not possible to get the image
            return

        if max_count(str(original_image_result.image_hash)) == 16:  # type: ignore
            if "category" in source["properties"] and "photo" in source["properties"]["category"]:
                msgs = "\n\t".join(original_img_messages)
                logging.warning(f"{filename}: has category {category} but image hash is {original_image_result.image_hash}:\n\t{msgs}")  # type: ignore

            # These image hashes indicate that the downloaded image is not useful to determine
            # if the updated query returns the same image
            error_msgs = "\n\t".join(original_img_messages)
            logging.warning(f"{filename}: Image hash {original_image_result.image_hash} not useful ({category}): \n\t{error_msgs}")  # type: ignore
            ignored_sources[filename] = f"Image hash {original_image_result.image_hash} not useful ({category})"  # type: ignore
            return

        # Update wms
        wms_messages: List[str] = []
        result = await update_wms(old_url, session, wms_messages)
        if result is None:
            error_msgs = "\n\t".join(wms_messages)
            logging.info(f"{filename}: Not possible to update wms url:\n\t{error_msgs}")
            ignored_sources[filename] = "Not possible to update wms url"
            return

        new_url, new_projections = result
        del result

        # Servers that report a lot of projection may be configured wrongly
        # Check for CRS:84, EPSG:3857, EPSG:4326 and keep existing projections if still advertised
        if len(new_projections) > 15:
            filtered_projs: Set[str] = set()
            for proj in ["CRS:84", "EPSG:3857", "EPSG:4326"]:
                if proj in new_projections:
                    filtered_projs.add(proj)
            for proj in old_projections:
                if proj in new_projections:
                    filtered_projs.add(proj)
            new_projections = filtered_projs

        # Download image for updated url
        new_img_messages: List[str] = []
        updated_image_result = await get_image(
            url=new_url,
            available_projections=new_projections,
            lon=pt.x,  # type: ignore
            lat=pt.y,  # type: ignore
            zoom=test_zoom_level,
            session=session,
            messages=new_img_messages,
        )

        if not updated_image_result.status == ImageHashStatus.SUCCESS or updated_image_result.image_hash is None:  # type: ignore
            error_msgs = "\n\t".join(new_img_messages)
            logging.warning(
                f"{filename}: Could not download image with updated url: {updated_image_result.status}\n\t{error_msgs}"
            )
            ignored_sources[filename] = "Could not download image with updated url"
            return

        # Only sources are updated where the new query returns the same image
        if not image_similar(original_image_result.image_hash, updated_image_result.image_hash, test_zoom_level):  # type: ignore

            original_hash = original_image_result.image_hash  # type: ignore
            new_hash = updated_image_result.image_hash  # type: ignore
            hash_diff = original_hash - new_hash  # type: ignore

            error_original_img_messages = "\n\t".join(original_img_messages)
            error_new_img_messages = "\n\t".join(new_img_messages)
            logging.info(
                f"{filename}: ImageHash not the same for: {filename}: {original_hash} - {new_hash}: {hash_diff}\n\t{error_original_img_messages} \n\t{error_new_img_messages}"
            )
            ignored_sources[
                filename
            ] = f"ImageHash for reference image and image with updated url differs: {original_hash} - {new_hash}: {new_hash}"
            return

        # Test if selected projections work despite not being advertised
        for EPSG in {"EPSG:3857", "EPSG:4326"}:
            if EPSG not in new_projections:
                epsg_check_messages: List[str] = []
                epsg_image_result = await get_image(
                    url=new_url,
                    available_projections=[EPSG],
                    lon=pt.x,  # type: ignore
                    lat=pt.y,  # type: ignore
                    zoom=test_zoom_level,
                    session=session,
                    messages=epsg_check_messages,
                )

                epsg_check_messages_str = "\n\t".join(epsg_check_messages)
                logging.info(
                    f"{filename}: Test if projection {EPSG} works despite not advertised:\n\t{epsg_check_messages_str}"
                )

                if epsg_image_result.status == ImageHashStatus.NETWORK_ERROR:
                    if EPSG in old_projections and EPSG not in new_projections:
                        new_projections.add(EPSG)
                        added_projections[filename]["Network error, but projection was previously included."].append(
                            EPSG
                        )

                elif epsg_image_result.status == ImageHashStatus.SUCCESS:

                    epsg_image_hash = epsg_image_result.image_hash  # type: ignore
                    original_image_hash = original_image_result.image_hash  # type: ignore

                    # Relax similarity constraint to account for differences due to loss of quality due to re-projection
                    hash_diff = original_image_result.image_hash - epsg_image_result.image_hash  # type: ignore
                    if image_similar(original_image_result.image_hash, epsg_image_result.image_hash, test_zoom_level):  # type: ignore
                        new_projections.add(EPSG)
                        added_projections[filename]["Projection returns similar image despite not advertised."].append(
                            EPSG
                        )
                        logging.info(
                            f"{filename}: Add {EPSG} despite not being advertised: {epsg_image_hash} - {original_image_hash}: {hash_diff}"
                        )
                    elif epsg_image_hash is not None:
                        logging.info(
                            f"{filename}: Do not add {EPSG} Difference: {epsg_image_hash} - {original_image_hash}: {hash_diff}"
                        )
                    else:
                        logging.info(f"{filename}: Do not add {EPSG} No image returned.")

        # Check if projections are supported by server
        not_supported_projections: Set[str] = set()
        image_hashes: Dict[str, Tuple[ImageResult, List[str]]] = {}
        for proj in new_projections:
            proj_messages: List[str] = []
            epsg_image_result = await get_image(
                url=new_url,
                available_projections=[proj],
                lon=pt.x,  # type: ignore
                lat=pt.y,  # type: ignore
                zoom=test_zoom_level,
                session=session,
                messages=proj_messages,
            )

            image_hashes[proj] = (epsg_image_result, proj_messages)

            msgs = "\n\t".join(proj_messages)
            logging.info(f"{filename} Projection check: {proj}: {epsg_image_result.status}:\n\t{msgs}")

            if epsg_image_result.status == ImageHashStatus.IMAGE_ERROR:
                not_supported_projections.add(proj)
                removed_projections[filename]["Projection check: does not return an image"].append(proj)
            elif epsg_image_result.status == ImageHashStatus.NETWORK_ERROR:
                # If not successfully status do not add if not previously added
                if proj not in old_projections:
                    removed_projections[filename][
                        "Projection check: network error and previously not included"
                    ].append(proj)
                    not_supported_projections.add(proj)

        if len(not_supported_projections) > 0:
            removed = ",".join(not_supported_projections)
            logging.info(f"{filename}: remove projections that are advertised but do not return an image: {removed}")
            new_projections -= not_supported_projections

        # Check if EPSG:3857 and EPSG:4326 are similar
        if (
            "EPSG:3857" in image_hashes
            and "EPSG:4326" in image_hashes
            and image_hashes["EPSG:3857"][0].status == ImageHashStatus.SUCCESS
            and image_hashes["EPSG:4326"][0].status == ImageHashStatus.SUCCESS
        ):
            img_hash_3857 = image_hashes["EPSG:3857"][0].image_hash  # type: ignore
            img_hash_4326 = image_hashes["EPSG:4326"][0].image_hash  # type: ignore
            diff_hash = img_hash_3857 - img_hash_4326  # type: ignore
            if not image_similar(img_hash_3857, img_hash_4326, test_zoom_level):
                msgs = "\n\t".join(image_hashes["EPSG:3857"][1] + image_hashes["EPSG:4326"][1])
                logging.warning(
                    f"{filename}: ({category}) ImageHash for EPSG:3857 and EPSG:4326 not similar: {img_hash_3857} - {img_hash_4326}: {diff_hash}:\n\t{msgs}"
                )

        # Check projections again to filter out EPSG:3857 alias
        new_projections = eliutils.clean_projections(new_projections)

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
        logging.exception(f"{filename}: Error occurred while processing source: {e}")


def handle_exception(loop: AbstractEventLoop, context: Dict[Any, Any]):
    msg = context.get("exception", context["message"])
    logging.error(f"This should not happen: Caught unhandled exception: {msg} {context}")


async def start_processing(sources_directory: str):

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)

    headers = {"User-Agent": "Mozilla/5.0 (compatible; WMSsync; +https://github.com/osmlab/editor-layer-index)"}
    timeout = aiohttp.ClientTimeout(total=600)
    conn = aiohttp.TCPConnector(limit_per_host=1)
    async with ClientSession(headers=headers, timeout=timeout, connector=conn) as session:
        jobs: List[Coroutine[Any, Any, None]] = []
        files = glob.glob(os.path.join(sources_directory, "**", "*.geojson"), recursive=True)
        for filename in files:
            jobs.append(process_source(filename, session))
        await asyncio.gather(*jobs)

    print("")
    print("")
    print("Report:")
    print("")
    print(f"Processed {len(processed_sources)} sources")
    print("")
    if (len(processed_sources)) > 0:
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
