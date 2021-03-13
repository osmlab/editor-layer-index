import argparse
import asyncio
import glob
import json
import logging
import os
import re
import io
from collections import namedtuple
from urllib.parse import urlparse
import aiohttp
import imagehash
import mercantile
from shapely.geometry import shape, Point
import aiofiles
from aiohttp import ClientSession
from PIL import Image
from io import BytesIO
from collections import defaultdict
import matplotlib.pyplot as plt
from pyproj import Transformer
from pyproj.crs import CRS
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from enum import Enum


logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser(description="Test min zoom")
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
domain_lockes = {}
domain_lock = asyncio.Lock()


def max_count(elements):
    counts = defaultdict(int)
    for el in elements:
        counts[el] += 1
    return max(counts.items(), key=lambda x: x[1])[1]


outdir = "min_zoom_results"
if not os.path.exists(outdir):
    os.mkdir(outdir)

logging.info("Tmp outdirectory: {}".format(outdir))

ImageStatus = Enum("ImageStatus", "SUCCESS IMAGE_ERROR NETWORK_ERROR OTHER")

transformers = {}


def get_transformer(crs_from, crs_to):
    """ Cache transformer objects"""
    key = (crs_from, crs_to)
    if key not in transformers:
        transformers[key] = Transformer.from_crs(crs_from, crs_to, always_xy=True)
    return transformers[key]


def get_http_headers(source):
    """ Extract http headers from source"""
    headers = {}
    if "custom-http-headers" in source["properties"]:
        key = source["properties"]["custom-http-headers"]["header-name"]
        value = source["properties"]["custom-http-headers"]["header-value"]
        headers[key] = value
    return headers


async def get_tms_image(tile, source, session):
    tms_url = source["properties"]["url"]
    parameters = {}
    # {z} instead of {zoom}
    if "{z}" in tms_url:
        return
    if "{apikey}" in tms_url:
        return

    if "{switch:" in tms_url:
        match = re.search(r"switch:?([^}]*)", tms_url)
        switches = match.group(1).split(",")
        tms_url = tms_url.replace(match.group(0), "switch")
        parameters["switch"] = switches[0]

    extra_headers = get_http_headers(source)
    query_url = tms_url
    if "{-y}" in tms_url:
        y = 2 ** tile.z - 1 - tile.y
        query_url = query_url.replace("{-y}", str(y))
    elif "{!y}" in tms_url:
        y = 2 ** (tile.z - 1) - 1 - tile.y
        query_url = query_url.replace("{!y}", str(y))
    else:
        query_url = query_url.replace("{y}", str(tile.y))
    parameters["x"] = tile.x
    parameters["zoom"] = tile.z
    query_url = query_url.format(**parameters)

    return query_url


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


async def get_wms_image(tile, source, session):
    bounds = list(mercantile.bounds(tile))
    if "available_projections" not in source["properties"]:
        return None
    available_projections = source["properties"]["available_projections"]
    url = source["properties"]["url"]

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
        return None

    wms_version = wms_version_from_url(url)
    bbox = _get_bbox(proj, bounds, wms_version)
    if bbox is None:
        return None

    formatted_url = url.format(proj=proj, width=256, height=256, bbox=bbox)

    return formatted_url


async def get_image(session, url):
    status = ImageStatus.OTHER
    img = None
    try:
        async with session.request(method="GET", url=url, ssl=False) as response:
            if response.status == 200:
                data = await response.read()
                try:
                    img = Image.open(io.BytesIO(data))
                    status = ImageStatus.SUCCESS
                    return status, img
                except Exception:
                    logging.warning(f"{status}: {url}")
                    status = ImageStatus.IMAGE_ERROR
            else:
                status = ImageStatus.NETWORK_ERROR
    except Exception:
        logging.warning(f"{status}: {url}")
        status = ImageStatus.NETWORK_ERROR
    logging.warning(f"{status}: {url}")
    return status, img


