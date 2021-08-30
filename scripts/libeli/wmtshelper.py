from io import StringIO
import xml.etree.ElementTree as ET
from typing import Optional
from dataclasses import dataclass


class ParserError(Exception):
    """Base class for exceptions related to parsing."""

    pass


def find_text(path: str, element: str, xmlelement: ET.Element) -> str:
    """Find text for path below xmlelement

    Parameters
    ----------
    path : str
        The path that is searched for the text
    element : str
        The element that is searched
    xmlelement : ET.Element
        The xml element that is searcher

    Returns
    -------
    str
        The text that is found

    Raises
    ------
    ParserError
        If path is not found
    """
    e = xmlelement.find(path)
    if e is None or e.text is None:
        raise ParserError(f"{path} for {element} not found")
    return e.text


def find_all_text(path: str, element: str, xmlelement: ET.Element) -> list[str]:
    """Find all text for path below xmlelement

    Parameters
    ----------
    path : str
        The path that is searched for the text
    element : str
        The element that is searched
    xmlelement : ET.Element
        The xml element that is searcher

    Returns
    -------
    str
        The text that is found

    Raises
    ------
    ParserError
        If path is not found
    """
    es = xmlelement.findall(path)
    if es is None:
        raise ParserError(f"{path} for {element} not found")
    return [e.text for e in es if e is not None and e.text is not None]


BoundingBox = tuple[float, float, float, float]


@dataclass
class TileMatrix:
    identifier: str
    scale_denominator: float
    top_left_corner: tuple[float, float]
    tile_width: int
    tile_height: int
    matrix_width: int
    matrix_height: int


@dataclass
class TileMatrixSet:
    identifier: str
    title: list[str]
    abstract: list[str]
    supported_crs: str
    well_known_scale_set: Optional[str]
    tile_matrix: list[TileMatrix]


@dataclass
class Dimension:
    identifier: str
    default: str
    current: Optional[bool]
    values: list[str]


@dataclass
class Layer:
    identifier: str
    title: list[str]
    abstract: list[str]
    bounding_box: Optional[BoundingBox]
    bounding_box_wsg84: Optional[BoundingBox]
    styles: list[str]
    formats: list[str]
    dimensions: list[Dimension]
    tile_matrix_set_keys: list[str]
    resource_url: Optional[str]


