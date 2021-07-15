from bs4 import BeautifulSoup
from pyproj.crs.crs import CRS
from .eliutils import epsg_3857_alias, valid_epsgs, get_transformer
from urllib.parse import urlsplit, urlunsplit


def get_tilemap_resource_url(url):
    """ Convert URLa in tms format to tilemap resources urls

    Parameters
    ----------
    url : str
        The url tms url (e.g. https://wms.openstreetmap.fr/tms/1.0.0/rennes_2014/{zoom}/{x}/{y})

    Returns
    -------
    str
        Teh tilemap resource url (e.g. https://wms.openstreetmap.fr/tms/1.0.0/rennes_2014)
    """
    u = list(urlsplit(url))
    u[2] = u[2].rsplit("/", maxsplit=3)[0]
    new_url = urlunsplit(u)
    return new_url


def parse_tilemap_resource(xml):
    """Parse relevant data from a tilemap resource
    
    See https://wiki.osgeo.org/wiki/Tile_Map_Service_Specification#TileMap_Resource

    Parameters
    ----------
    xml : string
        xml to be parsed

    Returns
    -------
    dict
        Parsed data

        Example:
        {
            "crs": "EPSG:3857",
            "bbox": [-20037508.34, -20037508.34, 20037508.34, 20037508.34],
            "min-zoom": 0,
            "max-zoom": 21,
        }

    """
    soup = BeautifulSoup(xml, "lxml")
    tilemap = soup.find("tilemap")

    # When we could not find a tilemap, we have nothing we can do
    if tilemap is None:
        return None

    data = {}
    srs_element = tilemap.find("srs")
    if srs_element and len(srs_element.contents) > 0:
        data["crs"] = srs_element.contents[0]

    # Parse bounding box if available
    bbox_element = tilemap.find("boundingbox")
    if bbox_element:
        bbox = [
            float(bbox_element[attribute])
            for attribute in ["minx", "miny", "maxx", "maxy"]
        ]
        data["bbox"] = bbox

        # Try to convert bounding box to EPSG:4326

        # Test if we can indentify the CRS
        proj = None
        if "crs" in data and (
            data["crs"].upper() == "EPSG:3785" or data["crs"].upper() in epsg_3857_alias
        ):
            proj = "EPSG:3785"
        elif "crs" in data and data["crs"].upper() in valid_epsgs:
            proj = data["crs"].upper()

        if proj:
            if proj == "EPSG:4326":
                data["bbox4326"] == data["bbox"]
            else:
                crs_from = CRS.from_string(proj)
                crs_to = CRS.from_string("epsg:4326")
                transformer = get_transformer(crs_from, crs_to)
                bbox4326 = list(transformer.transform(data["bbox"][0], data["bbox"][1])) + list(
                    transformer.transform(data["bbox"][2], data["bbox"][3])
                )
                data["bbox4326"] = bbox4326

    available_zooms = set()
    for tileset_element in soup.find_all("tileset"):
        href = tileset_element["href"]
        href_zoom_level = href.rsplit("/", maxsplit=1)[-1]
        available_zooms.add(int(href_zoom_level))
    if len(available_zooms) > 0:
        data["min_zoom"] = min(available_zooms)
        data["max_zoom"] = max(available_zooms)

    return data
