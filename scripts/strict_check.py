#!/usr/bin/env python

"""
usage: strict_check.py [-h] path [path ...]

Checks new ELI sources for validity and common errors

"""

import json
import io
import re
import warnings
from io import StringIO
from argparse import ArgumentParser
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import xml.etree.ElementTree as ET
import mercantile
import validators
from jsonschema import ValidationError, RefResolver, Draft4Validator
import colorlog
import requests
import os
from owslib.wmts import WebMapTileService
from shapely.geometry import shape, Point, box


def dict_raise_on_duplicates(ordered_pairs):
    """Reject duplicate keys."""
    d = {}
    for k, v in ordered_pairs:
        if k in d:
            raise ValidationError("duplicate key: %r" % (k,))
        else:
            d[k] = v
    return d


parser = ArgumentParser(description='Strict checks for ELI sources newly added')
parser.add_argument('path', nargs='+', help='Path of files to check.')

arguments = parser.parse_args()
logger = colorlog.getLogger()
logger.setLevel('INFO')
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter())
logger.addHandler(handler)

schema = json.load(io.open('schema.json', encoding='utf-8'))

resolver = RefResolver('', None)
validator = Draft4Validator(schema, resolver=resolver)

borkenbuild = False
spacesave = 0

headers = {'User-Agent': 'Mozilla/5.0 (compatible; MSIE 6.0; OpenStreetMap Editor Layer Index CI check)'}


logger.warning("This is a new and improved check for new or changed imagery sources. "
               "It is currently in beta stage. Please report any issues.")


def get_http_headers(source):
    """ Extract http headers from source"""
    custom_headers = {}
    custom_headers.update(headers)
    if 'custom-http-headers' in source['properties']:
        key = source['properties']['custom-http-headers']['header-name']
        value = source['properties']['custom-http-headers']['header-value']
        custom_headers[key] = value
    return custom_headers


def test_url(url, headers):
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            return True
    except:
        pass
    return False


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


