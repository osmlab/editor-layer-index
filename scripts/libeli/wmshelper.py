import logging
import xml.etree.ElementTree as ET
from collections import OrderedDict
from dataclasses import dataclass
from io import StringIO
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import regex  # type: ignore
import validators
from pyproj.crs.crs import CRS

from .eliutils import (
    BoundingBox,
    find_attr,
    find_attr_optional,
    find_text,
    find_text_optional,
    findall_text,
    get_transformer,
)


@dataclass
class Style:
    """Representation of a Style element."""

    name: str
    title: Optional[str]


@dataclass
class Dimension:
    """Representation of a Dimension element."""

    name: str
    units: str
    unit_symbol: Optional[str]
    default: Optional[str]
    multiple_values: Optional[bool]
    current: Optional[bool]
    nearest_value: Optional[bool]
    values: List[str]


@dataclass
class Layer:
    """Representation of a Layer element."""

    name: Optional[str]
    # Title is mandatory for all layers. But some WMS server implementations allow not having a title.
    title: Optional[str]
    abstract: Optional[str]
    styles: Dict[str, Style]
    crs: Set[str]
    bbox: Optional[BoundingBox]
    dimension: Optional[Dimension]


@dataclass
class ServiceException:
    """Representation of a ServiceException element."""

    message: str
    code: Optional[str]


@dataclass
class ServiceExceptionReport:
    """Representation of a ServiceExceptionReport element."""

    exceptions: List[ServiceException]


class ServiceExceptionError(RuntimeError):
    """Request returned a ServiceException."""


def get_bbox(crs: str, bounds: BoundingBox, wms_version: str) -> str:
    """Calculate bbox parameter for a GetMap request.

    Parameters
    ----------
    crs : str
        The crs of the coordinates for the bbox parameter.
    bounds : BoundingBox
        The bounding box the coordinates should be calculated (in EPSG:4326).
    wms_version : str
        The WMS version the bbox parameter should be calculated for.

    Returns
    -------
    str
        The formatted bbox parameter
    """
    if crs in {"EPSG:4326", "CRS:84"}:
        if crs == "EPSG:4326" and wms_version == "1.3.0":
            return ",".join(map(str, [bounds.south, bounds.west, bounds.north, bounds.east]))
        else:
            return ",".join(map(str, [bounds.west, bounds.south, bounds.east, bounds.north]))
    else:
        try:
            crs_from = CRS.from_string("EPSG:4326")
            crs_to = CRS.from_string(crs)
            transformer = get_transformer(crs_from, crs_to)

            bl: Tuple[float, float] = transformer.transform(bounds.west, bounds.south)
            tr: Tuple[float, float] = transformer.transform(bounds.east, bounds.north)

            # WMS < 1.3.0 assumes x,y coordinate ordering.
            # WMS 1.3.0 expects coordinate ordering defined in CRS.
            if crs_to.axis_info[0].direction == "north" and wms_version == "1.3.0":
                return ",".join(map(lambda x: str(round(x, 2)), [bl[1], bl[0], tr[1], tr[0]]))
            else:
                return ",".join(map(lambda x: str(round(x, 2)), [bl[0], bl[1], tr[0], tr[1]]))
        except Exception as e:
            raise RuntimeError(f"Error when creating bbox parameter: {e}")


