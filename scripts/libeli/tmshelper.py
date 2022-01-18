import xml.etree.ElementTree as ET
from dataclasses import dataclass
from io import StringIO
from typing import List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

from pyproj.crs.crs import CRS

from .eliutils import (
    BoundingBox,
    epsg_3857_alias,
    find_attr,
    find_text,
    find_text_optional,
    get_transformer,
    valid_epsgs,
)


@dataclass
class TileFormat:
    """TileFormat XML element representation."""

    width: int
    height: int
    mime_type: str
    extension: str


@dataclass
class TileSet:
    """TileSet XML element  representation."""

    href: str
    units_per_pixel: float
    order: int
    zoom_level: int


@dataclass
class TileMap:
    """TileMap XML element  representation."""

    title: str
    abstract: Optional[str]
    crs: str
    bbox: Optional[BoundingBox]
    bbox84: Optional[BoundingBox]
    tile_format: TileFormat
    tilesets: List[TileSet]


class TMSURL:
    """Helper class to facilitate handling of TMS URLs."""

    def __init__(self, url: str) -> None:
        """Inits TMSURL from an existing URL.

        Parameters
        ----------
        url : str
            The url tms url (e.g. https://wms.openstreetmap.fr/tms/1.0.0/rennes_2014/{zoom}/{x}/{y})
        """
        self._url = urlparse(url)

    def get_tilemap_resource_url(self) -> Optional[str]:
        """Get the TileMap resource URL.

        Note: According to the TMS specification URLs are only well defined from the TileMapService downwards and not upwards.
        This URL is a "best guess".

        See https://wiki.osgeo.org/wiki/Tile_Map_Service_Specification

        Returns
        -------
        Optional[str]
            The TileMap resource URL or None (e.g.  https://wms.openstreetmap.fr/tms/1.0.0/rennes_2014)
        """

        if self._url.path.count("/") < 3:
            return None

        url_parts = list(self._url)
        url_parts[2] = self._url.path.rsplit("/", maxsplit=3)[0]
        return urlunparse(url_parts)


class TileMapResource:
    """Representation of a TMS TileMapResource."""

    def __init__(self, tilemap_resource_xml: str) -> None:
        """Init TileMapResource from XML

        Parameters
        ----------
        tilemap_resource_xml : str
            The XML to parse
        """
        self.tile_map = None
        self._parse_xml(tilemap_resource_xml)

    def _parse_xml(self, xml: str) -> None:

        try:
            it = ET.iterparse(StringIO(xml))
            for _, el in it:
                _, _, el.tag = el.tag.rpartition("}")
            root: ET.Element = it.root  # type: ignore
        except Exception as e:
            raise ET.ParseError(f"Could not parse XML. {e}")

        def parse_tileset(element: ET.Element) -> TileSet:
            href = find_attr(element, "href")
            units_per_pixel = float(find_attr(element, "units-per-pixel"))
            order = int(find_attr(element, "order"))
            zoom_level = int(href.rsplit("/", maxsplit=1)[-1])
            return TileSet(href=href, units_per_pixel=units_per_pixel, order=order, zoom_level=zoom_level)

        def parse_tileformat(element: ET.Element) -> TileFormat:
            width = int(find_attr(element, "width"))
            height = int(find_attr(element, "height"))
            mime_type = find_attr(element, "mime-type")
            extension = find_attr(element, "extension")
            return TileFormat(width=width, height=height, mime_type=mime_type, extension=extension)

        if root.tag == "TileMap":
            tilemap_element = root
        else:
            tilemap_element = root.find("./TileMap")

        if tilemap_element is not None:

            title = find_text(tilemap_element, "Title")
            abstract = find_text_optional(tilemap_element, "Abstract")
            crs = find_text(tilemap_element, "SRS").upper()
            # Normalize EPSG:3785 alias to EPSG:3785
            if crs in epsg_3857_alias:
                crs = "EPSG:3785"

            tileformat_element = tilemap_element.find("TileFormat")
            if tileformat_element is None:
                raise RuntimeError("No TileFormat found.")
            tile_format = parse_tileformat(tileformat_element)

            bbox = None
            bbox84 = None
            boundingbox_element = tilemap_element.find("BoundingBox")
            if boundingbox_element is not None:
                bbox = BoundingBox(
                    west=float(find_attr(boundingbox_element, "minx")),
                    east=float(find_attr(boundingbox_element, "maxx")),
                    south=float(find_attr(boundingbox_element, "minx")),
                    north=float(find_attr(boundingbox_element, "maxy")),
                )

                # Calc bounding box in EPSG:4326
                if crs == "EPSG:4326":
                    bbox84 = bbox
                elif crs in valid_epsgs:
                    crs_from = CRS.from_string(crs)
                    crs_to = CRS.from_string("EPSG:4326")
                    transformer = get_transformer(crs_from, crs_to)
                    tl = transformer.transform(bbox.west, bbox.north)
                    br = transformer.transform(bbox.east, bbox.south)
                    bbox84 = BoundingBox(west=tl[0], east=br[0], south=br[1], north=tl[1])

            tilesets = [parse_tileset(tileset_element) for tileset_element in tilemap_element.findall(".//TileSet")]
            tilemap = TileMap(
                title=title,
                abstract=abstract,
                crs=crs,
                bbox=bbox,
                bbox84=bbox84,
                tile_format=tile_format,
                tilesets=tilesets,
            )
            self.tile_map = tilemap

    def get_min_max_zoom_level(self) -> Tuple[Optional[int], Optional[int]]:
        """Return the min, respectively max zoom level defined in the TileMapResource.

        Returns
        -------
        Tuple[Optional[int], Optional[int]]
            min, respectively max zoom level
        """
        if self.tile_map is not None:
            levels = [ts.zoom_level for ts in self.tile_map.tilesets]
            min_level = min(levels)
            max_level = max(levels)
            return min_level, max_level
        return None, None
