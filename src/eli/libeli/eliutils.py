"""Shared coordinate systems, geometry, and XML utilities."""

import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass

from pyproj import database
from pyproj.crs.crs import CRS
from pyproj.enums import PJType
from pyproj.exceptions import CRSError
from pyproj.transformer import Transformer
from shapely.geometry import Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.geometry.multipolygon import MultiPolygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from eli.projections import useful_projections


@dataclass
class BoundingBox:
    """Geographic extent with a lazily constructed polygon."""

    west: float
    east: float
    south: float
    north: float

    _geom: Polygon | None = None

    def geom(self) -> Polygon:
        if self._geom is None:
            geom: Polygon = box(self.west, self.south, self.east, self.north)
            self._geom = geom
        return self._geom


epsg_3857_alias = set(
    [f"EPSG:{epsg}" for epsg in [900913, 3587, 54004, 41001, 102113, 102100, 3785]]
    + ["OSGEO:41001", "ESRI:102113", "ESRI:102100"]
)


def get_valid_epsgs() -> set[str]:
    """Retruns a Set of valid and not deprecated EPSG codes

    Returns
    -------
    Set[str]
        The valid EPSG codes
    """
    codes = {"CRS:84"}
    for pj_type in PJType:
        codes.update(
            map(
                lambda x: f"EPSG:{x}",
                database.get_codes("EPSG", pj_type, allow_deprecated=False),
            )
        )
    return codes


valid_epsgs = get_valid_epsgs()

# EPSG:3857 alias are valid if server does not support EPSG:3857
valid_epsgs.update(epsg_3857_alias)


def is_valid_epsg(epsg: str) -> bool:
    return epsg in valid_epsgs


def epsg_valid_in_bbox(epsg: str, geom: BaseGeometry) -> bool:
    if epsg == "CRS:84":
        return True

    try:
        crs = CRS.from_string(epsg)
    except CRSError:
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
    return crs_box.intersects(geom)


def clean_projections(
    epsg_codes: Iterable[str], bbox: BoundingBox | list[BoundingBox] | None = None
) -> set[str]:

    # Filter invalid codes
    filtered_codes = {epsg for epsg in epsg_codes if is_valid_epsg(epsg)}

    # Filter projections which area of use is outside of the boundign box
    if bbox is not None:
        if isinstance(bbox, list):
            geoms = [b.geom() for b in bbox]
            geom: BaseGeometry = unary_union(geoms)
        else:
            geom = bbox.geom()

        filtered_codes = {epsg for epsg in filtered_codes if epsg_valid_in_bbox(epsg, geom)}

    # There exists different alias for EPSG:3857. If alias are present, keep only one alias
    # (preferably EPSG:3857)
    if "EPSG:3857" in filtered_codes:
        filtered_codes -= epsg_3857_alias
    else:
        alias_codes = sorted(
            filtered_codes & epsg_3857_alias,
            key=lambda x: (x.split(":")[0], int(x.split(":")[1])),
            reverse=True,
        )
        filtered_codes -= set(alias_codes[1:])

    return useful_projections(filtered_codes)


transformers: dict[tuple[CRS, CRS], Transformer] = {}


def get_transformer(crs_from: CRS, crs_to: CRS) -> Transformer:
    """Cache transformer objects"""
    key = (crs_from, crs_to)
    if key not in transformers:
        transformers[key] = Transformer.from_crs(crs_from, crs_to, always_xy=True)
    return transformers[key]


def search_encoding(xml: str) -> str | None:
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


def find_text_optional(element: ET.Element, path: str) -> str | None:
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


def find_attr_optional(element: ET.Element, attribute: str) -> str | None:
    return element.attrib.get(attribute, None)


def findall_text(element: ET.Element, path: str) -> list[str]:
    es = element.findall(path)
    return [e.text for e in es if e.text is not None]


def orient_geometry_rfc7946(geometry: BaseGeometry) -> Polygon | MultiPolygon:
    """Converts orientation of geometry according to the GeoJSON RFC7946

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
        return orient(geometry, sign=1.0)
    if isinstance(geometry, MultiPolygon):
        return MultiPolygon([orient(geom, sign=1.0) for geom in geometry.geoms])
    raise ValueError(f"Only Polygon or MultiPolygon types are supported, not {type(geometry)}")


def parse_xml(xml: str) -> ET.Element:
    """Parse service XML and remove namespaces for version-independent lookups."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as error:
        raise ET.ParseError(f"Could not parse XML. {error}") from error
    for element in root.iter():
        _, _, element.tag = element.tag.rpartition("}")
    return root


def preferred_projection(projections: Iterable[str]) -> str | None:
    """Prefer web imagery coordinate systems, then the first valid advertised CRS."""
    available = set(projections)
    for preferred in ("EPSG:4326", "EPSG:3857"):
        if preferred in available:
            return preferred
    for projection in sorted(available):
        try:
            CRS.from_string(projection)
        except CRSError:
            continue
        return projection
    return None
