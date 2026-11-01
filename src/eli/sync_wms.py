"""Synchronize WMS source URLs and supported projections."""

import asyncio
import io
import json
import logging
import ssl
import xml.etree.ElementTree as ET
from asyncio.events import AbstractEventLoop
from collections import defaultdict
from collections.abc import Coroutine, Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

import aiofiles
import aiohttp
import imagehash
import magic
import mercantile
from aiohttp import ClientSession
from imagehash import ImageHash
from PIL import Image
from shapely.geometry import Point, box
from shapely.geometry.base import BaseGeometry
from shapely.geometry.geo import shape

from eli.libeli import eliutils, wmshelper
from eli.projections import unused_projections

ZOOM_LEVEL = 14
IMAGE_SIZE = 256


@dataclass
class RequestResult:
    """Cached HTTP response data or its transport failure."""

    status: int | None = None
    text: str | None = None
    data: bytes | None = None
    exception: str | None = None


class ImageHashStatus(Enum):
    """Distinguish successful image hashing from transport and decoding failures."""

    SUCCESS = 1
    IMAGE_ERROR = 2
    NETWORK_ERROR = 3
    OTHER = 4


@dataclass
class ImageResult:
    """Image-comparison outcome and the optional computed hash."""

    status: ImageHashStatus
    image_hash: ImageHash | None


