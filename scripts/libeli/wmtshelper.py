import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from io import StringIO
from typing import List, Optional, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .eliutils import (
    BoundingBox,
    find_attr,
    find_text,
    find_text_optional,
    findall_text,
)


@dataclass
class TileMatrix:
    """Representation of a TileMatrix element."""

    identifier: str
    scale_denominator: float
    top_left_corner: Tuple[float, float]
    tile_width: int
    tile_height: int
    matrix_width: int
    matrix_height: int


@dataclass
class TileMatrixSet:
    """Representation of a TileMatrixSet element."""

    identifier: str
    title: List[str]
    abstract: List[str]
    supported_crs: str
    well_known_scale_set: Optional[str]
    tile_matrix: List[TileMatrix]


@dataclass
class Dimension:
    """Representation of a Dimension element."""

    identifier: str
    default: Optional[str]
    current: Optional[bool]
    values: List[str]


@dataclass
class ResourceURL:
    """Representation of a ResourceURL element."""

    format: str
    resource_type: str
    template: str


@dataclass
class Layer:
    """Representation of a Layer element."""

    identifier: str
    title: List[str]
    abstract: List[str]
    bounding_box: Optional[BoundingBox]
    bounding_box_wsg84: Optional[BoundingBox]
    styles: List[str]
    formats: List[str]
    dimensions: List[Dimension]
    tile_matrix_set_keys: List[str]
    resource_urls: List[ResourceURL]


def is_googlemaps_compatible(tile_matrix_set: TileMatrixSet) -> bool:
    """Check if TileMatrixSet is compatible with the urn:ogc:def:wkss:OGC:1.0:GoogleMapsCompatible TileMatrixSet.

    Parameters
    ----------
    tile_matrix_set : TileMatrixSet
        The TileMatrixSet to check
    Returns
    -------
    bool
        True if tile_matrix_set is compatible

    """

    if not tile_matrix_set.supported_crs in {
        "urn:ogc:def:crs:EPSG:3857",
        "urn:ogc:def:crs:EPSG:6.18:3:3857",
        "urn:ogc:def:crs:EPSG::3857",
        "EPSG:3857",
    }:
        return False

    def calc_scale_denominator(level: int) -> float:
        return 559082264.0287178 / 2**level

    for tile_matrix in tile_matrix_set.tile_matrix:

        # Check tile size
        if not tile_matrix.tile_height % 256 == 0:
            return False
        if not tile_matrix.tile_width % 256 == 0:
            return False

        # The TileMatrix identifier must be an int representing the level
        # corresponding to the correct scale denominator
        try:
            tile_matrix_level = int(tile_matrix.identifier)
        except:
            return False
        if tile_matrix_level < 0:
            return False
        if not math.isclose(tile_matrix.scale_denominator, calc_scale_denominator(tile_matrix_level)):
            return False

        x, y = tile_matrix.top_left_corner
        if not math.isclose(x, -20037508.34278925) or not math.isclose(y, 20037508.34278925):
            return False

    return True


