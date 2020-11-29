import argparse
import asyncio
import glob
import io
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from collections import OrderedDict, namedtuple
from io import StringIO
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import aiohttp
import imagehash
import mercantile
import pyproj
from PIL import Image
from shapely.geometry import shape
from pyproj import Transformer
from pyproj.crs import CRS
import aiofiles
from aiohttp import ClientSession

logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser(description='Update WMS URLs and related properties')
parser.add_argument('sources',
                    metavar='sources',
                    type=str,
                    nargs='?',
                    help='path to sources directory',
                    default="sources")

args = parser.parse_args()
sources_directory = args.sources

response_cache = {}
domain_locks = {}
domain_lock = asyncio.Lock()

RequestResult = namedtuple('RequestResultCache',
                           ['status', 'text', 'exception'],
                           defaults=[None, None, None])

ZOOM_LEVEL = 14


# Before adding a new WMS version, it should be checked if every consumer supports it!
supported_wms_versions = ['1.3.0', '1.1.1', '1.1.0', '1.0.0']

# List of not deprecated EPSG codes
valid_epsgs = set()
for pj_type in pyproj.enums.PJType:
    valid_epsgs.update(
        map(
            lambda x: "EPSG:{}".format(x),
            pyproj.get_codes("EPSG", pj_type, allow_deprecated=False),
        )
    )

epsg_3857_alias = set(['EPSG:{}'.format(epsg) for epsg in [900913, 3587, 54004, 41001, 102113, 102100, 3785]])


def compare_projs(old_projs, new_projs):
    """ Compare two collections of projections. Returns True if both collections contain the same elements.

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
    """ Compare URLs. Returns True if the urls contain the same parameters.

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