# One sync run owns its separate caches, locks, projection sets, and reporting counters.
# pylint: disable-next=R0902
class WMSSync:
    """One WMS sync run, including its response cache, locks, and report."""

    def __init__(self) -> None:
        self.ignored_sources: dict[str, str] = {}
        self.added_projections: defaultdict[str, defaultdict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self.removed_projections: defaultdict[str, defaultdict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self.processed_sources: set[str] = set()
        self.nossl_sslcontext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.response_cache: dict[str, RequestResult] = {}
        self.domain_locks: dict[str, asyncio.Lock] = {}
        self.domain_lock = asyncio.Lock()
        self.supported_wms_versions = ["1.3.0", "1.1.1", "1.1.0", "1.0.0"]
        self.failures = 0
        self.nossl_sslcontext.check_hostname = False
        self.nossl_sslcontext.verify_mode = ssl.CERT_NONE
        self.nossl_sslcontext.set_ciphers("ALL")

    def image_similar(self, hash_a: ImageHash, hash_b: ImageHash) -> bool:
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
        return bool(hash_a - hash_b < 6)

    def max_count(self, elements: Sequence[Any]) -> int:
        """Return the occurrences of the most common element"""
        counts: defaultdict[str, int] = defaultdict(int)
        for el in elements:
            counts[el] += 1
        return max(counts.items(), key=lambda x: x[1])[1]

    def compare_projs(self, old_projs: Iterable[str], new_projs: Iterable[str]) -> bool:
        """Return whether two projection collections contain the same elements.

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

    def compare_urls(self, old_url: str, new_url: str) -> bool:
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
        if not len(set(old_parameters)) == len(old_parameters):
            return False
        return set(old_parameters) == set(new_parameters)

    async def get_url(self, url: str, session: ClientSession, headers: Any = None) -> RequestResult:
        """Fetch url.

        Send one request per domain at a time and cache each URL so it is not
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
        async with self.domain_lock:
            if o.netloc not in self.domain_locks:
                self.domain_locks[o.netloc] = asyncio.Lock()
            lock = self.domain_locks[o.netloc]
        async with lock:
            if url not in self.response_cache:
                for attempt in range(3):
                    try:
                        logging.debug("GET %s", url)
                        async with session.request(
                            method="GET", url=url, ssl=self.nossl_sslcontext, headers=headers
                        ) as response:
                            status = response.status
                            text = None
                            try:
                                text = await response.text()
                                encoding = eliutils.search_encoding(text)
                                if encoding is not None:
                                    try:
                                        text = await response.text(encoding=encoding)
                                    except (
                                        aiohttp.ClientError,
                                        OSError,
                                        UnicodeError,
                                        LookupError,
                                    ) as e:
                                        logging.error(
                                            "Could not read text with encoding '%s': ´%s",
                                            encoding,
                                            e,
                                        )
                            except (
                                aiohttp.ClientError,
                                OSError,
                                UnicodeError,
                                LookupError,
                            ):
                                pass
                            data = None
                            try:
                                data = await response.read()
                            except (
                                aiohttp.ClientError,
                                OSError,
                                UnicodeError,
                                LookupError,
                            ):
                                pass
                            self.response_cache[url] = RequestResult(
                                status=status, text=text, data=data
                            )
                    except (
                        aiohttp.ClientError,
                        OSError,
                        UnicodeError,
                        LookupError,
                    ) as e:
                        logging.debug("Error for: %s (%s)", url, e)
                        self.response_cache[url] = RequestResult(
                            exception=f"Exception {e} for: {url}"
                        )
                    if self.response_cache[url].exception is None:
                        break
                    if attempt < 2:
                        await asyncio.sleep(15)
            else:
                logging.debug("Cached %s", url)
            return self.response_cache[url]

    # A tile probe needs explicit URL, projection, location, zoom, session, and diagnostic inputs.
    # pylint: disable-next=R0912,R0913,R0914,R0915
    async def get_image(
        self,
        *,
        url: str,
        available_projections: Iterable[str],
        lon: float,
        lat: float,
        zoom: int,
        session: aiohttp.ClientSession,
        messages: list[str],
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
        tile: mercantile.Tile = list(mercantile.tiles(lon, lat, lon, lat, zooms=zoom))[0]
        bounds: mercantile.LngLatBbox = mercantile.bounds(tile)
        tile_bbox = eliutils.BoundingBox(
            west=bounds.west, east=bounds.east, north=bounds.north, south=bounds.south
        )
        img_hash: ImageHash | None = None
        status: ImageHashStatus = ImageHashStatus.OTHER
        proj = eliutils.preferred_projection(available_projections)
        if proj is None:
            messages.append(f"No projection left: {available_projections}")
            return ImageResult(status, img_hash)
        wms_version = wmshelper.WMSURL(url).wms_version()
        if wms_version is None:
            wms_version = "1.3.0"
        wms_bbox = wmshelper.get_bbox(proj, tile_bbox, wms_version)
        if wms_bbox is None:
            messages.append(f"Projection {proj} could not be parsed by pyproj.")
            return ImageResult(status, img_hash)
        try:
            formatted_url = url.format(
                proj=proj, width=IMAGE_SIZE, height=IMAGE_SIZE, bbox=wms_bbox
            )
        except (KeyError, IndexError, ValueError) as e:
            logging.error("Invalid URL %s: %s", url, e)
            return ImageResult(status, img_hash)
        messages.append(f"Image URL: {formatted_url}")
        for i in range(2):
            try:
                async with session.request(
                    method="GET", url=formatted_url, ssl=self.nossl_sslcontext
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
                                        (
                                            f"Body not same size as advertised: {data_length} vs "
                                            f"{advertised_length}"
                                        )
                                    )
                            try:
                                img = Image.open(io.BytesIO(data))
                                img_hash = imagehash.average_hash(img)
                                status = ImageHashStatus.SUCCESS
                                messages.append(f"ImageHash: {img_hash}")
                                return ImageResult(status, img_hash)
                            except (OSError, ValueError, Image.DecompressionBombError) as e:
                                status = ImageHashStatus.IMAGE_ERROR
                                messages.append(str(e))
                                filetype: str = magic.from_buffer(data)
                                messages.append(
                                    (
                                        "Could not open received data "
                                        f"as image (Received filetype: {filetype} Body Length: "
                                        f"{data_length} {formatted_url})"
                                    )
                                )
                    else:
                        status = ImageHashStatus.NETWORK_ERROR
                    if response.status == 503:
                        await asyncio.sleep(30)
            except (OSError, ValueError, Image.DecompressionBombError) as e:
                status = ImageHashStatus.NETWORK_ERROR
                messages.append(f"Could not download image in try {i}: {e}")
            await asyncio.sleep(15)
        return ImageResult(status, img_hash)

    # Resolve matching layer styles, WMS version, and projection intersections together.
    # pylint: disable-next=R0912,R0914,R0915
    async def update_wms(
        self, url: str, session: ClientSession, messages: list[str]
    ) -> tuple[str, set[str]] | None:
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
        wms_capabilities = None
        wms_getcapabilities_url = None
        for wms_version in self.supported_wms_versions:
            if wms_version < old_wms_version:
                continue
            try:
                wms_getcapabilities_url = wms_url.get_capabilities_url(wms_version=wms_version)
                messages.append(f"WMS url: {wms_getcapabilities_url}")
                resp = await self.get_url(wms_getcapabilities_url, session)
                if not resp.status == 200 or resp.text is None:
                    messages.append(
                        (
                            "Could not download GetCapabilities URL for "
                            f"{wms_getcapabilities_url}: HTTP Code: {resp.status} "
                            f"{resp.exception}"
                        )
                    )
                    continue
                xml = resp.text
                wms_capabilities = wmshelper.WMSCapabilities(xml)
                if wms_capabilities is not None:
                    break
            except (ET.ParseError, RuntimeError, ValueError, KeyError) as e:
                messages.append(f"Could not get GetCapabilities URL for {wms_version}: {e}")
        if wms_capabilities is None:
            messages.append("Could not contact WMS server. Check logs.")
            return None
        layers_advertised = wms_capabilities.layers
        layers_advertised_lower_case = {layer.lower(): layer for layer in layers_advertised}
        updated_layers: list[str] = []
        for layer in layers:
            layer_lower = layer.lower()
            if layer_lower not in layers_advertised_lower_case:
                messages.append(f"Layer {layer} not advertised by server {wms_getcapabilities_url}")
                return None
            updated_layers.append(layers_advertised_lower_case[layer_lower])
        image_format = wms_url.format()
        if image_format is None:
            image_format = "image/jpeg"
        transparent = wms_url.is_transparent()
        if transparent and (not ("png" in image_format.lower() or "gif" in image_format.lower())):
            transparent = None
        new_url = wms_url.get_map_url(
            version=wms_capabilities.version,
            layers=updated_layers,
            styles=wms_url.styles(),
            crs="{proj}",
            bounds="{bbox}",
            image_format=image_format,
            width="{width}",
            height="{height}",
            transparent=transparent,
        )
        new_projections = wms_capabilities.layers[updated_layers[0]].crs
        for layer in updated_layers[1:]:
            new_projections.intersection_update(wms_capabilities.layers[layer].crs)
        layer_bbox: list[eliutils.BoundingBox] = []
        for layer in updated_layers:
            bounds = wms_capabilities.layers[layer].bbox
            if bounds is not None:
                layer_bbox.append(bounds)
        new_projections = eliutils.clean_projections(new_projections, layer_bbox)
        if len(new_projections) == 0:
            if len(updated_layers) > 1:
                messages.append("No common valid projections among layers.")
            else:
                messages.append("No valid projections for layer.")
            return None
        new_projections -= unused_projections(new_projections, new_url)
        return (new_url, new_projections)

    # Conservative projection updates share the original source and image-comparison baseline.
    # pylint: disable-next=R0911,R0912,R0914,R0915
    async def process_source(self, filename: str, session: ClientSession) -> None:
        try:
            async with aiofiles.open(filename, encoding="utf-8") as f:
                contents = await f.read()
                source = json.loads(contents)
            if not source["properties"]["type"] == "wms":
                return
            if "bboxSR" in source["properties"]["url"]:
                return
            if "available_projections" not in source["properties"]:
                return
            if "header" in source["properties"]["url"]:
                return
            if "geometry" not in source:
                return
            self.processed_sources.add(filename)
            category = source["properties"].get("category", None)
            if source["geometry"] is None:
                geom: BaseGeometry = box(-180, -90, 180, 90)
                pt: Point = Point(7.44, 46.56)
            else:
                geom = shape(source["geometry"])
                pt = geom.representative_point()
            test_zoom_level = ZOOM_LEVEL
            if "min_zoom" in source["properties"]:
                test_zoom_level = max(source["properties"]["min_zoom"], test_zoom_level)
            if "max_zoom" in source["properties"]:
                test_zoom_level = min(source["properties"]["max_zoom"], test_zoom_level)
            old_url = source["properties"]["url"]
            old_projections = source["properties"]["available_projections"]
            original_img_messages: list[str] = []
            original_image_result = await self.get_image(
                url=old_url,
                available_projections=old_projections,
                lon=pt.x,
                lat=pt.y,
                zoom=test_zoom_level,
                session=session,
                messages=original_img_messages,
            )
            if (
                not original_image_result.status == ImageHashStatus.SUCCESS
                or original_image_result.image_hash is None
            ):
                self.ignored_sources[filename] = "Not possible to download reference image"
                return
            if self.max_count(str(original_image_result.image_hash)) == 16:
                if (
                    "category" in source["properties"]
                    and "photo" in source["properties"]["category"]
                ):
                    msgs = "\n\t".join(original_img_messages)
                    logging.warning(
                        "%s: has category %s but image hash is %s:\n\t%s",
                        filename,
                        category,
                        original_image_result.image_hash,
                        msgs,
                    )
                error_msgs = "\n\t".join(original_img_messages)
                logging.warning(
                    "%s: Image hash %s not useful (%s): \n\t%s",
                    filename,
                    original_image_result.image_hash,
                    category,
                    error_msgs,
                )
                self.ignored_sources[filename] = (
                    f"Image hash {original_image_result.image_hash} not useful ({category})"
                )
                return
            wms_messages: list[str] = []
            result = await self.update_wms(old_url, session, wms_messages)
            if result is None:
                error_msgs = "\n\t".join(wms_messages)
                logging.info("%s: Not possible to update wms url:\n\t%s", filename, error_msgs)
                self.ignored_sources[filename] = "Not possible to update wms url"
                return
            new_url, new_projections = result
            del result
            if len(new_projections) > 15:
                filtered_projs: set[str] = set()
                for proj in ["CRS:84", "EPSG:3857", "EPSG:4326"]:
                    if proj in new_projections:
                        filtered_projs.add(proj)
                for proj in old_projections:
                    if proj in new_projections:
                        filtered_projs.add(proj)
                new_projections = filtered_projs
            new_img_messages: list[str] = []
            updated_image_result = await self.get_image(
                url=new_url,
                available_projections=new_projections,
                lon=pt.x,
                lat=pt.y,
                zoom=test_zoom_level,
                session=session,
                messages=new_img_messages,
            )
            if (
                not updated_image_result.status == ImageHashStatus.SUCCESS
                or updated_image_result.image_hash is None
            ):
                error_msgs = "\n\t".join(new_img_messages)
                logging.warning(
                    "%s: Could not download image with updated url: %s\n\t%s",
                    filename,
                    updated_image_result.status,
                    error_msgs,
                )
                self.ignored_sources[filename] = "Could not download image with updated url"
                return
            if not self.image_similar(
                original_image_result.image_hash, updated_image_result.image_hash
            ):
                original_hash = original_image_result.image_hash
                new_hash = updated_image_result.image_hash
                hash_diff = original_hash - new_hash
                error_original_img_messages = "\n\t".join(original_img_messages)
                error_new_img_messages = "\n\t".join(new_img_messages)
                logging.info(
                    "%s: ImageHash not the same for: %s: %s - %s: %s\n\t%s \n\t%s",
                    filename,
                    filename,
                    original_hash,
                    new_hash,
                    hash_diff,
                    error_original_img_messages,
                    error_new_img_messages,
                )
                self.ignored_sources[filename] = (
                    "ImageHash for reference image and image with updated url differs: "
                    f"{original_hash} - {new_hash}: {new_hash}"
                )
                return
            for epsg in ("EPSG:3857", "EPSG:4326"):
                if epsg not in new_projections:
                    epsg_check_messages: list[str] = []
                    epsg_image_result = await self.get_image(
                        url=new_url,
                        available_projections=[epsg],
                        lon=pt.x,
                        lat=pt.y,
                        zoom=test_zoom_level,
                        session=session,
                        messages=epsg_check_messages,
                    )
                    epsg_check_messages_str = "\n\t".join(epsg_check_messages)
                    logging.info(
                        "%s: Test if projection %s works despite not advertised:\n\t%s",
                        filename,
                        epsg,
                        epsg_check_messages_str,
                    )
                    if epsg_image_result.status == ImageHashStatus.NETWORK_ERROR:
                        if epsg in old_projections and epsg not in new_projections:
                            new_projections.add(epsg)
                            self.added_projections[filename][
                                "Network error, but projection was previously included."
                            ].append(epsg)
                    elif epsg_image_result.status == ImageHashStatus.SUCCESS:
                        epsg_image_hash = epsg_image_result.image_hash
                        original_image_hash = original_image_result.image_hash
                        assert original_image_hash is not None and epsg_image_hash is not None
                        hash_diff = original_image_hash - epsg_image_hash
                        if self.image_similar(original_image_hash, epsg_image_hash):
                            new_projections.add(epsg)
                            self.added_projections[filename][
                                "Projection returns similar image despite not advertised."
                            ].append(epsg)
                            logging.info(
                                "%s: Add %s despite not being advertised: %s - %s: %s",
                                filename,
                                epsg,
                                epsg_image_hash,
                                original_image_hash,
                                hash_diff,
                            )
                        elif epsg_image_hash is not None:
                            logging.info(
                                "%s: Do not add %s Difference: %s - %s: %s",
                                filename,
                                epsg,
                                epsg_image_hash,
                                original_image_hash,
                                hash_diff,
                            )
                        else:
                            logging.info("%s: Do not add %s No image returned.", filename, epsg)
            not_supported_projections: set[str] = set()
            image_hashes: dict[str, tuple[ImageResult, list[str]]] = {}
            for proj in new_projections:
                proj_messages: list[str] = []
                epsg_image_result = await self.get_image(
                    url=new_url,
                    available_projections=[proj],
                    lon=pt.x,
                    lat=pt.y,
                    zoom=test_zoom_level,
                    session=session,
                    messages=proj_messages,
                )
                image_hashes[proj] = (epsg_image_result, proj_messages)
                msgs = "\n\t".join(proj_messages)
                logging.info(
                    "%s Projection check: %s: %s:\n\t%s",
                    filename,
                    proj,
                    epsg_image_result.status,
                    msgs,
                )
                if epsg_image_result.status == ImageHashStatus.IMAGE_ERROR:
                    not_supported_projections.add(proj)
                    self.removed_projections[filename][
                        "Projection check: does not return an image"
                    ].append(proj)
                elif epsg_image_result.status == ImageHashStatus.NETWORK_ERROR:
                    if proj not in old_projections:
                        self.removed_projections[filename][
                            "Projection check: network error and previously not included"
                        ].append(proj)
                        not_supported_projections.add(proj)
            if len(not_supported_projections) > 0:
                removed = ",".join(not_supported_projections)
                logging.info(
                    "%s: remove projections that are advertised but do not return an image: %s",
                    filename,
                    removed,
                )
                new_projections -= not_supported_projections
            if (
                "EPSG:3857" in image_hashes
                and "EPSG:4326" in image_hashes
                and (image_hashes["EPSG:3857"][0].status == ImageHashStatus.SUCCESS)
                and (image_hashes["EPSG:4326"][0].status == ImageHashStatus.SUCCESS)
            ):
                img_hash_3857 = image_hashes["EPSG:3857"][0].image_hash
                img_hash_4326 = image_hashes["EPSG:4326"][0].image_hash
                assert img_hash_3857 is not None and img_hash_4326 is not None
                diff_hash = img_hash_3857 - img_hash_4326
                if not self.image_similar(img_hash_3857, img_hash_4326):
                    msgs = "\n\t".join(image_hashes["EPSG:3857"][1] + image_hashes["EPSG:4326"][1])
                    logging.warning(
                        (
                            "%s: (%s) ImageHash for EPSG:3857 and EPSG:4326 not similar: %s - "
                            "%s: %s:\n\t%s"
                        ),
                        filename,
                        category,
                        img_hash_3857,
                        img_hash_4326,
                        diff_hash,
                        msgs,
                    )
            new_projections = eliutils.clean_projections(new_projections)
            new_projections -= unused_projections(new_projections, new_url)
            url_has_changed = not self.compare_urls(source["properties"]["url"], new_url)
            projections_have_changed = not self.compare_projs(
                source["properties"]["available_projections"], new_projections
            )
            if url_has_changed:
                source["properties"]["url"] = new_url
            if projections_have_changed:
                source["properties"]["available_projections"] = list(
                    sorted(new_projections, key=lambda x: (x.split(":")[0], int(x.split(":")[1])))
                )
            if url_has_changed or projections_have_changed:
                with open(filename, "w", encoding="utf-8") as out:
                    json.dump(source, out, indent=4, sort_keys=False, ensure_ascii=False)
                    out.write("\n")
        # Each independent WMS source must report unexpected failures without aborting the full
        # sync.
        # pylint: disable-next=broad-exception-caught
        except Exception as e:
            self.failures += 1
            logging.exception("%s: Error occurred while processing source: %s", filename, e)

    def handle_exception(self, loop: AbstractEventLoop, context: dict[Any, Any]) -> None:
        """Count unexpected task failures and let asyncio preserve their full traceback."""
        self.failures += 1
        loop.default_exception_handler(context)

    async def start_processing(self, files: list[Path]) -> None:
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(self.handle_exception)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; WMSsync; +https://github.com/osmlab/editor-layer-index)"
            )
        }
        timeout = aiohttp.ClientTimeout(total=600)
        conn = aiohttp.TCPConnector(limit_per_host=1)
        async with ClientSession(headers=headers, timeout=timeout, connector=conn) as session:
            jobs: list[Coroutine[Any, Any, None]] = []

            for path in files:
                jobs.append(self.process_source(str(path), session))
            await asyncio.gather(*jobs)
        print("")
        print("")
        print("Report:")
        print("")
        print(f"Processed {len(self.processed_sources)} sources")
        print("")
        if len(self.processed_sources) > 0:
            print(
                (
                    "Ignored sources: ("
                    f"{len(self.ignored_sources)}"
                    " / "
                    f"{round(len(self.ignored_sources) / len(self.processed_sources) * 100, 1)}"
                    "%)"
                )
            )
            for filename, reason in self.ignored_sources.items():
                print(f"\t{filename}: {reason}")
            print("")
            print("Removed projections:")
            for filename in self.removed_projections:
                for reason in self.removed_projections[filename]:
                    projs_str = ",".join(self.removed_projections[filename][reason])
                    print(f"\t{filename}: {reason}: {projs_str}")
            print("")
            print("Added projections:")
            for filename in self.added_projections:
                for reason in self.added_projections[filename]:
                    projs_str = ",".join(self.added_projections[filename][reason])
                    print(f"\t{filename}: {reason}: {projs_str}")