def check_wms(source, info_msgs, warning_msgs, error_msgs):
    """
    Check WMS source

    Parameters
    ----------
    source : dict
        Source dictionary
    info_msgs : list
        Good messages
    warning_msgs: list
        Warning messages
    error_msgs: list:
        Error Messages
    """

    wms_url = source['properties']['url']
    source_headers = get_http_headers(source)

    params = ["{proj}", "{bbox}", "{width}", "{height}"]
    missingparams = [p for p in params if p not in wms_url]
    if len(missingparams) > 0:
        error_msgs.append("The following values are missing in the URL: {}".format(",".join(missingparams)))

    wms_args = {}
    u = urlparse(wms_url)
    url_parts = list(u)
    for k, v in parse_qsl(u.query, keep_blank_values=True):
        wms_args[k.lower()] = v

    def validate_wms_getmap_url():
        """
        Layers and styles can contain whitespaces. Ignore them here. They are checked against GetCapabilities later.
        """
        url_parts_without_layers = "&".join(["{}={}".format(key, value) for key, value in wms_args.items()
                                             if key not in {'layers', 'styles'}])
        parts = url_parts.copy()
        parts[4] = url_parts_without_layers
        url = urlunparse(parts).replace('{', '').replace('}', '')
        return validators.url(url)

    if not validate_wms_getmap_url():
        error_msgs.append("URL validation error: {}".format(wms_url))

    # Check mandatory WMS GetMap parameters (Table 8, Section 7.3.2, WMS 1.3.0 specification)
    missing_request_parameters = set()
    is_esri = 'request' not in wms_args
    if is_esri:
        required_parameters = ['f', 'bbox', 'size', 'imageSR', 'bboxSR', 'format']
    else:
        required_parameters = ['version', 'request', 'layers', 'bbox', 'width', 'height', 'format']
    for request_parameter in required_parameters:
        if request_parameter.lower() not in wms_args:
            missing_request_parameters.add(request_parameter)

    # Nothing more to do for esri rest api
    if is_esri:
        return

    if 'version' in wms_args and wms_args['version'] == '1.3.0':
        if 'crs' not in wms_args:
            missing_request_parameters.add('crs')
        if 'srs' in wms_args:
            error_msgs.append("WMS {} urls should not contain SRS parameter.".format(wms_args['version']))
    elif 'version' in wms_args and not wms_args['version'] == '1.3.0':
        if 'srs' not in wms_args:
            missing_request_parameters.add('srs')
        if 'crs' in wms_args:
            error_msgs.append("WMS {} urls should not contain CRS parameter.".format(wms_args['version']))
    if len(missing_request_parameters) > 0:
        missing_request_parameters_str = ",".join(missing_request_parameters)
        error_msgs.append("Parameter '{}' is missing in url.".format(missing_request_parameters_str))
        return
    # Styles is mandatory according to the WMS specification, but some WMS servers seems not to care
    if 'styles' not in wms_args:
        warning_msgs.append("Parameter 'styles' is missing in url. 'STYLES=' can be used to request default style.")

    def get_getcapabilitie_url(wms_version=None):

        get_capabilities_args = {'service': 'WMS',
                                 'request': 'GetCapabilities'}
        if wms_version is not None:
            get_capabilities_args['version'] = wms_version

        # Keep extra arguments, such as map or key
        for key in wms_args:
            if key not in {'version', 'request', 'layers', 'bbox', 'width', 'height', 'format', 'crs', 'srs', 'styles'}:
                get_capabilities_args[key] = wms_args[key]

        url_parts[4] = urlencode(list(get_capabilities_args.items()))
        return urlunparse(url_parts)

    # We first send a service=WMS&request=GetCapabilities request to server
    # According to the WMS Specification Section 6.2 Version numbering and negotiation, the server should return
    # the GetCapabilities XML with the highest version the server supports.
    # If this fails, it is tried to explicitly specify a WMS version
    exceptions = []
    wms = None
    for wmsversion in [None, '1.3.0', '1.1.1', '1.1.0', '1.0.0']:
        if wmsversion is None:
            wmsversion_str = "-"
        else:
            wmsversion_str = wmsversion

        try:
            wms_getcapabilites_url = get_getcapabilitie_url(wmsversion)
            r = requests.get(wms_getcapabilites_url, headers=source_headers)
            xml = r.text
            wms = parse_wms(xml)
            if wms is not None:
                break
        except Exception as e:
            exceptions.append("WMS {}: Error: {}".format(wmsversion_str, str(e)))
            continue

    if wms is None:
        for msg in exceptions:
            error_msgs.append(msg)
        return

    for access_constraint in wms['AccessConstraints']:
        info_msgs.append("AccessConstraints: {}".format(access_constraint))
    for fee in wms['Fees']:
        info_msgs.append("Fee: {}".format(fee))

    if source['geometry'] is None:
        geom = None
    else:
        geom = shape(source['geometry'])

    # Check layers
    if 'layers' in wms_args:
        layer_arg = wms_args['layers']
        layers = layer_arg.split(',')
        not_found_layers = []
        for layer_name in layer_arg.split(","):
            if layer_name not in wms['layers']:
                not_found_layers.append(layer_name)
        if len(not_found_layers) > 0:
            error_msgs.append("Layers '{}' not advertised by WMS GetCapabilities "
                              "request.".format(",".join(not_found_layers)))

        # Check source geometry against layer bounding box
        # Regardless of its projection, each layer should advertise an approximated bounding box in lon/lat.
        # See WMS 1.3.0 Specification Section 7.2.4.6.6 EX_GeographicBoundingBox
        if geom is not None and geom.is_valid:
            max_outside = 0.0
            for layer_name in layers:
                if layer_name in wms['layers']:
                    bbox = wms['layers'][layer_name]['BBOX']
                    geom_bbox = box(*bbox)
                    geom_outside_bbox = geom.difference(geom_bbox)
                    area_outside_bbox = geom_outside_bbox.area / geom.area * 100.0
                    max_outside = max(max_outside, area_outside_bbox)
            # 5% is an arbitrary chosen value and should be adapted as needed
            if max_outside > 5.0:
                error_msgs.append("{}% of geometry is outside of the layers bounding box. "
                                  "Geometry should be checked".format(round(area_outside_bbox, 2)))

        # Check styles
        if 'styles' in wms_args:
            style = wms_args['styles']
            # default style needs not to be advertised by the server
            if not (style == 'default' or style == '' or style == ',' * len(layers)):
                styles = wms_args['styles'].split(',')
                if not len(styles) == len(layers):
                    error_msgs.append("Not the same number of styles and layers.")
                else:
                    for layer_name, style in zip(layers, styles):
                        if (len(style) > 0 and not style == 'default' and layer_name in wms['layers'] and
                                style not in wms['layers'][layer_name]['Styles']):
                            error_msgs.append("Layer '{}' does not support style '{}'".format(layer_name, style))

        # Check CRS
        crs_should_included_if_available = {'EPSG:4326', 'EPSG:3857', 'CRS:84'}
        if 'available_projections' not in source['properties']:
            error_msgs.append("source is missing 'available_projections' element.")
        else:
            for layer_name in layers:
                if layer_name in wms['layers']:
                    not_supported_crs = set()
                    for crs in source['properties']['available_projections']:
                        if crs.upper() not in wms['layers'][layer_name]['CRS']:
                            not_supported_crs.add(crs)

                    if len(not_supported_crs) > 0:
                        supported_crs_str = ",".join(wms['layers'][layer_name]['CRS'])
                        not_supported_crs_str = ",".join(not_supported_crs)
                        warning_msgs.append("Layer '{}': CRS '{}' not in: {}".format(layer_name,
                                                                                     not_supported_crs_str,
                                                                                     supported_crs_str))

                    supported_but_not_included = set()
                    for crs in crs_should_included_if_available:
                        if (crs not in source['properties']['available_projections'] and
                                crs in wms['layers'][layer_name]['CRS']):
                            supported_but_not_included.add(crs)

                    if len(supported_but_not_included) > 0:
                        supported_but_not_included_str = ','.join(supported_but_not_included)
                        warning_msgs.append("Layer '{}': CRS '{}' not included in available_projections but "
                                            "supported by server.".format(layer_name, supported_but_not_included_str))

    if wms_args['version'] < wms['version']:
        warning_msgs.append("Query requests WMS version '{}', server supports '{}'".format(wms_args['version'],
                                                                                           wms['version']))

    # Check formats
    imagery_format = wms_args['format']
    imagery_formats_str = "', '".join(wms['formats'])
    if imagery_format not in wms['formats']:
        error_msgs.append("Format '{}' not in '{}'.".format(imagery_format, imagery_formats_str))

    if 'category' in source['properties'] and 'photo' in source['properties']['category']:
        if 'jpeg' not in imagery_format and 'jpeg' in imagery_formats_str:
            warning_msgs.append("Server supports JPEG, but '{}' is used. "
                                "JPEG is typically preferred for photo sources, but might not be always "
                                "the best choice. "
                                "(Server supports: '{}')".format(imagery_format, imagery_formats_str))