async def get_url(url: str, session: ClientSession, with_text=False, with_data=False, headers=None):
    """ Fetch url.

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
        return RequestResult(exception="Could not parse URL: {}".format(url))

    async with domain_lock:
        if o.netloc not in domain_locks:
            domain_locks[o.netloc] = asyncio.Lock()
        lock = domain_locks[o.netloc]

    async with lock:
        if url not in response_cache:
            for i in range(3):
                try:
                    logging.debug("GET {}".format(url))
                    async with session.request(method="GET", url=url, ssl=False, headers=headers) as response:
                        status = response.status
                        if with_text:
                            try:
                                text = await response.text()
                            except:
                                text = await response.read()
                            response_cache[url] = RequestResult(status=status, text=text)
                        elif with_data:
                            data = await response.read()
                            response_cache[url] = RequestResult(status=status, text=data)
                        else:
                            response_cache[url] = RequestResult(status=status)
                except asyncio.TimeoutError:
                    response_cache[url] = RequestResult(exception="Timeout for: {}".format(url))
                except Exception as e:
                    logging.debug("Error for: {} ({})".format(url, str(e)))
                    response_cache[url] = RequestResult(exception="Exception {} for: {}".format(str(e), url))
                if RequestResult.exception is None:
                    break
        else:
            logging.debug("Cached {}".format(url))

        return response_cache[url]


async def get_image(url, available_projections, lon, lat, zoom, session, messages):
    """ Download image (tms tile for coordinate lon,lat on level zoom and calculate image hash

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

    proj = None
    if 'EPSG:4326' in available_projections:
        proj = 'EPSG:4326'
    elif 'EPSG:3857' in available_projections:
        proj = 'EPSG:3857'
    else:
        for proj in available_projections:
            try:
                CRS.from_string(proj)
            except:
                continue
            break
    if proj is None:
        messages.append("No projection left: {}".format(available_projections))
        return None

    crs_from = CRS.from_string("epsg:4326")
    crs_to = CRS.from_string(proj)
    if not proj == 'EPSG:4326':
        transformer = Transformer.from_crs(crs_from, crs_to, always_xy=True)
        bounds = list(transformer.transform(bounds[0], bounds[1])) + \
                 list(transformer.transform(bounds[2], bounds[3]))

    # WMS < 1.3.0 assumes x,y coordinate ordering.
    # WMS 1.3.0 expects coordinate ordering defined in CRS.
    if crs_to.axis_info[0].direction == 'north' and '=1.3.0' in url:
        bbox = ",".join(map(str, [bounds[1],
                                  bounds[0],
                                  bounds[3],
                                  bounds[2]]))
    else:
        bbox = ",".join(map(str, bounds))

    formatted_url = url.format(proj=proj,
                               width=512,
                               height=512,
                               bbox=bbox)
    messages.append("Image URL: {}".format(formatted_url))
    for i in range(3):
        try:
            # Downloag image
            async with session.request(method="GET", url=formatted_url, ssl=False) as response:
                data = await response.read()
                img = Image.open(io.BytesIO(data))
                img_hash = imagehash.average_hash(img)
                messages.append("ImageHash: {}".format(img_hash))
                return img_hash
        except Exception as e:
            messages.append("Could not download image in try {}: {}".format(i, str(e)))
        await asyncio.sleep(5)

    return None


def parse_wms(xml):
    """ Rudimentary parsing of WMS Layers from GetCapabilites Request
        owslib.wms seems to have problems parsing some weird not relevant metadata.
        This function aims at only parsing relevant layer metadata
    """
    wms = {}
    # Remove prefixes to make parsing easier
    # From https://stackoverflow.com/questions/13412496/python-elementtree-module-how-to-ignore-the-namespace-of-xml-files-to-locate-ma
    try:
        it = ET.iterparse(StringIO(xml))
        for _, el in it:
            _, _, el.tag = el.tag.rpartition('}')
        root = it.root
    except:
        raise RuntimeError("Could not parse XML.")

    root_tag = root.tag.rpartition("}")[-1]
    if root_tag in {'ServiceExceptionReport', 'ServiceException'}:
        raise RuntimeError("WMS service exception")

    if root_tag not in {'WMT_MS_Capabilities', 'WMS_Capabilities'}:
        raise RuntimeError("No Capabilities Element present: Root tag: {}".format(root_tag))

    if 'version' not in root.attrib:
        raise RuntimeError("WMS version cannot be identified.")
    version = root.attrib['version']
    wms['version'] = version

    layers = {}

    def parse_layer(element, crs=set(), styles={}, bbox=None):
        new_layer = {'CRS': crs,
                     'Styles': {},
                     'BBOX': bbox}
        new_layer['Styles'].update(styles)
        for tag in ['Name', 'Title', 'Abstract']:
            e = element.find("./{}".format(tag))
            if e is not None:
                new_layer[e.tag] = e.text
        for tag in ['CRS', 'SRS']:
            es = element.findall("./{}".format(tag))
            for e in es:
                new_layer["CRS"].add(e.text.upper())
        for tag in ['Style']:
            es = element.findall("./{}".format(tag))
            for e in es:
                new_style = {}
                for styletag in ['Title', 'Name']:
                    el = e.find("./{}".format(styletag))
                    if el is not None:
                        new_style[styletag] = el.text
                new_layer["Styles"][new_style['Name']] = new_style
        # WMS Version 1.3.0
        e = element.find("./EX_GeographicBoundingBox")
        if e is not None:
            bbox = [float(e.find("./{}".format(orient)).text.replace(',', '.'))
                    for orient in ['westBoundLongitude',
                                   'southBoundLatitude',
                                   'eastBoundLongitude',
                                   'northBoundLatitude']]
            new_layer['BBOX'] = bbox
        # WMS Version < 1.3.0
        e = element.find("./LatLonBoundingBox")
        if e is not None:
            bbox = [float(e.attrib[orient].replace(',', '.')) for orient in ['minx', 'miny', 'maxx', 'maxy']]
            new_layer['BBOX'] = bbox

        if 'Name' in new_layer:
            layers[new_layer['Name']] = new_layer

        for sl in element.findall("./Layer"):
            parse_layer(sl,
                        new_layer['CRS'].copy(),
                        new_layer['Styles'],
                        new_layer['BBOX'])

    # Find child layers. CRS and Styles are inherited from parent
    top_layers = root.findall(".//Capability/Layer")
    for top_layer in top_layers:
        parse_layer(top_layer)

    wms['layers'] = layers

    # Parse formats
    formats = []
    for es in root.findall(".//Capability/Request/GetMap/Format"):
        formats.append(es.text)
    wms['formats'] = formats

    # Parse access constraints and fees
    constraints = []
    for es in root.findall(".//AccessConstraints"):
        constraints.append(es.text)
    fees = []
    for es in root.findall(".//Fees"):
        fees.append(es.text)
    wms['Fees'] = fees
    wms['AccessConstraints'] = constraints

    return wms


async def update_wms(wms_url, session: ClientSession, messages):
    """ Update wms parameters using WMS GetCapabilities request

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

    layers = wms_args['layers'].split(',')
    if len(layers) > 1:
        # Currently only one layer is supported"
        messages.append("Currently only 1 layer is supported")
        return None

    def get_getcapabilitie_url(wms_version=None):
        get_capabilities_args = {'service': 'WMS',
                                 'request': 'GetCapabilities'}
        if wms_version is not None:
            get_capabilities_args['version'] = wms_version

        # Drop all wms getmap parameters, keep all extra arguments (e.g. such as map or key)
        for key in wms_args:
            if key not in {'version', 'request', 'layers', 'bbox', 'width', 'height', 'format', 'crs', 'srs',
                           'styles', 'transparent'}:
                get_capabilities_args[key] = wms_args[key]
        url_parts[4] = urlencode(list(get_capabilities_args.items()))
        return urlunparse(url_parts)

    # Fetch highest supported WMS GetCapabilities
    wms = None
    for wmsversion in supported_wms_versions:
        # Do not try versions older than in the url
        if wmsversion < wms_args['version']:
            continue

        try:
            wms_getcapabilites_url = get_getcapabilitie_url(wmsversion)
            resp = await get_url(wms_getcapabilites_url, session, with_text=True)
            if resp.exception is not None:
                messages.append("Could not download GetCapabilites URL for {}: {}".format(wmsversion, resp.exception))
                continue
            xml = resp.text
            if isinstance(xml, bytes):
                # Parse xml encoding to decode
                try:
                    xml_ignored = xml.decode(errors='ignore')
                    str_encoding = re.search("encoding=\"(.*?)\"", xml_ignored).group(1)
                    xml = xml.decode(encoding=str_encoding)
                except Exception as e:
                    raise RuntimeError("Could not parse encoding: {}".format(str(e)))

            wms = parse_wms(xml)
            if wms is not None:
                break
        except Exception as e:
            messages.append("Could not get GetCapabilites URL for {} in try: {}".format(wmsversion, str(e)))

    if wms is None:
        # Could not request GetCapabilities
        messages.append("Could not contact WMS server")
        return None

    if layers[0] not in wms['layers']:
        # Layer not advertised by server
        messages.append("Layer {} not advertised by server".format(layers[0]))
        return None

    wms_args['version'] = wms['version']
    if wms_args['version'] == '1.3.0':
        wms_args.pop('srs', None)
        wms_args['crs'] = '{proj}'
    if 'styles' not in wms_args:
        wms_args['styles'] = ''

    def test_proj(proj):
        if proj == 'CRS:84':
            return True
        if 'AUTO' in proj:
            return False
        if 'EPSG' in proj:
            try:
                CRS.from_string(proj)
                return True
            except:
                return False
        return False

    new_projections = wms['layers'][layers[0]]['CRS']
    new_projections = set([proj.upper() for proj in new_projections if test_proj(proj)])

    new_wms_parameters = OrderedDict()
    for key in ['map', 'layers', 'styles', 'format', 'transparent', 'crs', 'srs', 'width', 'height', 'bbox', 'version',
                'service', 'request']:
        if key in wms_args:
            new_wms_parameters[key] = wms_args[key]
    for key in wms_args:
        if key not in new_wms_parameters:
            new_wms_parameters[key] = wms_args[key]

    baseurl = wms_url.split("?")[0]
    new_url = baseurl + "?" + "&".join(
        ["{}={}".format(key.upper(), value) for key, value in new_wms_parameters.items()])
    return {'url': new_url, 'available_projections': new_projections}


async def process_source(filename, session: ClientSession):
    async with aiofiles.open(filename, mode='r', encoding='utf-8') as f:
        contents = await f.read()
        source = json.loads(contents)

    # Exclude sources
    # Skip non wms layers
    if not source['properties']['type'] == 'wms':
        return
    # check if it is esri rest and not wms
    if 'bboxSR' in source['properties']['url']:
        return
    if 'available_projections' not in source['properties']:
        return
    if 'header' in source['properties']['url']:
        return
    if 'geometry' not in source:
        return
    if source['geometry'] is None:
        return

    # Get existing image hash
    geom = shape(source['geometry'])
    pt = geom.representative_point()
    original_img_messages = []
    image_hash = await get_image(url=source['properties']['url'],
                                 available_projections=source['properties']['available_projections'],
                                 lon=pt.x,
                                 lat=pt.y,
                                 zoom=ZOOM_LEVEL,
                                 session=session,
                                 messages=original_img_messages)
    if image_hash is None:
        # We are finished if it was not possible to get the image
        return

    if str(image_hash) in {'0000000000000000', 'FFFFFFFFFFFFFFFF'}:
        # These image hashes indicate that the downloaded image is not useful to determine
        # if the updated query returns the same image
        logging.info(
            "ImageHash {} not useful for: {} || {}".format(str(image_hash), filename, " || ".join(original_img_messages)))
        return

    # Update wms
    wms_messages = []
    result = await update_wms(source['properties']['url'], session, wms_messages)
    if result is None:
        logging.info("Not possible to update wms url for {}: {}".format(filename, " || ".join(wms_messages)))
        return

    # Test if selected projections work despite not being advertised
    for EPSG in {'EPSG:3857', 'EPSG:4326'}:
        if EPSG not in result['available_projections']:
            epsg_image_hash = await get_image(url=result['url'],
                                              available_projections=[EPSG],
                                              lon=pt.x,
                                              lat=pt.y,
                                              zoom=ZOOM_LEVEL,
                                              session=session,
                                              messages=[])
            if epsg_image_hash == image_hash:
                result['available_projections'].add(EPSG)

    # Download image for updated url
    new_img_messages = []
    new_image_hash = await get_image(url=result['url'],
                                     available_projections=result['available_projections'],
                                     lon=pt.x,
                                     lat=pt.y,
                                     zoom=ZOOM_LEVEL,
                                     session=session,
                                     messages=new_img_messages)

    if new_image_hash is None:
        logging.warning("Could not download new image: {}".format(" || ".join(new_img_messages)))
        return

    # Only sources are updated where the new query returns the same image
    if not image_hash == new_image_hash:
        logging.info(
            "Image hash not the same for: {}: {} {} | {} | {}".format(filename,
                                                                      image_hash,
                                                                      new_image_hash,
                                                                      "||".join(original_img_messages),
                                                                      "||".join(new_img_messages)))

    # Servers that report a lot of projection may be configured wrongly
    # Check for CRS:84, EPSG:3857, EPSG:4326 and keep existing projections if still advertised
    if len(result['available_projections']) > 15:
        filtered_projs = set()
        for proj in ['CRS:84', 'EPSG:3857', 'EPSG:4326']:
            if proj in result['available_projections']:
                filtered_projs.add(proj)
        for proj in source['properties']['available_projections']:
            if proj in result['available_projections']:
                filtered_projs.add(proj)
        result['available_projections'] = filtered_projs

    # Filter alias projections
    if 'EPSG:3857' in result['available_projections']:
        for epsg in epsg_3857_alias:
            if epsg in result['available_projections']:
                result['available_projections'].remove(epsg)

    # Filter deprecated projections
    result["available_projections"] = [
        epsg for epsg in result["available_projections"]
        if epsg == "CRS:84" or (epsg in valid_epsgs and epsg not in epsg_3857_alias)
    ]

    # Check if only formatting has changes
    url_has_changed = not compare_urls(source['properties']['url'], result['url'])
    projections_have_changed = not compare_projs(source['properties']['available_projections'],
                                                 result['available_projections'])

    if url_has_changed:
        source['properties']['url'] = result['url']
    if projections_have_changed:
        source['properties']['available_projections'] = list(
            sorted(result['available_projections'], key=lambda x: (x.split(':')[0], int(x.split(':')[1]))))

    if url_has_changed or projections_have_changed:
        with open(filename, 'w', encoding='utf-8') as out:
            json.dump(source, out, indent=4, sort_keys=False, ensure_ascii=False)
            out.write("\n")


async def start_processing(sources_directory):
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; MSIE 6.0; ELI WMS sync )'}
    timeout = aiohttp.ClientTimeout(total=180)

    async with ClientSession(headers=headers, timeout=timeout) as session:
        jobs = []
        for filename in glob.glob(os.path.join(sources_directory, '**', '*.geojson'), recursive=True):
            jobs.append(process_source(filename, session))
        await asyncio.gather(*jobs)


asyncio.run(start_processing(sources_directory))