async def process_source(filename):

    logging.info(f"Processing {filename}")
    headers = {"User-Agent": "Mozilla/5.0 (compatible; MSIE 6.0; ELI WMS sync )"}
    timeout = aiohttp.ClientTimeout(total=10)
    conn = aiohttp.TCPConnector(limit_per_host=2)
    async with ClientSession(
        headers=headers, timeout=timeout, connector=conn
    ) as session:

        out_image = os.path.join(
            outdir, os.path.basename(filename).replace(".geojson", ".png")
        )

        if os.path.exists(out_image):
            return

        async with aiofiles.open(filename, mode="r", encoding="utf-8") as f:
            contents = await f.read()
        source = json.loads(contents)

        # Skip non tms layers
        if not source["properties"]["type"] in {"tms", "wms"}:
            return

        if "geometry" in source and source["geometry"] is not None:
            geom = shape(source["geometry"])
            centroid = geom.representative_point()
        else:
            centroid = Point(0, 0)

        async def test_zoom(zoom):
            tile = mercantile.tile(centroid.x, centroid.y, zoom)

            if source["properties"]["type"] == "tms":
                url = await get_tms_image(tile, source, session)
            elif source["properties"]["type"] == "wms":
                url = await get_wms_image(tile, source, session)
            if url is None:
                return None, None, None

            try:
                status, img = await get_image(session, url)
                if status == ImageStatus.SUCCESS:
                    image_hash = imagehash.average_hash(img)
                    pal_image = Image.new("P", (1, 1))
                    pal_image.putpalette(
                        (0, 0, 0, 0, 255, 0, 255, 0, 0, 255, 255, 0) + (0, 0, 0) * 252
                    )
                    img_comp = img.convert("RGB").quantize(palette=pal_image)
                    colors = img_comp.getcolors(1000)
                    max_pixel_count = max([count for count, color in colors])
                    return image_hash, img, max_pixel_count
            except Exception as e:
                logging.error(e)
            return None, None, None

        image_hashes = {}
        max_pixel_counts = {}
        images = {}
        for zoom in range(20):
            image_hash, img, max_pixel_count = await test_zoom(zoom)
            images[zoom] = img
            image_hashes[zoom] = image_hash
            max_pixel_counts[zoom] = max_pixel_count

        # Getting images was not sucessful, nothing to do
        if len([zoom for zoom in range(20) if images[zoom] is None]) == len(range(20)):
            return

        def compare_neighbors(zoom):
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

        def zoom_in_is_empty(zoom):
            if zoom + 1 < 20:
                if (
                    image_hashes[zoom + 1] is None
                    or max_count(str(image_hashes[zoom + 1]).upper().replace("F", "O"))
                    == 16
                ):
                    return True
            return False

        # Find minzoom
        min_zoom = None
        for zoom in range(20):
            if image_hashes[zoom] is None:
                continue
            if zoom_in_is_empty(zoom):
                continue
            if max_count(str(image_hashes[zoom]).upper().replace("F", "O")) == 16:
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
            # ax.tick_params(axis='both', which='both', length=0.0, width=0.0)
            ax.get_xaxis().set_ticks([])
            ax.get_yaxis().set_ticks([])
            if image_hashes[z] is None:
                ax.set_xlabel("")
            else:
                ax.set_xlabel(
                    str(image_hashes[z]) + "\n" + str(max_pixel_counts[z] - 256 * 256)
                )
            ax.set_ylabel(z)
            title = "Zoom: {}".format(z)

            if z == min_zoom:
                title += " <== "

            if ("min_zoom" not in source["properties"] and z == 0) or (
                "min_zoom" in source["properties"]
                and source["properties"]["min_zoom"] == z
            ):
                title += " ELI "

            ax.set_title(title)
            if (
                "attribution" in source["properties"]
                and "text" in source["properties"]["attribution"]
            ):
                plt.figtext(0.01, 0.01, source["properties"]["attribution"]["text"])

        def update_source(selected_min_zoom, source, filename):
            # Check against source if we found at least one image
            if selected_min_zoom is not None:

                original_min_zoom = 0
                if "min_zoom" in source["properties"]:
                    original_min_zoom = source["properties"]["min_zoom"]

                # Do nothing if existing value is same as tested value
                if (
                    selected_min_zoom is None or selected_min_zoom == 0
                ) and "min_zoom" not in source["properties"]:
                    return
                if not selected_min_zoom == original_min_zoom:
                    logging.info(
                        "Update {}: {}, previously: {}".format(
                            source["properties"]["name"],
                            selected_min_zoom,
                            original_min_zoom,
                        )
                    )
                    if selected_min_zoom is None or selected_min_zoom == 0:
                        source["properties"].pop("min_zoom", None)
                    else:
                        source["properties"]["min_zoom"] = selected_min_zoom

                    with open(filename, "w", encoding="utf-8") as out:
                        json.dump(
                            source, out, indent=4, sort_keys=False, ensure_ascii=False
                        )
                        out.write("\n")

        def on_click(event):
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
            except Exception as e:
                print(str(e))

        def on_key(event):
            selected_min_zoom = min_zoom
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
        except Exception as e:
            logging.warning(str(e))
        return


def start_processing(sources_directory):

    if os.path.isfile(sources_directory):
        asyncio.run(process_source(sources_directory))
    elif os.path.isdir(sources_directory):
        for filename in glob.glob(
            os.path.join(sources_directory, "**", "*.geojson"), recursive=True
        ):
            asyncio.run(process_source(filename))


start_processing(sources_directory)
