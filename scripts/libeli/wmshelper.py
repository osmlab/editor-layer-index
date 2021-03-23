import xml.etree.ElementTree as ET
from io import StringIO
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import pyproj
from pyproj import Transformer
from pyproj.crs import CRS
import mercantile
import validators
import regex


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


def get_bbox(proj, bounds, wms_version):
    """ Build wms bbox parameter for a GetMap request"""
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


def wms_version_from_url(url):
    """ Extract wms version from url"""
    u = urlparse(url.lower())
    qsl = dict(parse_qsl(u.query))
    if "version" not in qsl:
        return None
    else:
        return qsl["version"]


def wms_layers_from_url(url):
    """ Extract layers from url"""
    u = urlparse(url.lower())
    qsl = dict(parse_qsl(u.query))
    if "layers" not in qsl:
        return []
    else:
        return qsl["layers"]


def parse_wms_parameters(wms_url):
    """ Parse wms argumentes from url """
    wms_args = {}
    u = urlparse(wms_url)
    for k, v in parse_qsl(u.query, keep_blank_values=True):
        wms_args[k.lower()] = v
    return wms_args


def get_getcapabilities_url(wms_url, wms_version=None):
    """Construct a GetCapabilities request from a wms url"""
    wms_args = {}
    u = urlparse(wms_url)
    url_parts = list(u)
    for k, v in parse_qsl(u.query, keep_blank_values=True):
        wms_args[k.lower()] = v

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


def parse_wms(xml):
    """Rudimentary parsing of WMS Layers from GetCapabilites Request

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
        if es.text:
            constraints.append(regex.sub(r"\p{C}+", "", es.text))
    fees = []
    for es in root.findall(".//Fees"):
        if es.text:
            fees.append(regex.sub(r"\p{C}+", "", es.text))
    wms["Fees"] = fees
    wms["AccessConstraints"] = constraints

    return wms


def validate_wms_getmap_url(wms_url):
    """ Validate a wms GetMap url as used typically for a wms type in ELI"""
    wms_args = parse_wms_parameters(wms_url)
    url_parts = list(urlparse(wms_url))
    url_parts_without_layers = "&".join(
        [
            "{}={}".format(key, value)
            for key, value in wms_args.items()
            if key not in {"layers", "styles"}
        ]
    )
    url_parts[4] = url_parts_without_layers
    url = urlunparse(url_parts).replace("{", "").replace("}", "")
    return validators.url(url)
