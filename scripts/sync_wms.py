import argparse
import asyncio
import glob
import io
import json
import os
import re
import xml.etree.ElementTree as ET
from collections import OrderedDict, namedtuple
from io import StringIO
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import aiohttp
import imagehash
import mercantile
from PIL import Image
from shapely.geometry import shape
from pyproj import Transformer
from pyproj.crs import CRS
import aiofiles
from aiohttp import ClientSession

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


async def get_url(url: str, session: ClientSession, with_text=False, headers=None):
    """ Ensure that only one request is sent to a domain at one point in time and that the same url is not
    queried more than once.
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
            try:
                print("GET {}".format(url), headers)
                async with session.request(method="GET", url=url, ssl=False, headers=headers) as response:
                    status = response.status
                    if with_text:
                        try:
                            text = await response.text()
                        except:
                            text = await response.read()
                        response_cache[url] = RequestResult(status=status, text=text)
                    else:
                        response_cache[url] = RequestResult(status=status)
            except asyncio.TimeoutError:
                response_cache[url] = RequestResult(exception="Timeout for: {}".format(url))
            except Exception as e:
                print("Error for: {} ({})".format(url, str(e)))
                response_cache[url] = RequestResult(exception="Exception {} for: {}".format(str(e), url))
        else:
            print("Cached {}".format(url))

        return response_cache[url]


async def get_image(url, available_projections, lon, lat, zoom, session):
    """ Download image (tms tile for coordinate lon,lat on level zoom and calculate image hash"""
    tile = list(mercantile.tiles(lon, lat, lon, lat, zooms=zoom))[0]
    bounds = list(mercantile.bounds(tile))

    proj = None
    if 'EPSG:4326' in available_projections:
        proj = 'EPSG:4326'
    elif 'EPSG:3857' in available_projections:
        proj = 'EPSG:3857'
    else:
        for proj in available_projections:
            if 'EPSG' in proj.upper():
                break
    if proj is None:
        return None

    if not proj == 'EPSG:4326':
        crs_from = CRS.from_string("epsg:4326")
        crs_to = CRS.from_string(proj)
        transformer = Transformer.from_crs(crs_from, crs_to, always_xy=True)
        bounds = list(transformer.transform(bounds[0], bounds[1])) + list(transformer.transform(bounds[2], bounds[3]))

    if proj == 'EPSG:4326' and '1.3.0' in url:
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

    try:
        # Downloag image
        async with session.request(method="GET", url=formatted_url, ssl=False) as response:
            data = await response.read()
            img = Image.open(io.BytesIO(data))
            hash = imagehash.average_hash(img)
            return hash
    except Exception as e:
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


async def update_wms(wms_url, session: ClientSession):
    """ Update wms parameters using WMS GetCapabilities request"""
    wms_args = {}
    u = urlparse(wms_url)
    url_parts = list(u)
    for k, v in parse_qsl(u.query, keep_blank_values=True):
        wms_args[k.lower()] = v

    layers = wms_args['layers'].split(',')
    if len(layers) > 1:
        # Currently only one layer is supported"
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

    # We first send a service=WMS&request=GetCapabilities request to server
    # According to the WMS Specification Section 6.2 Version numbering and negotiation, the server should return
    # the GetCapabilities XML with the highest version the server supports.
    # If this fails, it is tried to explicitly specify a WMS version
    exceptions = []
    wms = None
    for wmsversion in ['1.3.0', '1.1.1', '1.1.0', '1.0.0', None]:
        try:
            wms_getcapabilites_url = get_getcapabilitie_url(wmsversion)
            resp = await get_url(wms_getcapabilites_url, session, with_text=True)
            if resp.exception is not None:
                exceptions.append("WMS {}: {}".format(wmsversion, resp.exception))
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
            pass

    if wms is None:
        # Could not request GetCapabilities
        return None

    if layers[0] not in wms['layers']:
        # Layer not advertised by server
        return None

    wms_args['version'] = wms['version']
    if wms_args['version'] == '1.3.0':
        wms_args.pop('srs', None)
        wms_args['crs'] = '{proj}'
    if 'styles' not in wms_args:
        wms_args['styles'] = ''

    new_projections = wms['layers'][layers[0]]['CRS']
    new_projections = [proj for proj in new_projections if 'AUTO' not in proj]
    new_projections = sorted(new_projections, key=lambda x: (x.split(':')[0], int(x.split(':')[1])))

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
    return {'url': new_url, 'available_projections': list(new_projections)}


async def process_source(filename, session: ClientSession):
    async with aiofiles.open(filename, mode='r', encoding='utf-8') as f:
        contents = await f.read()
        source = json.loads(contents)

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

    # Get existing image hash
    geom = shape(source['geometry'])
    pt = geom.centroid
    image_hash = await get_image(url=source['properties']['url'],
                                 available_projections=source['properties']['available_projections'],
                                 lon=pt.x,
                                 lat=pt.y,
                                 zoom=15,
                                 session=session)
    if image_hash is None:
        # We are finished if it was not possible to get the image
        return

    if str(image_hash) in {'0000000000000000', 'FFFFFFFFFFFFFFFF'}:
        # These image hashes indicate that the downloaded image is not useful to determine
        # if the updated query returns the same image
        return

    # Update wms
    result = await update_wms(source['properties']['url'], session)
    if result is None:
        return

    new_image_hash = await get_image(url=result['url'],
                                     available_projections=result['available_projections'],
                                     lon=pt.x,
                                     lat=pt.y,
                                     zoom=15,
                                     session=session)

    # Only sources are updated where the new query returns the same image
    if image_hash == new_image_hash:
        # Skip servers with a lot of available projections. These servers are probably not ideally configured.
        if len(result['available_projections']) < 10:
            source['properties']['url'] = result['url']
            source['properties']['available_projections'] = result['available_projections']

            with open(filename, 'w', encoding='utf-8') as out:
                json.dump(source, out, indent=4, sort_keys=False, ensure_ascii=False)
                out.write("\n")


async def start_processing(sources_directory):
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; MSIE 6.0; ELI WMS sync )'}
    timeout = aiohttp.ClientTimeout(total=90)

    async with ClientSession(headers=headers, timeout=timeout) as session:
        jobs = []
        for filename in glob.glob(os.path.join(sources_directory, '**', '*.geojson'), recursive=True):
            jobs.append(process_source(filename, session))
        await asyncio.gather(*jobs)


asyncio.run(start_processing(sources_directory))