def check_wms_endpoint(source, info_msgs, warning_msgs, error_msgs):
    """
    Check WMS Endpoint source

    Currently it is only tested if a GetCapabilities request can be parsed.

    Parameters
    ----------
    source : dict
        Source dictionary
    info_msgs : list
        Good messages
    warning_msgs: list
        Warning messages
    error_msgs: list:
        Error Messages

    """

    wms_url = source['properties']['url']
    source_headers = get_http_headers(source)
    if not validators.url(wms_url):
        error_msgs.append("URL validation error: {}".format(wms_url))

    wms_args = {}
    u = urlparse(wms_url)
    url_parts = list(u)
    for k, v in parse_qsl(u.query, keep_blank_values=True):
        wms_args[k.lower()] = v

    def get_getcapabilitie_url(wms_version=None):

        get_capabilities_args = {'service': 'WMS',
                                 'request': 'GetCapabilities'}
        if wms_version is not None:
            get_capabilities_args['version'] = wms_version

        # Keep extra arguments, such as map or key
        for key in wms_args:
            if key not in {'version', 'request', 'layers', 'bbox', 'width', 'height', 'format', 'crs', 'srs'}:
                get_capabilities_args[key] = wms_args[key]

        url_parts[4] = urlencode(list(get_capabilities_args.items()))
        return urlunparse(url_parts)

    for wmsversion in [None, '1.3.0', '1.1.1', '1.1.0', '1.0.0']:
        try:
            url = get_getcapabilitie_url(wms_version=wmsversion)
            r = requests.get(url, headers=source_headers)
            xml = r.text
            wms = parse_wms(xml)

            for access_constraint in wms['AccessConstraints']:
                info_msgs.append("AccessConstraints: {}".format(access_constraint))
            for fee in wms['Fees']:
                info_msgs.append("Fee: {}".format(fee))

            break
        except Exception as e:
            error_msgs.append("WMS: {} Exception: {}".format(wmsversion, str(e)))


def check_wmts(source, info_msgs, warning_msgs, error_msgs):
    """
    Check WMTS source

    Parameters
    ----------
    source : dict
        Source dictionary
    info_msgs : list
        Good messages
    warning_msgs: list
        Warning messages
    error_msgs: list:
        Error Messages
    """

    try:
        wmts_url = source['properties']['url']
        if not validators.url(wmts_url):
            error_msgs.append("URL validation error: {}".format(wmts_url))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            wmts = WebMapTileService(wmts_url)
    except Exception as e:
        error_msgs.append("Exception: {}".format(str(e)))