class WMTSCapabilities:
    """Representation of a response to a WMTS GetCapabilities request."""

    def __init__(self, get_capabilities_xml: str) -> None:
        """Inits a WMTSCapabilities object from the XML of a GetCapabilities request."""
        self.layers: dict[str, Layer] = {}
        self.tile_matrix_sets: dict[str, TileMatrixSet] = {}
        self._parse_xml(get_capabilities_xml)

    def _parse_xml(self, xml: str) -> None:

        try:
            it = ET.iterparse(StringIO(xml))
            for _, el in it:
                _, _, el.tag = el.tag.rpartition("}")
            root: ET.Element = it.root  # type: ignore
        except Exception as e:
            raise ET.ParseError(f"Could not parse XML. {e}")

        def parse_coordinate(value: str) -> Tuple[float, float]:
            vals = value.strip().split(" ")
            return float(vals[0]), float(vals[1])

        def parse_tile_matrix(element: ET.Element) -> TileMatrix:

            top_left_corner = parse_coordinate(find_text(element, "./TopLeftCorner"))

            tile_matrix = TileMatrix(
                identifier=find_text(element, "./Identifier"),
                scale_denominator=float(find_text(element, "./ScaleDenominator")),
                top_left_corner=top_left_corner,
                tile_width=int(find_text(element, "./TileWidth")),
                tile_height=int(find_text(element, "./TileHeight")),
                matrix_width=int(find_text(element, "./MatrixWidth")),
                matrix_height=int(find_text(element, "./MatrixHeight")),
            )
            return tile_matrix

        def parse_layer_dimension(element: ET.Element) -> Dimension:

            _current = None
            current_xml = xml.find("./Current")
            if current_xml is not None and element.text is not None:
                _current = element.text.lower() == "true"

            _dimension = Dimension(
                identifier=find_text(element, "./Identifier"),
                default=find_text_optional(element, "./Default"),
                current=_current,
                values=findall_text(element, "./Value"),
            )
            return _dimension

        def parse_resource_url(element: ET.Element) -> ResourceURL:
            _format = find_attr(element, "format")
            _resource_type = find_attr(element, "resourceType")
            _template = find_attr(element, "template")
            return ResourceURL(format=_format, resource_type=_resource_type, template=_template)

        def parse_layer(element: ET.Element) -> Layer:

            _bounding_box = None
            xml_bbox = element.find("./BoundingBox")
            if xml_bbox is not None:
                _bounding_box = parse_bounding_box(xml_bbox)

            _bounding_box84 = None
            xml_bbox84 = element.find("./WGS84BoundingBox")
            if xml_bbox84 is not None:
                _bounding_box84 = parse_bounding_box(xml_bbox84)

            _styles: List[str] = []
            for xml_style in element.findall(".//Style"):
                if xml_style is not None:
                    xml_style_text = xml_style.text
                    if xml_style_text is not None:
                        _styles.append(xml_style_text)

            _dimensions: List[Dimension] = []
            for xml_dimension in element.findall("./Dimension"):
                _dimension = parse_layer_dimension(xml_dimension)
                _dimensions.append(_dimension)

            _resource_urls: List[ResourceURL] = []
            for xml_resource_url in element.findall("./ResourceURL"):
                _resource_url = parse_resource_url(xml_resource_url)
                _resource_urls.append(_resource_url)

            layer = Layer(
                identifier=find_text(element, "./Identifier"),
                title=findall_text(element, "./Title"),
                abstract=findall_text(element, "./Abstract"),
                bounding_box=_bounding_box,
                bounding_box_wsg84=_bounding_box84,
                styles=_styles,
                formats=findall_text(element, "./Format"),
                dimensions=_dimensions,
                tile_matrix_set_keys=findall_text(element, "./TileMatrixSetLink/TileMatrixSet"),
                resource_urls=_resource_urls,
            )
            return layer

        def parse_tile_matrix_set(element: ET.Element) -> TileMatrixSet:
            _tile_matrix = [parse_tile_matrix(e) for e in element.findall(".//TileMatrix")]

            _well_known_scale_set = find_text_optional(element, "./WellKnownScaleSet")

            tile_matrix_set = TileMatrixSet(
                identifier=find_text(element, "./Identifier"),
                title=findall_text(element, "./Title"),
                abstract=findall_text(element, "./Abstract"),
                tile_matrix=_tile_matrix,
                supported_crs=find_text(element, "./SupportedCRS").strip(),
                well_known_scale_set=_well_known_scale_set,
            )
            return tile_matrix_set

        def parse_bounding_box(element: ET.Element) -> BoundingBox:
            lower = parse_coordinate(find_text(element, "./LowerCorner"))
            upper = parse_coordinate(find_text(element, "./UpperCorner"))
            return BoundingBox(west=lower[0], east=upper[0], south=lower[1], north=upper[1])

        # Parse TileMatrixSets
        for xml_tms in root.findall(".//Contents/TileMatrixSet"):
            tile_matrix_set = parse_tile_matrix_set(xml_tms)
            self.tile_matrix_sets[tile_matrix_set.identifier] = tile_matrix_set

        # Parse Layers
        for ls in root.findall(".//Contents/Layer"):
            layer = parse_layer(ls)
            self.layers[layer.identifier] = layer

    def supported_crs(self, layer: str) -> Set[str]:
        """List supported CRS of a layer

        Parameters
        ----------
        layer : str
            The name of the layer

        Returns
        -------
        Set[str]
            The CRS supported by the layer

        Raises
        ------
        RuntimeError
            If the layer is not supported
        """
        if layer not in self.layers:
            raise RuntimeError(f"Layer '{layer}' is not available. Available layers: {','.join(self.layers.keys())}")
        return {
            self.tile_matrix_sets[tile_matrix_set_key].supported_crs
            for tile_matrix_set_key in self.layers[layer].tile_matrix_set_keys
        }

    def tms_compatible_layers(self) -> Set[str]:
        """Returns the subset of layers that are TMS compatible.

        Returns
        -------
        Set[str]
            The TMS compatible layers
        """
        tms_compatible_layers: Set[str] = set()
        for layer in self.layers.values():

            # Check if there is a simpleProfileTile compatible ResourceURL
            for resource_url in layer.resource_urls:
                if resource_url.resource_type == "simpleProfileTile":
                    tms_compatible_layers.add(layer.identifier)
                    continue

            # Check if one of the linked TileMatrixSet is GoogleMapsCompatible
            for tile_matrix_set_key in self.layers[layer.identifier].tile_matrix_set_keys:
                tile_matrix_set = self.tile_matrix_sets[tile_matrix_set_key]
                if is_googlemaps_compatible(tile_matrix_set):
                    tms_compatible_layers.add(layer.identifier)

        return tms_compatible_layers

    def get_tms_compatible_urls(self, layer: str) -> Set[str]:
        """Returns a TMS URL if layer is TMS compatible.

        Parameters
        ----------
        layer : str
            The layer the TMS URL should be generated from

        Returns
        -------
        str
            The TMS Url

        Raises
        ------
        RuntimeError
            If the layer is not TMS compatible
        RuntimeError
            If the layer does not exist
        """
        if layer not in self.layers:
            raise RuntimeError(f"Layer '{layer}' is not available. Available layers: {','.join(self.layers.keys())}")

        urls: Set[str] = set()

        # Use simpleProfileTile if available
        for resource_url in self.layers[layer].resource_urls:
            if "simpleProfileTile" in resource_url.resource_type:
                urls.add(resource_url.template)

        # Use normal tile resources if there is a compatible tilematrix set
        for tile_matrix_set_key in self.layers[layer].tile_matrix_set_keys:
            tile_matrix_set = self.tile_matrix_sets[tile_matrix_set_key]

            if is_googlemaps_compatible(tile_matrix_set):
                for resource_url in self.layers[layer].resource_urls:
                    urls.add(resource_url.template)

        # Convert URLs in ELI format
        replacement_parameters = {
            "TileMatrix": "{zoom}",
            "TileCol": "{x}",
            "TileRow": "{y}",
            "TileMatrixSet": "{TileMatrixSet}",
        }
        for dimension in self.layers[layer].dimensions:
            if dimension.default is not None:
                value = dimension.default
            else:
                value = dimension.values[0]
            replacement_parameters[dimension.identifier] = value

        urls = set(map(lambda url: url.format(**replacement_parameters), urls))
        return urls


