"""Preview imagery tiles and interactively select minimum zoom."""

import asyncio
import glob
import io
import json
import logging
import os
import re
from collections import defaultdict
from collections.abc import Iterable
from enum import Enum
from typing import Any
from urllib.parse import parse_qsl, urlparse

import aiofiles
import aiohttp
import imagehash
import mercantile
from aiohttp import ClientSession
from PIL import Image
from pyproj import CRS, Transformer
from pyproj.exceptions import ProjError
from shapely.geometry import Point, shape

from eli.common import JSON
from eli.libeli.eliutils import preferred_projection

ImageStatus = Enum("ImageStatus", "SUCCESS IMAGE_ERROR NETWORK_ERROR OTHER")


class MinZoom:
    """Keep interactive preview state and output paths for one run."""

    def __init__(self, output: str) -> None:
        self.response_cache: dict[str, Any] = {}
        self.domain_lockes: dict[str, asyncio.Lock] = {}
        self.domain_lock = asyncio.Lock()
        self.transformers: dict[tuple[Any, Any], Transformer] = {}
        self.outdir = output
        os.makedirs(output, exist_ok=True)

    def max_count(self, elements: Iterable[str]) -> int:
        counts: dict[str, int] = defaultdict(int)
        for el in elements:
            counts[el] += 1
        return max(counts.items(), key=lambda x: x[1])[1]

    def get_transformer(self, crs_from: CRS, crs_to: CRS) -> Transformer:
        """Cache transformer objects"""
        key = (crs_from, crs_to)
        if key not in self.transformers:
            self.transformers[key] = Transformer.from_crs(crs_from, crs_to, always_xy=True)
        return self.transformers[key]

    def get_http_headers(self, source: JSON) -> dict[str, str]:
        """Extract http headers from source"""
        headers = {}
        if "custom-http-headers" in source["properties"]:
            key = source["properties"]["custom-http-headers"]["header-name"]
            value = source["properties"]["custom-http-headers"]["header-value"]
            headers[key] = value
        return headers

    def tms_url(self, tile: mercantile.Tile, source: JSON) -> str | None:
        tms_url = source["properties"]["url"]
        parameters: dict[str, Any] = {}
        if "{z}" in tms_url:
            return None
        if "{apikey}" in tms_url:
            return None
        if "{switch:" in tms_url:
            match = re.search("switch:?([^}]*)", tms_url)
            if match is None:
                return None
            switches = match.group(1).split(",")
            tms_url = tms_url.replace(match.group(0), "switch")
            parameters["switch"] = switches[0]
        query_url = tms_url
        if "{-y}" in tms_url:
            y = 2**tile.z - 1 - tile.y
            query_url = query_url.replace("{-y}", str(y))
        elif "{!y}" in tms_url:
            y = 2 ** (tile.z - 1) - 1 - tile.y
            query_url = query_url.replace("{!y}", str(y))
        else:
            query_url = query_url.replace("{y}", str(tile.y))
        parameters["x"] = tile.x
        parameters["zoom"] = tile.z
        query_url = query_url.format(**parameters)
        return str(query_url)

    def wms_version_from_url(self, url: str) -> str | None:
        """Extract wms version from url"""
        u = urlparse(url.lower())
        qsl = dict(parse_qsl(u.query))
        if "version" not in qsl:
            return None
        return qsl["version"]

    def _get_bbox(self, proj: str, bounds: list[float], wms_version: str | None) -> str | None:
        """Build wms bbox parameter for GetMap request"""
        if proj in {"EPSG:4326", "CRS:84"}:
            if proj == "EPSG:4326" and wms_version == "1.3.0":
                bbox = ",".join(map(str, [bounds[1], bounds[0], bounds[3], bounds[2]]))
            else:
                bbox = ",".join(map(str, bounds))
        else:
            try:
                crs_from = CRS.from_string("epsg:4326")
                crs_to = CRS.from_string(proj)
                transformer = self.get_transformer(crs_from, crs_to)
                bounds = list(transformer.transform(bounds[0], bounds[1])) + list(
                    transformer.transform(bounds[2], bounds[3])
                )
            except ProjError, ValueError:
                return None
            if crs_to.axis_info[0].direction == "north" and wms_version == "1.3.0":
                bbox = ",".join(map(str, [bounds[1], bounds[0], bounds[3], bounds[2]]))
            else:
                bbox = ",".join(map(str, bounds))
        return bbox

    def wms_url(self, tile: mercantile.Tile, source: JSON) -> str | None:
        bounds = list(mercantile.bounds(tile))
        if "available_projections" not in source["properties"]:
            return None
        available_projections = source["properties"]["available_projections"]
        url = source["properties"]["url"]
        proj = preferred_projection(available_projections)
        if proj is None:
            return None
        wms_version = self.wms_version_from_url(url)
        bbox = self._get_bbox(proj, bounds, wms_version)
        if bbox is None:
            return None
        formatted_url = url.format(proj=proj, width=256, height=256, bbox=bbox)
        return str(formatted_url)

    async def get_image(
        self, session: ClientSession, url: str
    ) -> tuple[ImageStatus, Image.Image | None]:
        status = ImageStatus.OTHER
        img = None
        try:
            async with session.request(method="GET", url=url, ssl=False) as response:
                if response.status == 200:
                    data = await response.read()
                    try:
                        img = Image.open(io.BytesIO(data))
                        status = ImageStatus.SUCCESS
                        return (status, img)
                    except OSError, ValueError, Image.DecompressionBombError:
                        logging.warning("%s: %s", status, url)
                        status = ImageStatus.IMAGE_ERROR
                else:
                    status = ImageStatus.NETWORK_ERROR
        except aiohttp.ClientError, OSError:
            logging.warning("%s: %s", status, url)
            status = ImageStatus.NETWORK_ERROR
        logging.warning("%s: %s", status, url)
        return (status, img)

    # Tile samples, plot callbacks, and source edits share one interactive figure lifecycle.
    # pylint: disable-next=R0912,R0914,R0915
    async def process_source(self, filename: str) -> None:
        import matplotlib.pyplot as plt

        logging.info("Processing %s", filename)
        headers = {"User-Agent": "Mozilla/5.0 (compatible; MSIE 6.0; ELI WMS sync )"}
        timeout = aiohttp.ClientTimeout(total=10)
        conn = aiohttp.TCPConnector(limit_per_host=2)
        async with ClientSession(headers=headers, timeout=timeout, connector=conn) as session:
            out_image = os.path.join(
                self.outdir, os.path.basename(filename).replace(".geojson", ".png")
            )
            if os.path.exists(out_image):
                return
            async with aiofiles.open(filename, encoding="utf-8") as f:
                contents = await f.read()
            source = json.loads(contents)
            if source["properties"]["type"] not in {"tms", "wms"}:
                return
            if "geometry" in source and source["geometry"] is not None:
                geom = shape(source["geometry"])
                centroid = geom.representative_point()
            else:
                centroid = Point(0, 0)

            async def test_zoom(zoom: int) -> tuple[Any, Image.Image | None, int | None]:
                url: str | None = None
                tile = mercantile.tile(centroid.x, centroid.y, zoom)
                if source["properties"]["type"] == "tms":
                    url = self.tms_url(tile, source)
                elif source["properties"]["type"] == "wms":
                    url = self.wms_url(tile, source)
                if url is None:
                    return (None, None, None)
                try:
                    status, img = await self.get_image(session, url)
                    if status == ImageStatus.SUCCESS and img is not None:
                        image_hash = imagehash.average_hash(img)
                        pal_image = Image.new("P", (1, 1))
                        pal_image.putpalette(
                            (0, 0, 0, 0, 255, 0, 255, 0, 0, 255, 255, 0) + (0, 0, 0) * 252
                        )
                        img_comp = img.convert("RGB").quantize(palette=pal_image)
                        colors = img_comp.getcolors(1000)
                        assert colors is not None
                        max_pixel_count = max(color[0] for color in colors)
                        return (image_hash, img, max_pixel_count)
                except (OSError, ValueError, Image.DecompressionBombError) as e:
                    logging.error(e)
                return (None, None, None)

            image_hashes = {}
            max_pixel_counts = {}
            images = {}
            for zoom in range(20):
                image_hash, img, max_pixel_count = await test_zoom(zoom)
                images[zoom] = img
                image_hashes[zoom] = image_hash
                max_pixel_counts[zoom] = max_pixel_count
            if len([zoom for zoom in range(20) if images[zoom] is None]) == len(range(20)):
                return

            def compare_neighbors(zoom: int) -> bool:
                same_as_a_neighbor = False
                this_hash = image_hashes[zoom]
                if zoom - 1 >= 0:
                    left_hash = image_hashes[zoom - 1]
                    if left_hash == this_hash:
                        same_as_a_neighbor = True
                if zoom + 1 < 20:
                    right_hash = image_hashes[zoom + 1]
                    if right_hash == this_hash:
                        same_as_a_neighbor = True
                return same_as_a_neighbor

            def zoom_in_is_empty(zoom: int) -> bool:
                if zoom + 1 < 20:
                    if (
                        image_hashes[zoom + 1] is None
                        or self.max_count(str(image_hashes[zoom + 1]).upper().replace("F", "O"))
                        == 16
                    ):
                        return True
                return False

            min_zoom = None
            for zoom in range(20):
                if image_hashes[zoom] is None:
                    continue
                if zoom_in_is_empty(zoom):
                    continue
                if self.max_count(str(image_hashes[zoom]).upper().replace("F", "O")) == 16:
                    continue
                if not compare_neighbors(zoom):
                    min_zoom = zoom
                    break
            fig, axs = plt.subplots(2, 10, figsize=(15, 5))
            for z in range(20):
                if z < 10:
                    ax = axs[0][z]
                else:
                    ax = axs[1][z - 10]
                ax.set_xlim(0, 256)
                ax.set_ylim(0, 256)
                if images[z] is not None:
                    ax.imshow(images[z])
                else:
                    ax.text(
                        0.5,
                        0.5,
                        "No data",
                        horizontalalignment="center",
                        verticalalignment="center",
                        transform=ax.transAxes,
                    )
                ax.set_aspect("equal")
                ax.get_xaxis().set_ticks([])
                ax.get_yaxis().set_ticks([])
                if image_hashes[z] is None:
                    ax.set_xlabel("")
                else:
                    count = max_pixel_counts[z]
                    assert count is not None
                    ax.set_xlabel(str(image_hashes[z]) + "\n" + str(count - 256 * 256))
                ax.set_ylabel(z)
                title = f"Zoom: {z}"
                if z == min_zoom:
                    title += " <== "
                if (
                    "min_zoom" not in source["properties"]
                    and z == 0
                    or (
                        "min_zoom" in source["properties"] and source["properties"]["min_zoom"] == z
                    )
                ):
                    title += " ELI "
                ax.set_title(title)
                if (
                    "attribution" in source["properties"]
                    and "text" in source["properties"]["attribution"]
                ):
                    plt.figtext(0.01, 0.01, source["properties"]["attribution"]["text"])

            def update_source(selected_min_zoom: int | None, source: JSON, filename: str) -> None:
                if selected_min_zoom is not None:
                    original_min_zoom = 0
                    if "min_zoom" in source["properties"]:
                        original_min_zoom = source["properties"]["min_zoom"]
                    if (
                        selected_min_zoom is None or selected_min_zoom == 0
                    ) and "min_zoom" not in source["properties"]:
                        return
                    if not selected_min_zoom == original_min_zoom:
                        logging.info(
                            "Update %s: %s, previously: %s",
                            source["properties"]["name"],
                            selected_min_zoom,
                            original_min_zoom,
                        )
                        if selected_min_zoom is None or selected_min_zoom == 0:
                            source["properties"].pop("min_zoom", None)
                        else:
                            source["properties"]["min_zoom"] = selected_min_zoom
                        with open(filename, "w", encoding="utf-8") as out:
                            json.dump(source, out, indent=4, sort_keys=False, ensure_ascii=False)
                            out.write("\n")

            def on_click(event: Any) -> None:
                if event.inaxes is None:
                    return
                try:
                    selected_min_zoom = int(event.inaxes.yaxis.get_label().get_text())
                    update_source(selected_min_zoom, source, filename)
                    if selected_min_zoom < 10:
                        ax = axs[0][selected_min_zoom]
                    else:
                        ax = axs[1][selected_min_zoom - 10]
                    for sp in ax.spines.values():
                        sp.set_color("red")
                    plt.savefig(out_image)
                    plt.close()
                except (OSError, ValueError) as e:
                    print(str(e))

            def on_key(event: Any) -> None:
                if event.canvas is not fig.canvas:
                    return
                selected_min_zoom = min_zoom
                if selected_min_zoom is None:
                    return
                update_source(selected_min_zoom, source, filename)
                if selected_min_zoom < 10:
                    ax = axs[0][selected_min_zoom]
                else:
                    ax = axs[1][selected_min_zoom - 10]
                for sp in ax.spines.values():
                    sp.set_color("red")
                plt.savefig(out_image)
                plt.close()

            fig.suptitle(filename)
            plt.tight_layout()
            fig.canvas.mpl_connect("button_press_event", on_click)
            fig.canvas.mpl_connect("key_press_event", on_key)
            plt.show()
            try:
                plt.close()
            except (RuntimeError, ValueError) as e:
                logging.warning(str(e))
            return

    def start_processing(self, sources_directory: str) -> None:
        if os.path.isfile(sources_directory):
            asyncio.run(self.process_source(sources_directory))
        elif os.path.isdir(sources_directory):
            for filename in glob.glob(
                os.path.join(sources_directory, "**", "*.geojson"), recursive=True
            ):
                asyncio.run(self.process_source(filename))