class WMSURL:
    """Helper class to facilitate manipulating of WMS Urls."""

    def __init__(self, url: str) -> None:
        """Inits a WMSURL from a WMS GetMap or GetCapabilities URL

        Parameters
        ----------
        url : str
            An WMS GetMap or GetCapabilities URL.
        """
        self._url = urlparse(url)

        # Filter parameter that might be required for authentication etc.
        ignored_parameters = {
            "version",
            "request",
            "layers",
            "styles",
            "crs",
            "srs",
            "bbox",
            "width",
            "height",
            "format",
            "transparent",
            "bgcolor",
            "exceptions",
            "time",
            "elevation",
            "dpi",
            "map_resolution",
            "format_options",
        }

        self._qsl = {k: v for k, v in parse_qsl(self._url.query) if k.lower() not in ignored_parameters}
        self._qsl_norm = {k.lower(): v for k, v in parse_qsl(self._url.query)}

    def get_capabilities_url(self, wms_version: Optional[str] = None) -> str:
        """Returns a GetCapabilities URL.

        Parameters
        ----------
        wms_version : Optional[str], optional
            The WMS version that is requested, by default None
        uppercase : bool, optional
            If URL parameter names should be upper case, by default False

        Returns
        -------
        str
            The GetCapabilities URL
        """

        args = {k.lower(): v for k, v in self._qsl.items()}
        args.update({"service": "WMS", "request": "GetCapabilities"})
        if wms_version is not None:
            args["version"] = wms_version

        query = urlencode(list([(k.upper(), v) for k, v in args.items()]))
        url_parts = list(self._url)
        url_parts[4] = query
        return urlunparse(url_parts)

    def get_map_url(
        self,
        version: str,
        layers: List[str],
        styles: Optional[List[str]],
        crs: str,
        bounds: Optional[str | BoundingBox],
        format: str,
        width: str | int,
        height: str | int,
        transparent: Optional[bool] = None,
        background_color: Optional[str] = None,
        time: Optional[str] = None,
        # elevation: Optional[str]
    ) -> str:
        """Returns a formatted GetMap URL.

        Parameters
        ----------
        version : str
            The WMS version
        layers : List[str]
            The layers
        styles : Optional[List[str]]
            The Styles. Order of styles need to correspond with order of layers
        crs : str
            The EPSG code
        bounds : Optional[str | BoundingBox]
            The bounds of the request
        format : str
            The image format
        width : str | int
            The image width
        height :  str | int
            The image height
        transparent : Optional[bool], optional
            If images should be transparent, by default None
        background_color : Optional[str], optional
            If the images should have a background color, by default None
        time : Optional[str], optional
            The time dimension, by default None

        Returns
        -------
        str
            The formatted GetMap URL

        Raises
        ------
        RuntimeError
            If the creation of the URL failed
        """

        args: Dict[str, str] = OrderedDict()
        args["LAYERS"] = ",".join(layers)
        if styles is None:
            args["STYLES"] = ""
        else:
            args["STYLES"] = ",".join([s if s is not None else "" for s in styles])
        if version == "1.3.0":
            args["CRS"] = crs
        else:
            args["SRS"] = crs

        bbox = None
        if isinstance(bounds, BoundingBox):
            bbox = get_bbox(crs, bounds, version)
        elif isinstance(bounds, str):
            bbox = bounds
        if bbox is None:
            raise RuntimeError("It was not possible to calculate bbox.")

        args["BBOX"] = bbox
        args["FORMAT"] = format
        args["WIDTH"] = str(width)
        args["HEIGHT"] = str(height)
        if transparent is not None and transparent:
            args["TRANSPARENT"] = "TRUE"

        if background_color is not None:
            args["BGCOLOR"] = f"0x{background_color.upper()}"
        if time is not None:
            args["TIME"] = time

        args["VERSION"] = version
        args["SERVICE"] = "WMS"
        args["REQUEST"] = "GetMap"

        query = urlencode(list(args.items()), safe="/{},:")
        url_parts = list(self._url)
        url_parts[4] = query
        return urlunparse(url_parts)

    def wms_version(self) -> Optional[str]:
        """Returns the WMS version of the WMS URL.

        Returns
        -------
        Optional[str]
            The WMS version. None if the URL does not contain a WMS version
        """
        return self._qsl_norm.get("version", None)

    def layers(self) -> List[str]:
        """Returns a list with a layer names of the WMS URL.

        Note: Works only for GetMap URLs.

        Returns
        -------
        List[str]
            The layers
        """
        layers = self._qsl_norm.get("layers", "")
        return layers.split(",")

    def format(self) -> Optional[str]:
        """Returns the format of the GetMap request.

        Note: Works only for GetMap URLs.

        Returns
        -------
        Optional[str]
            The format if it is present in the URL
        """
        return self._qsl_norm.get("format", None)

    def styles(self) -> List[str]:
        """Returns the styles of the GetMap request.

        Note: Works only for GetMap URLs.

        Returns
        -------
        Optional[str]
            The styles if they are present in the URL
        """
        return self._qsl_norm.get("styles", "").split(",")

    def is_transparent(self) -> Optional[bool]:
        """Returns the transparent parameter of the GetMap request.

        Note: Works only for GetMap URLs.

        Returns
        -------
        Optional[bool]
            True/false if GetMap includes a transparent parameter, None otherwise
        """
        if "transparent" not in self._qsl_norm:
            return None
        else:
            return self._qsl_norm["transparent"].lower() == "true"

    def get_parameters(self) -> List[Tuple[str, str]]:
        """The parameters of the URL.

        Returns
        -------
        List[Tuple[str, str]]
            A dictionary with the parameters.
        """
        return parse_qsl(self._url.query, keep_blank_values=True)

    def is_valid_getmap_url(self) -> bool:
        """Validates if GetMap URL is a valid URL.

        Note: Works only for GetMap URLs.

        Returns
        -------
        bool
            True if URL is a valid GetMap URL
        """
        url = urlunparse(self._url)
        for key, rep in [
            ("{proj}", "EPSG:4326"),
            ("{bbox}", "-50,-50,50,50"),
            ("{width}", "100"),
            ("{height}", "100"),
        ]:
            url = url.replace(key, rep)
        return validators.url(url)  # type: ignore