class WMTSURL:
    def __init__(self, url: str) -> None:
        self._url = urlparse(url)
        self._qsl = parse_qsl(self._url.query)
        self._qsl_norm = {k.lower(): v for k, v in parse_qsl(self._url.query)}

    def is_kvp(self) -> bool:
        return self._qsl_norm.get("service", "").lower() == "wmts"

    def is_rest(self) -> bool:
        return "1.0.0/" in self._url.path

    def layer(self) -> Optional[str]:
        if self.is_kvp():
            return self._qsl_norm.get("layer", None)
        elif self.is_rest():
            rest_parts = self._url.path.rsplit("1.0.0/", 1)[-1].split("/")
            if len(rest_parts) >= 4:
                return rest_parts[0]
        return None

    def tilematrixset(self) -> Optional[str]:
        if self.is_kvp():
            return self._qsl_norm.get("tilematrixset", None)
        elif self.is_rest():
            # The following order is recommended but not required!: style, firstDimension, ..., lastDimension, TileMatrixSet, TileMatrix, TileRow and TileCol
            path_parts = self._url.path.split("/")
            if len(path_parts) < 5:
                return None
            else:
                return path_parts[-4]

    def get_capabilities_url(self) -> Optional[str]:
        if self.is_kvp():
            args = {"service": "WMTS", "version": "1.0.0", "request": "WMTS"}
            query = urlencode(list([(k.upper(), v) for k, v in args.items()]))
            url_parts = list(self._url)
            url_parts[4] = query
            return urlunparse(url_parts)
        elif self.is_rest():
            match = re.match(r"(http.*\d.\d.\d/)", urlunparse(self._url))
            if match is not None:
                return match.group(1) + "WMTSCapabilities.xml"
        return None