@dataclass
class WMTS:
    layers: dict[str, Layer]
    tile_matrix_sets: dict[str, TileMatrixSet]

    @staticmethod
    def parse_tile_matrix(xml: ET.Element) -> TileMatrix:

        _top_left_corner = list(map(float, find_text("./TopLeftCorner", "TileMatrix", xml).split(" ")))

        tile_matrix = TileMatrix(
            identifier=find_text("./Identifier", "TileMatrix", xml),
            scale_denominator=float(find_text("./ScaleDenominator", "TileMatrix", xml)),
            top_left_corner=(_top_left_corner[0], _top_left_corner[1]),
            tile_width=int(find_text("./TileWidth", "TileMatrix", xml)),
            tile_height=int(find_text("./TileHeight", "TileMatrix", xml)),
            matrix_width=int(find_text("./MatrixWidth", "TileMatrix", xml)),
            matrix_height=int(find_text("./MatrixHeight", "TileMatrix", xml)),
        )
        return tile_matrix


    @staticmethod
    def parse_layer_dimension(xml: ET.Element) -> Dimension:

        _current = None
        current_xml = xml.find("./Current")
        if current_xml is not None and current_xml.text is not None:
            _current = current_xml.text.lower() == "true"

        _dimension = Dimension(
            identifier=find_text("./Identifier", "Layer", xml),
            default=find_text("./Default", "Layer", xml),
            current=_current,
            values=find_all_text("./Value", "Layer", xml),
        )
        return _dimension


    @staticmethod
    def parse_layer(xml: ET.Element) -> Layer:

        _bounding_box = None
        xml_bbox = xml.find("./BoundingBox")
        if xml_bbox is not None:
            _bounding_box = WMTS.parse_bounding_box(xml_bbox)

        _bounding_box84 = None
        xml_bbox84 = xml.find("./WGS84BoundingBox")
        if xml_bbox84 is not None:
            _bounding_box84 = WMTS.parse_bounding_box(xml_bbox84)

        _styles: list[str] = []
        for xml_style in xml.findall(".//Style"):
            if xml_style is not None:
                xml_style_text = xml_style.text
                if xml_style_text is not None:
                    _styles.append(xml_style_text)

        _dimensions: list[Dimension] = []
        for xml_dimension in xml.findall("./Dimension"):
            _dimension = WMTS.parse_layer_dimension(xml_dimension)
            _dimensions.append(_dimension)

        _resource_url = None
        xml_resource_url = xml.find("./ResourceURL")
        if xml_resource_url is not None and "template" in xml_resource_url.attrib:
            _resource_url = xml_resource_url.attrib["template"]

        layer = Layer(
            identifier=find_text("./Identifier", "Layer", xml),
            title=find_all_text("./Title", "Layer", xml),
            abstract=find_all_text("./Abstract", "Layer", xml),
            bounding_box=_bounding_box,
            bounding_box_wsg84=_bounding_box84,
            styles=_styles,
            formats=find_all_text("./Format", "Layer", xml),
            dimensions=_dimensions,
            tile_matrix_set_keys=find_all_text("./TileMatrixSetLink/TileMatrixSet", "Layer", xml),
            resource_url=_resource_url,
        )
        return layer


    @staticmethod
    def parse_tile_matrix_set(xml: ET.Element) -> TileMatrixSet:
        _tile_matrix = [WMTS.parse_tile_matrix(tm) for tm in xml.findall(".//TileMatrix")]

        _well_known_scale_set = None
        xml_well_known_scale_set = xml.find("./WellKnownScaleSet")
        if xml_well_known_scale_set is not None:
            _well_known_scale_set = xml_well_known_scale_set.text

        tile_matrix_set = TileMatrixSet(
            identifier=find_text("./Identifier", "TileMatrixSet", xml),
            title=find_all_text("./Title", "TileMatrixSet", xml),
            abstract=find_all_text("./Abstract", "TileMatrixSet", xml),
            tile_matrix=_tile_matrix,
            supported_crs=find_text("./SupportedCRS", "TileMatrixSet", xml),
            well_known_scale_set=_well_known_scale_set,
        )
        return tile_matrix_set


    @staticmethod
    def parse_bounding_box(xml: ET.Element) -> BoundingBox:
        upper = list(map(float, find_text("./UpperCorner", "Layer", xml).split(" ")))
        lower = list(map(float, find_text("./LowerCorner", "Layer", xml).split(" ")))
        return (upper[0], upper[1], lower[0], lower[1])

    @classmethod
    def fromstring(cls, xml: str):
        "Construct a WMTS object from an xml string"

        # Remove prefixes to make parsing easier
        # From https://stackoverflow.com/questions/13412496/python-elementtree-module-how-to-ignore-the-namespace-of-xml-files-to-locate-ma
        try:
            it = ET.iterparse(StringIO(xml))
            for _, el in it:
                _, _, el.tag = el.tag.rpartition("}")
            root = it.root
        except Exception as e:
            raise ParserError(f"Could not parse XML. {e}")

        # Parse TileMatrixSets
        tile_matrix_sets: dict[str, TileMatrixSet] = {}
        for xml_tms in root.findall(".//Contents/TileMatrixSet"):
            tile_matrix_set = WMTS.parse_tile_matrix_set(xml_tms)
            tile_matrix_sets[tile_matrix_set.identifier] = tile_matrix_set

        # Parse Layers
        layers: dict[str, Layer] = {}
        for ls in root.findall(".//Contents/Layer"):
            layer = WMTS.parse_layer(ls)
            layers[layer.identifier] = layer

        return cls(layers=layers, tile_matrix_sets=tile_matrix_sets)