def check_tms(source, info_msgs, warning_msgs, error_msgs):
    """
    Check TMS source

    Parameters
    ----------
    source : dict
        Source dictionary
    info_msgs : list
        Good messages
    warning_msgs: list
        Warning messages
    error_msgs: list:
        Error Messages

    """

    try:
        if 'geometry' in source and source['geometry'] is not None:
            geom = shape(source['geometry'])
            centroid = geom.representative_point()
        else:
            centroid = Point(6.1, 49.6)

        tms_url = source['properties']['url']
        source_headers = get_http_headers(source)

        def validate_url():
            url = re.sub(r'switch:?([^}]*)', 'switch', tms_url).replace('{', '').replace('}', '')
            return validators.url(url)

        if not validate_url():
            error_msgs.append("URL validation error: {}".format(tms_url))

        parameters = {}

        # {z} instead of {zoom}
        if '{z}' in source['properties']['url']:
            error_msgs.append('{z} found instead of {zoom} in tile url')
            return

        if '{apikey}' in tms_url:
            warning_msgs.append("Not possible to check URL, apikey is required.")
            return
        if "{switch:" in tms_url:
            match = re.search(r'switch:?([^}]*)', tms_url)
            switches = match.group(1).split(',')
            tms_url = tms_url.replace(match.group(0), 'switch')
            parameters['switch'] = switches[0]

        min_zoom = 0
        max_zoom = 22
        if 'min_zoom' in source['properties']:
            min_zoom = int(source['properties']['min_zoom'])
        if 'max_zoom' in source['properties']:
            max_zoom = int(source['properties']['max_zoom'])

        zoom_failures = []
        zoom_success = []
        tested_zooms = set()

        def test_zoom(zoom):
            tested_zooms.add(zoom)
            tile = mercantile.tile(centroid.x, centroid.y, zoom)

            query_url = tms_url
            if '{-y}' in tms_url:
                y = 2 ** zoom - 1 - tile.y
                query_url = query_url.replace('{-y}', str(y))
            elif '{!y}' in tms_url:
                y = 2 ** (zoom - 1) - 1 - tile.y
                query_url = query_url.replace('{!y}', str(y))
            else:
                query_url = query_url.replace('{y}', str(tile.y))
            parameters['x'] = tile.x
            parameters['zoom'] = zoom
            query_url = query_url.format(**parameters)
            if test_url(query_url, source_headers):
                zoom_success.append(zoom)
                return True
            else:
                zoom_failures.append(zoom)
                return False

        # Test zoom levels
        for zoom in range(min_zoom, max_zoom + 1):
            test_zoom(zoom)

        tested_str = ",".join(list(map(str, sorted(tested_zooms))))
        if len(zoom_failures) == 0 and len(zoom_success) > 0:
            info_msgs.append("Zoom levels reachable. (Tested: {})".format(tested_str))
        elif len(zoom_failures) > 0 and len(zoom_success) > 0:
            not_found_str = ",".join(list(map(str, sorted(zoom_failures))))
            warning_msgs.append("Zoom level {} not reachable. (Tested: {}) "
                                "Tiles might not be present at tested location: {},{}".format(not_found_str,
                                                                                              tested_str,
                                                                                              centroid.x,
                                                                                              centroid.y))
        else:
            error_msgs.append("No zoom level reachable. (Tested: {}) "
                              "Tiles might not be present at tested location: {},{}".format(tested_str,
                                                                                            centroid.x,
                                                                                            centroid.y))

    except Exception as e:
        error_msgs.append("Exception: {}".format(str(e)))


