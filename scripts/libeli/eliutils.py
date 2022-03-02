import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

from pyproj.crs.crs import CRS
from pyproj.database import get_codes
from pyproj.enums import PJType
from pyproj.transformer import Transformer
from shapely.geometry import Polygon, box
from shapely.geometry.multipolygon import MultiPolygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union


@dataclass
class BoundingBox:

    west: float
    east: float
    south: float
    north: float

    _geom: Optional[Polygon] = None

    def geom(self) -> Polygon:
        if self._geom is None:
            geom: Polygon = box(self.west, self.south, self.east, self.north)
            self._geom = geom
        return self._geom


epsg_3857_alias = set(
    [f"EPSG:{epsg}" for epsg in [900913, 3587, 54004, 41001, 102113, 102100, 3785]]
    + ["OSGEO:41001", "ESRI:102113", "ESRI:102100"]
)


def get_valid_epsgs() -> Set[str]:
    """Retruns a Set of valid and not deprecated EPSG codes

    Returns
    -------
    Set[str]
        The valid EPSG codes
    """
    valid_epsgs = {"CRS:84"}
    for pj_type in PJType:
        valid_epsgs.update(
            map(
                lambda x: f"EPSG:{x}",
                get_codes("EPSG", pj_type, allow_deprecated=False),
            )
        )
    return valid_epsgs


valid_epsgs = get_valid_epsgs()

# EPSG:3857 alias are valid if server does not support EPSG:3857
valid_epsgs.update(epsg_3857_alias)


def is_valid_epsg(epsg: str) -> bool:
    return epsg in valid_epsgs


def epsg_valid_in_bbox(epsg: str, geom: Polygon | MultiPolygon) -> bool:
    if epsg == "CRS:84":
        return True

    try:
        crs = CRS.from_string(epsg)
    except:
        return False

    area_of_use = crs.area_of_use
    if area_of_use is None:
        return False

    crs_box: Polygon = box(
        area_of_use.west,
        area_of_use.south,
        area_of_use.east,
        area_of_use.north,
    )
    return crs_box.intersects(geom)  # type: ignore


def clean_projections(epsg_codes: Iterable[str], bbox: Optional[BoundingBox | List[BoundingBox]] = None) -> Set[str]:

    # Filter invalid codes
    filtered_codes = {epsg for epsg in epsg_codes if is_valid_epsg(epsg)}

    # Filter projections which area of use is outside of the boundign box
    if bbox is not None:

        if isinstance(bbox, list):
            geoms = [b.geom() for b in bbox]
            geom: Polygon | MultiPolygon = unary_union(geoms)
        else:
            geom = bbox.geom()

        filtered_codes = {epsg for epsg in filtered_codes if epsg_valid_in_bbox(epsg, geom)}

    # There exists different alias for EPSG:3857. If alias are present, keep only one alias (preferably EPSG:3857)
    if "EPSG:3857" in filtered_codes:
        filtered_codes -= epsg_3857_alias
    else:
        alias_codes = sorted(
            filtered_codes & epsg_3857_alias, key=lambda x: (x.split(":")[0], int(x.split(":")[1])), reverse=True
        )
        filtered_codes -= set(alias_codes[1:])

    return filtered_codes


transformers: Dict[Tuple[CRS, CRS], Transformer] = {}


def get_transformer(crs_from: CRS, crs_to: CRS) -> Transformer:
    """Cache transformer objects"""
    key = (crs_from, crs_to)
    if key not in transformers:
        transformers[key] = Transformer.from_crs(crs_from, crs_to, always_xy=True)
    return transformers[key]


def search_encoding(xml: str) -> Optional[str]:
    """Searchs for encoding="<ENCODING>" in xml and returns <ENCODING> if found

    Parameters
    ----------
    xml : str
        The XML to look for an encoding

    Returns
    -------
    Optional[str]
        The encoding or None
    """
    seek_xml = xml[:1000]
    m = re.search('encoding="([^\'"]+)', seek_xml)
    if m is None:
        return None
    if len(m.groups()) < 1:
        return None
    return m.group(1).strip()


def find_text(element: ET.Element, path: str) -> str:
    e = element.find(path)
    if e is None:
        raise RuntimeError(f"Path {path} was not found.")
    txt = e.text
    if txt is None:
        raise RuntimeError(f"Path {path} has no text.")
    return txt


def find_text_optional(element: ET.Element, path: str) -> Optional[str]:
    e = element.find(path)
    if e is None:
        return None
    txt = e.text
    if txt is None:
        return None
    return txt


def find_attr(element: ET.Element, attribute: str) -> str:
    if attribute not in element.attrib:
        raise RuntimeError(f"Attribute {attribute} was not found.")
    return element.attrib[attribute]


def find_attr_optional(element: ET.Element, attribute: str) -> Optional[str]:
    return element.attrib.get(attribute, None)


def findall_text(element: ET.Element, path: str) -> List[str]:
    es = element.findall(path)
    return [e.text for e in es if e.text is not None]


def orient_geometry_rfc7946(geometry: Polygon | MultiPolygon) -> Polygon | MultiPolygon:
    """ Converts orientation of geometry according to the GeoJSON RFC7946

    Parameters
    ----------
    geometry : Polygon | MultiPolygon
        The geometry to orient

    Returns
    -------
    Polygon | MultiPolygon
        The oriented geometry

    Raises
    ------
    ValueError
        If not a Polygon or MultiPolygon was passed
    """    

    if isinstance(geometry, Polygon):
        return orient(geometry, sign=1.0) # type: ignore
    elif isinstance(geometry, MultiPolygon): # type: ignore
        return MultiPolygon([orient(geom, sign=1.0) for geom in geometry.geoms]) # type: ignore
    raise ValueError(f"Only Polygon or MultiPolygon types are supported, not {type(geometry)}")