def parse_bool(value: Optional[str]) -> Optional[bool]:
    """Test XML value for True.

    Parameters
    ----------
    value : Optional[str]
        The value

    Returns
    -------
    Optional[bool]
        The parsed bool value
    """
    if value is None:
        return None
    return value == "1" or value.lower() == "true"


class WMSCapabilities:
    """Representation of the XML of a response to a WMS GetCapabilities request."""

    def __init__(self, get_capabilities_xml: str) -> None:
        """Inits a WMSCapabilities object from the XML of a GetCapabilities request.

        Parameters
        ----------
        get_capabilities_xml : str
            The XML to parse
        """
        self.layers: Dict[str, Layer] = {}
        self.fees: List[str] = []
        self.access_constraints: List[str] = []
        self.formats: List[str] = []
        self._parse_xml(get_capabilities_xml)

    def _parse_xml(self, xml: str) -> None:

        try:
            it = ET.iterparse(StringIO(xml))
            for _, el in it:
                _, _, el.tag = el.tag.rpartition("}")
            root: ET.Element = it.root  # type: ignore
        except Exception as e:
            raise ET.ParseError(f"Could not parse XML. {e}")

        def parse_service_exceptions(element: ET.Element) -> List[ServiceException]:
            exceptions: List[ServiceException] = []
            for service_exception_element in element.findall("./ServiceException"):
                message = service_exception_element.text
                if message is not None:
                    message = message.strip()
                code = find_attr_optional(service_exception_element, "code")
                exceptions.append(ServiceException(message=message if message is not None else "", code=code))
            return exceptions

        root_tag = root.tag.rpartition("}")[-1]
        if root_tag in {"ServiceExceptionReport", "ServiceException"}:
            exceptions = parse_service_exceptions(root)
            message = ";".join([f"{e.message}" for e in exceptions])
            raise ServiceExceptionError(message)

        if root_tag not in {"WMT_MS_Capabilities", "WMS_Capabilities"}:
            raise RuntimeError(f"No Capabilities Element present: Root tag: {root_tag}")

        if "version" not in root.attrib:
            raise RuntimeError("WMS version cannot be identified.")

        version = root.attrib["version"]
        self.version = version

        def parse_styles(element: ET.Element, layer_name: Optional[str]) -> List[Style]:
            result: List[Style] = []
            for e in element.findall("./Style"):
                name = find_text_optional(e, "./Name")
                # Style must have a name that is used as parameter for STYLES
                # See WMS 1.3.0 specification 7.2.4.6.5 Style
                # However, there are WMS server that contain styles without name
                # We ignore them
                if name is None:
                    logging.warning(f"Layer '{layer_name}' has style without name. This style is ignored.")
                    continue
                title = find_text_optional(e, "./Title")
                result.append(Style(name=name, title=title))
            return result

        def parse_dimension(element: ET.Element) -> Optional[Dimension]:
            name = find_attr(element, "name")
            units = find_attr(element, "units")
            unit_symbol = find_attr_optional(element, "unitSymbol")
            default = find_attr_optional(element, "default")
            multiple_values = parse_bool(find_attr_optional(element, "multipleValues"))
            nearest_value = parse_bool(find_attr_optional(element, "nearestValue"))
            current = parse_bool(find_attr_optional(element, "current"))
            txt = element.text
            if txt is None:
                txt = ""
            values = txt.split(",")
            return Dimension(
                name=name,
                units=units,
                unit_symbol=unit_symbol,
                default=default,
                multiple_values=multiple_values,
                nearest_value=nearest_value,
                current=current,
                values=values,
            )

        def parse_boundingbox(element: ET.Element) -> Optional[BoundingBox]:
            # WMS 1.3.0
            e = element.find("./EX_GeographicBoundingBox")
            if e is not None:
                return BoundingBox(
                    west=float(find_text(e, "./westBoundLongitude").replace(",", ".")),
                    east=float(find_text(e, "./eastBoundLongitude").replace(",", ".")),
                    south=float(find_text(e, "./southBoundLatitude").replace(",", ".")),
                    north=float(find_text(e, "./northBoundLatitude").replace(",", ".")),
                )
            # WMS < 1.3.0
            e = element.find("./LatLonBoundingBox")
            if e is not None:
                return BoundingBox(
                    west=float(find_attr(e, "minx").replace(",", ".")),
                    east=float(find_attr(e, "maxx").replace(",", ".")),
                    south=float(find_attr(e, "miny").replace(",", ".")),
                    north=float(find_attr(e, "maxy").replace(",", ".")),
                )
            return None

        def parse_layer(
            element: ET.Element,
            parent_crs: Set[str] = set(),
            parent_styles: Dict[str, Style] = {},
            parent_bbox: Optional[BoundingBox] = None,
        ):
            # Parse metadata
            name = find_text_optional(element, "./Name")
            title = find_text_optional(element, "./Title")
            abstract = find_text_optional(element, "./Abstract")

            # Parse CRS
            crs = parent_crs.copy()
            # WMS >= 1.3.0
            for c in findall_text(element, "./CRS"):
                crs.add(c.upper())
            # WMS < 1.3.0
            for c in findall_text(element, "./SRS"):
                crs.add(c.upper())

            # Parse styles
            styles = parent_styles.copy()
            for style in parse_styles(element, name):
                styles[style.name] = style

            # Parse bounding box. If none present, use parents bounding box
            layer_bbox = parse_boundingbox(element)
            if layer_bbox is None and parent_bbox is not None:
                layer_bbox = parent_bbox

            # Parse dimension
            e = element.find(f"./Dimension")
            dimension = None
            if e is not None:
                dimension = parse_dimension(e)

            layer = Layer(
                name=name,
                title=title,
                abstract=abstract,
                styles=styles,
                crs=crs,
                bbox=layer_bbox,
                dimension=dimension,
            )
            if layer.name is not None:
                self.layers[layer.name] = layer

            for e in element.findall("./Layer"):
                parse_layer(e, layer.crs, layer.styles, layer.bbox)

        for layer_element in root.findall(".//Capability/Layer"):
            parse_layer(layer_element)

        # Parse formats
        # WMS > 1.0.0
        for e in root.findall(".//Capability/Request/GetMap/Format"):
            format = e.text
            if format is not None:
                self.formats.append(format)
        # WMS 1.0.0
        for e in root.findall(".//Capability/Request/Map/Format"):
            for c in e:
                self.formats.append(c.tag)

        # Parse access constraints and fees
        for e in root.findall(".//AccessConstraints"):
            access_constraint = e.text
            if access_constraint is not None:
                # Remove invisible control characters and unused code points
                stripped_access_constraint: str = regex.sub(r"\p{C}+", "", access_constraint)  # type: ignore
                self.access_constraints.append(stripped_access_constraint)

        for e in root.findall(".//Fees"):
            fee = e.text
            if fee is not None:
                # Remove invisible control characters and unused code points
                stripped_fee: str = regex.sub(r"\p{C}+", "", fee)  # type: ignore
                self.fees.append(stripped_fee)