for filename in arguments.path:

    if not filename.lower()[-8:] == '.geojson':
        logger.info(f"{filename} is not a geojson file, skip")
        continue

    if not os.path.exists(filename):
        logger.info(f"{filename} does not exist, skip")
        continue

    try:
        logger.info("Processing {}".format(filename))

        # dict_raise_on_duplicates raises error on duplicate keys in geojson
        source = json.load(io.open(filename, encoding='utf-8'), object_pairs_hook=dict_raise_on_duplicates)

        # jsonschema validate
        validator.validate(source, schema)

        info_msgs = []
        warning_msgs = []
        error_msgs = []

        # Check for license url. Too many missing to mark as required in schema.
        if 'license_url' not in source['properties']:
            error_msgs.append("{} has no license_url set".format(filename))

        # Check if license url exists
        else:
            try:
                r = requests.get(source['properties']['license_url'], headers=headers)
                if not r.status_code == 200:
                    error_msgs.append("{}: license url {} is not reachable: HTTP code: {}".format(
                        filename, source['properties']['license_url'], r.status_code))

            except Exception as e:
                error_msgs.append("{}: license url {} is not reachable: {}".format(
                    filename, source['properties']['license_url'], str(e)))

        # Check attribution url exists
        if 'attribution' in source['properties']:
            if 'url' in source['properties']['attribution']:
                url = source['properties']['attribution']['url']
                try:
                    r = requests.get(url, headers=headers)
                    if not r.status_code == 200:
                        error_msgs.append("{}: attribution url {} is not reachable: HTTP code: {}".format(
                            filename, url, r.status_code))

                except Exception as e:
                    error_msgs.append("{}: attribution url {} is not reachable: {}".format(
                        filename, url, str(e)))

        # Check icon url exists
        if 'icon' in source['properties'] and source['properties']['icon'].startswith("http"):
            url = source['properties']['icon']
            try:
                r = requests.get(url, headers=headers)
                if not r.status_code == 200:
                    error_msgs.append("{}: icon url {} is not reachable: HTTP code: {}".format(
                        filename, url, r.status_code))

            except Exception as e:
                error_msgs.append("{}: icon url {} is not reachable: {}".format(
                    filename, url, str(e)))

        # Privacy policy
        # Check if privacy url is set
        if 'privacy_policy_url' not in source['properties']:
            error_msgs.append("{} has no privacy_policy_url. Adding privacy policies to sources"
                              " is important to comply with legal requirements in certain countries.".format(filename))
        else:
            # Check if privacy url exists
            try:
                r = requests.get(source['properties']['privacy_policy_url'], headers=headers)
                if not r.status_code == 200:
                    error_msgs.append("{}: privacy policy url {} is not reachable: HTTP code: {}".format(
                        filename, source['properties']['privacy_policy_url'], r.status_code))

            except Exception as e:
                error_msgs.append("{}: privacy policy url {} is not reachable: {}".format(
                    filename, source['properties']['privacy_policy_url'], str(e)))

        # Check for big fat embedded icons
        if 'icon' in source['properties']:
            if source['properties']['icon'].startswith("data:"):
                iconsize = len(source['properties']['icon'].encode('utf-8'))
                spacesave += iconsize
                logger.warning(
                    "{} icon should be disembedded to save {} KB".format(filename, round(iconsize / 1024.0, 2)))

        # Check for category
        if 'category' not in source['properties']:
            error_msgs.append("Source has no category.")

        # If we're not global we must have a geometry.
        # The geometry itself is validated by jsonschema
        if 'world' not in filename:
            if 'type' not in source['geometry']:
                error_msgs.append("{} should have a valid geometry or be global".format(filename))
            if source['geometry']['type'] != "Polygon":
                error_msgs.append("{} should have a Polygon geometry".format(filename))
            if 'country_code' not in source['properties']:
                error_msgs.append("{} should have a country or be global".format(filename))
        else:
            if 'geometry' not in source:
                error_msgs.append("{} should have null geometry".format(filename))
            elif source['geometry'] is not None:
                error_msgs.append("{} should have null geometry but it is {}".format(filename, source['geometry']))

        # Check if URL encodes HTTP headers
        if "user-agent" in source['properties']['url'].lower():
            error_msgs.append("URL should not encode HTTP headers")

        # Check imagery type
        if source['properties']['type'] == 'tms':
            check_tms(source, info_msgs, warning_msgs, error_msgs)
        elif source['properties']['type'] == 'wms':
            check_wms(source, info_msgs, warning_msgs, error_msgs)
        elif source['properties']['type'] == 'wms_endpoint':
            check_wms_endpoint(source, info_msgs, warning_msgs, error_msgs)
        elif source['properties']['type'] == 'wmts':
            check_wmts(source, info_msgs, warning_msgs, error_msgs)
        else:
            warning_msgs.append("Imagery type {} is currently not checked.".format(source['properties']['type']))

        for msg in info_msgs:
            logger.info(msg)
        for msg in warning_msgs:
            logger.warning(msg)
        for msg in error_msgs:
            logger.error(msg)

        if len(error_msgs) > 0:
            raise ValidationError("Errors occurred, see logs above.")
        logger.info("Finished processing {}".format(filename))
    except ValidationError as e:
        borkenbuild = True
if spacesave > 0:
    logger.warning("Disembedding all icons would save {} KB".format(round(spacesave / 1024.0, 2)))
if borkenbuild:
    raise SystemExit(1)
