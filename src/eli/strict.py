"""Validate source metadata against live imagery services."""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import mercantile
import requests
import validators
from jsonschema import ValidationError
from shapely.errors import ShapelyError
from shapely.geometry import Point
from shapely.geometry.geo import mapping, shape
from shapely.validation import explain_validity, make_valid

from eli.common import load_json
from eli.libeli import eliutils, tmshelper, wmshelper, wmtshelper
from eli.projections import unused_projections
from eli.strict_context import Message, MessageLevel, ValidationContext


class StrictChecker(ValidationContext):
    """Check source metadata and imagery services for one invocation."""

    # Protocol alternatives must accumulate independent WMS diagnostics instead of returning early.
    # pylint: disable-next=R0912,R0914,R0915
    def check_wms(self, source: dict[str, Any], messages: list[Message]) -> None:
        """Check WMS source

        Parameters
        ----------
        source : Dict[str, Any]
            The source
        messages : List[Message]
            The list to add messages to
        """
        url = source["properties"]["url"]
        wms_url = wmshelper.WMSURL(url)
        source_headers = self.get_http_headers(source)
        params = ["{proj}", "{bbox}", "{width}", "{height}"]
        source_url_excl_synonyms = source["properties"]["url"].replace("{wkid}", "{proj}")
        missingparams = [p for p in params if p not in source_url_excl_synonyms]
        if len(missingparams) > 0:
            messages.append(
                Message(
                    level=MessageLevel.ERROR,
                    message=(
                        f"The following values are missing in the URL: {','.join(missingparams)}"
                    ),
                )
            )
        try:
            wms_url.is_valid_getmap_url()
        except validators.ValidationError as e:
            messages.append(
                Message(level=MessageLevel.ERROR, message=f"URL validation error {e} for {url}")
            )
        wms_args = {key.lower(): value for key, value in wms_url.get_parameters()}
        is_esri = "request" not in wms_args
        missing_request_parameters: set[str] = set()
        if is_esri:
            required_parameters = ["f", "bbox", "size", "imageSR", "bboxSR", "format"]
        else:
            required_parameters = [
                "version",
                "request",
                "layers",
                "bbox",
                "width",
                "height",
                "format",
            ]
        for request_parameter in required_parameters:
            if request_parameter.lower() not in wms_args:
                missing_request_parameters.add(request_parameter)
        if not is_esri:
            if "version" in wms_args and wms_args["version"] == "1.3.0":
                if "crs" not in wms_args:
                    missing_request_parameters.add("crs")
                if "srs" in wms_args:
                    messages.append(
                        Message(
                            level=MessageLevel.ERROR,
                            message=(
                                f"WMS {wms_args['version']} URLs should not contain SRS parameter: "
                                f"{url}"
                            ),
                        )
                    )
            elif "version" in wms_args and (not wms_args["version"] == "1.3.0"):
                if "srs" not in wms_args:
                    missing_request_parameters.add("srs")
                if "crs" in wms_args:
                    messages.append(
                        Message(
                            level=MessageLevel.ERROR,
                            message=(
                                f"WMS {wms_args['version']} URLs should not contain CRS parameter: "
                                f"{url}"
                            ),
                        )
                    )
        if len(missing_request_parameters) > 0:
            missing_request_parameters_str = ",".join(missing_request_parameters)
            messages.append(
                Message(
                    level=MessageLevel.ERROR,
                    message=(
                        f"Parameter '{missing_request_parameters_str}' is missing in URL: {url}."
                    ),
                )
            )
            return
        if is_esri:
            return
        if "styles" not in wms_args:
            messages.append(
                Message(
                    level=MessageLevel.WARNING,
                    message=(
                        "Parameter 'styles' is missing in url. 'STYLES=' can be used to "
                        f"request default style.: {url}"
                    ),
                )
            )
        exceptions: list[str] = []
        wms = None
        for wms_version in [None, "1.3.0", "1.1.1", "1.1.0", "1.0.0"]:
            if wms_version is None:
                wms_version_str = "-"
            else:
                wms_version_str = wms_version
            wms_getcapabilities_url = None
            try:
                wms_getcapabilities_url = wms_url.get_capabilities_url(wms_version=wms_version)
                _, xml = self.get_text_encoded(wms_getcapabilities_url, headers=source_headers)
                if xml is None:
                    exceptions.append(
                        f"WMS: no capabilities document from {wms_getcapabilities_url}"
                    )
                    break
                wms = wmshelper.WMSCapabilities(xml)
                break
            except (requests.ConnectionError, requests.Timeout) as e:
                exceptions.append(f"WMS: {type(e).__name__}: {e} {wms_getcapabilities_url}")
                break
            except (
                requests.RequestException,
                ET.ParseError,
                RuntimeError,
                ValueError,
                KeyError,
            ) as e:
                exceptions.append(f"WMS {wms_version_str}: Error: {e} {wms_getcapabilities_url}")
                continue
        if wms is None:
            for msg in exceptions:
                messages.append(Message(level=MessageLevel.ERROR, message=msg))
            return
        for access_constraint in wms.access_constraints:
            messages.append(
                Message(level=MessageLevel.INFO, message=f"AccessConstraints: {access_constraint}")
            )
        for fee in wms.fees:
            messages.append(Message(level=MessageLevel.INFO, message=f"Fee: {fee}"))
        if source["geometry"] is None:
            geom = None
        else:
            geom = shape(source["geometry"])
        # Protocol alternatives must accumulate independent WMS diagnostics instead of returning
        # early.
        # pylint: disable-next=R1702
        if "layers" in wms_args:
            layers = wms_args["layers"].split(",")
            not_found_layers = [layer_name for layer_name in layers if layer_name not in wms.layers]
            if len(not_found_layers) > 0:
                messages.append(
                    Message(
                        level=MessageLevel.ERROR,
                        message=(
                            "Layers '"
                            f"{','.join(not_found_layers)}"
                            "' not advertised by WMS GetCapabilities request (Some "
                            "server do not advertise layers, but they are very rare).: "
                            f"{url}"
                        ),
                    )
                )
            if not not_found_layers and geom is not None and geom.is_valid:
                bboxs: list[eliutils.BoundingBox] = []
                for layer_name in layers:
                    if layer_name in wms.layers:
                        layer_bbox = wms.layers[layer_name].bbox
                        if layer_bbox is not None:
                            bboxs.append(layer_bbox)
                max_area_outside = (
                    self.max_area_outside_bbox(geom, bboxs) if len(bboxs) == len(layers) else 0.0
                )
                if max_area_outside > 5.0:
                    messages.append(
                        Message(
                            level=MessageLevel.ERROR,
                            message=(
                                f"{round(max_area_outside, 2)}"
                                "% of geometry is outside of the layers bounding box. "
                                "Geometry should be checked"
                            ),
                        )
                    )
            if "styles" in wms_args:
                style_parameter = wms_args["styles"]
                if style_parameter not in ("default", "", "," * len(layers)):
                    styles = style_parameter.split(",")
                    if not len(styles) == len(layers):
                        messages.append(
                            Message(
                                level=MessageLevel.ERROR,
                                message=(
                                    f"Not the same number of styles and layers. {len(styles)} vs "
                                    f"{len(layers)}"
                                ),
                            )
                        )
                    else:
                        for layer_name, style_name in zip(layers, styles):
                            if (
                                len(style_name) > 0
                                and (not style_name == "default")
                                and (layer_name in wms.layers)
                                and (style_name not in wms.layers[layer_name].styles)
                            ):
                                messages.append(
                                    Message(
                                        level=MessageLevel.ERROR,
                                        message=(
                                            f"Layer '{layer_name}' does not support style '"
                                            f"{style_name}'"
                                        ),
                                    )
                                )
            if "available_projections" not in source["properties"]:
                messages.append(
                    Message(
                        level=MessageLevel.ERROR,
                        message=(
                            "Sources of type wms must include the 'available_projections' element."
                        ),
                    )
                )
            else:
                crs_should_included_if_available = {"EPSG:4326", "EPSG:3857", "CRS:84"}
                crs_should_included_if_available -= unused_projections(
                    source["properties"].get("available_projections", []) + ["CRS:84"], url
                )
                for layer_name in layers:
                    if layer_name in wms.layers:
                        not_supported_crs: set[str] = set()
                        available_projections: list[str] = source["properties"][
                            "available_projections"
                        ]
                        for crs in available_projections:
                            if crs.upper() not in wms.layers[layer_name].crs:
                                not_supported_crs.add(crs)
                        if len(not_supported_crs) > 0:
                            supported_crs_str = ",".join(wms.layers[layer_name].crs)
                            not_supported_crs_str = ",".join(not_supported_crs)
                            messages.append(
                                Message(
                                    level=MessageLevel.WARNING,
                                    message=(
                                        f"Layer '{layer_name}': CRS '{not_supported_crs_str}"
                                        f"' not in: {supported_crs_str}"
                                        ". Some server support CRS which are not advertised."
                                    ),
                                )
                            )
                        supported_but_not_included: set[str] = set()
                        for crs in crs_should_included_if_available:
                            if (
                                crs not in available_projections
                                and crs in wms.layers[layer_name].crs
                            ):
                                supported_but_not_included.add(crs)
                        if len(supported_but_not_included) > 0:
                            supported_but_not_included_str = ",".join(supported_but_not_included)
                            messages.append(
                                Message(
                                    level=MessageLevel.WARNING,
                                    message=(
                                        f"Layer '{layer_name}': CRS '"
                                        f"{supported_but_not_included_str}' not included in "
                                        "available_projections but supported by server."
                                    ),
                                )
                            )
        if wms_args["version"] < wms.version:
            messages.append(
                Message(
                    level=MessageLevel.WARNING,
                    message=(
                        f"Query requests WMS version '{wms_args['version']}', server supports '"
                        f"{wms.version}'"
                    ),
                )
            )
        request_imagery_format = wms_args["format"]
        wms_advertised_formats_str = "', '".join(wms.formats)
        if request_imagery_format not in wms.formats:
            messages.append(
                Message(
                    level=MessageLevel.ERROR,
                    message=(
                        f"Format '{request_imagery_format}' not in '{wms_advertised_formats_str}': "
                        f"{url}."
                    ),
                )
            )
        if "category" in source["properties"] and "photo" in source["properties"]["category"]:
            if "jpeg" not in request_imagery_format and "jpeg" in wms.formats:
                messages.append(
                    Message(
                        level=MessageLevel.WARNING,
                        message=(
                            "Server supports JPEG, but '"
                            f"{request_imagery_format}"
                            "' is used. JPEG is typically preferred for photo sources, "
                            "but might not be always the best choice. (Server supports: '"
                            f"{wms_advertised_formats_str}"
                            "')"
                        ),
                    )
                )

    def check_wms_endpoint(self, source: dict[str, Any], messages: list[Message]) -> None:
        """Check WMS Endpoint source

        Parameters
        ----------
        source : Dict[str, Any]
            The source
        messages : List[Message]
            The list to add messages to
        """
        url = source["properties"]["url"]
        wms_url = wmshelper.WMSURL(url)
        try:
            validators.url(url)
        except validators.ValidationError as e:
            messages.append(
                Message(level=MessageLevel.ERROR, message=f"URL validation error: {e} for {url}")
            )
        source_headers = self.get_http_headers(source)
        exceptions: list[str] = []
        wms = None
        for wms_version in [None, "1.3.0", "1.1.1", "1.1.0", "1.0.0"]:
            if wms_version is None:
                wms_version_str = "-"
            else:
                wms_version_str = wms_version
            wms_getcapabilities_url = None
            try:
                wms_getcapabilities_url = wms_url.get_capabilities_url(wms_version=wms_version)
                _, xml = self.get_text_encoded(wms_getcapabilities_url, headers=source_headers)
                if xml is None:
                    exceptions.append(
                        f"WMS: no capabilities document from {wms_getcapabilities_url}"
                    )
                    break
                wms = wmshelper.WMSCapabilities(xml)
                break
            except (requests.ConnectionError, requests.Timeout) as e:
                exceptions.append(f"WMS: {type(e).__name__}: {e} {wms_getcapabilities_url}")
                break
            except (
                requests.RequestException,
                ET.ParseError,
                RuntimeError,
                ValueError,
                KeyError,
            ) as e:
                exceptions.append(f"WMS {wms_version_str}: Error: {e} {wms_getcapabilities_url}")
                continue
        if wms is None:
            for msg in exceptions:
                messages.append(Message(level=MessageLevel.ERROR, message=msg))

    def check_wmts(self, source: dict[str, Any], messages: list[Message]) -> None:
        """Check WMTS source

        Parameters
        ----------
        source : Dict[str, Any]
            The source
        messages : List[Message]
            The list to add messages to
        """
        url = source["properties"]["url"]
        source_headers = self.get_http_headers(source)
        try:
            validators.url(url)
        except validators.ValidationError as e:
            messages.append(
                Message(level=MessageLevel.ERROR, message=f"URL validation error: {e} for {url}")
            )
        r, xml = self.get_text_encoded(url, headers=source_headers)
        if not r.status_code == 200:
            messages.append(
                Message(
                    level=MessageLevel.ERROR,
                    message=f"Failed to fetch {url}: HTTP code {r.status_code}",
                )
            )
        if xml is None:
            return
        wmts_capabilities = None
        try:
            wmts_capabilities = wmtshelper.WMTSCapabilities(xml)
        except (requests.RequestException, ET.ParseError, RuntimeError, ValueError, KeyError) as e:
            messages.append(
                Message(
                    level=MessageLevel.ERROR,
                    message=f"Failed to parse WMTS Capabilities for URL {url}: {e}",
                )
            )
        if wmts_capabilities is not None:
            tms_compatible_layers = wmts_capabilities.tms_compatible_layers()
            for layer in tms_compatible_layers:
                tms_urls = wmts_capabilities.get_tms_compatible_urls(layer)
                if len(tms_urls) == 1:
                    messages.append(
                        Message(
                            level=MessageLevel.WARNING,
                            message=(
                                f"Layer {layer} could be represented as type "
                                f"'tms' and the URL: {list(tms_urls)[0]}"
                            ),
                        )
                    )
                elif len(tms_urls) > 1:
                    messages.append(
                        Message(
                            level=MessageLevel.WARNING,
                            message=(
                                "Layer "
                                f"{layer}"
                                " could be represented as type 'tms' and one of the URLs: "
                                f"{', '.join(tms_urls)}"
                            ),
                        )
                    )

    # TMS metadata and tile probes accumulate independent diagnostics for one source.
    # pylint: disable-next=R0912,R0914,R0915
    def check_tms(self, source: dict[str, Any], messages: list[Message]) -> None:
        """Check TMS source

        Parameters
        ----------
        source : Dict[str, Any]
            The source
        messages : List[Message]
            The list to add messages to
        """
        # TMS metadata and tile probes accumulate independent diagnostics for one source.
        # pylint: disable-next=R1702
        try:
            url = source["properties"]["url"]
            source_headers = self.get_http_headers(source)
            if source["geometry"] is None:
                geom = None
            else:
                geom = shape(source["geometry"])
            try:
                _url = re.sub("switch:?([^}]*)", "switch", url).replace("{", "").replace("}", "")
                validators.url(_url)
            except validators.ValidationError as e:
                messages.append(
                    Message(level=MessageLevel.ERROR, message=f"URL validation error {e} / {url}")
                )
            parameters = {}
            if "{z}" in source["properties"]["url"]:
                messages.append(
                    Message(
                        level=MessageLevel.ERROR,
                        message=f"Parameter {{z}} is used instead of {{zoom}} in tile url: {url}",
                    )
                )
                return
            if "{apikey}" in url:
                messages.append(
                    Message(
                        level=MessageLevel.WARNING,
                        message=f"Not possible to check URL, apikey is required: {url}",
                    )
                )
                return
            match = re.search("switch:?([^}]*)", url)
            if match is not None:
                switches = match.group(1).split(",")
                url = url.replace(match.group(0), "switch")
                parameters["switch"] = switches[0]
            min_zoom = 0
            max_zoom = 22
            if "min_zoom" in source["properties"]:
                min_zoom = int(source["properties"]["min_zoom"])
            if "max_zoom" in source["properties"]:
                max_zoom = int(source["properties"]["max_zoom"])
            tms_url = tmshelper.TMSURL(url=url)
            tilemap_resource_url = tms_url.get_tilemap_resource_url()
            if tilemap_resource_url is not None:
                for tilemap_url in [
                    tilemap_resource_url,
                    tilemap_resource_url + "/tilemapresource.xml",
                ]:
                    try:
                        r, xml = self.get_text_encoded(
                            tilemap_url.format(**parameters), headers=self.headers
                        )
                        if r.status_code == 200 and xml is not None:
                            try:
                                tilemap_resource = tmshelper.TileMapResource(xml)
                            except (
                                requests.RequestException,
                                ET.ParseError,
                                RuntimeError,
                                ValueError,
                                KeyError,
                            ):
                                continue
                            if tilemap_resource.tile_map is None:
                                continue
                            tilemap_minzoom, tilemap_maxzoom = (
                                tilemap_resource.get_min_max_zoom_level()
                            )
                            if min_zoom != tilemap_minzoom:
                                messages.append(
                                    Message(
                                        level=MessageLevel.WARNING,
                                        message=(
                                            f"min_zoom level '{min_zoom}"
                                            "' not the same as specified in TileMap: '"
                                            f"{tilemap_minzoom}': {tilemap_url}"
                                            ". Caution: this might be "
                                            "intentional as some server "
                                            "timeout for low zoom levels."
                                        ),
                                    )
                                )
                            if not max_zoom == tilemap_maxzoom:
                                messages.append(
                                    Message(
                                        level=MessageLevel.WARNING,
                                        message=(
                                            f"max_zoom level '{max_zoom}"
                                            "' not the same as specified in TileMap: '"
                                            f"{tilemap_maxzoom}': {tilemap_url}"
                                        ),
                                    )
                                )
                            if geom is not None and tilemap_resource.tile_map.bbox84 is not None:
                                max_area_outside = self.max_area_outside_bbox(
                                    geom, tilemap_resource.tile_map.bbox84
                                )
                                if max_area_outside > 5.0:
                                    messages.append(
                                        Message(
                                            level=MessageLevel.ERROR,
                                            message=(
                                                f"{round(max_area_outside, 2)}"
                                                "% of geometry is outside of "
                                                "the layers bounding box. "
                                                "Geometry should be checked"
                                            ),
                                        )
                                    )
                            break
                    except (
                        requests.RequestException,
                        ET.ParseError,
                        RuntimeError,
                        ValueError,
                        KeyError,
                    ) as e:
                        print(f"Error fetching TMS: {e}: {url}")
            if geom is not None:
                centroid: Point = geom.representative_point()
            else:
                centroid = Point(6.1, 49.6)
            centroid_x: float = centroid.x
            centroid_y: float = centroid.y
            zoom_failures: list[tuple[int, str, int, str | None]] = []
            zoom_success: list[int] = []
            tested_zooms: set[int] = set()

            def test_zoom(zoom: int) -> None:
                tested_zooms.add(zoom)
                tile: mercantile.Tile = mercantile.tile(centroid_x, centroid_y, zoom)
                tile_x: int = tile.x
                tile_y: int = tile.y
                query_url = url
                if "{-y}" in url:
                    y = 2**zoom - 1 - tile_y
                    query_url = query_url.replace("{-y}", str(y))
                elif "{!y}" in url:
                    y = 2 ** (zoom - 1) - 1 - tile_y
                    query_url = query_url.replace("{!y}", str(y))
                else:
                    query_url = query_url.replace("{y}", str(tile_y))
                parameters["x"] = tile_x
                parameters["zoom"] = zoom
                query_url = query_url.format(**parameters)
                url_is_good, http_code, mime = self.test_image(query_url, source_headers)
                if url_is_good:
                    zoom_success.append(zoom)
                else:
                    zoom_failures.append((zoom, query_url, http_code, mime))

            for zoom in range(min_zoom, max_zoom + 1):
                test_zoom(zoom)
            tested_str = ",".join(list(map(str, sorted(tested_zooms))))
            sorted_failures = sorted(zoom_failures, key=lambda x: x[0])
            if len(zoom_failures) == 0 and len(zoom_success) > 0:
                messages.append(
                    Message(
                        level=MessageLevel.INFO,
                        message=f"Zoom levels reachable. (Tested: {tested_str})",
                    )
                )
            elif len(zoom_failures) > 0 and len(zoom_success) > 0:
                not_found_str = ",".join(
                    list(map(str, [level for level, _, _, _ in sorted_failures]))
                )
                messages.append(
                    Message(
                        level=MessageLevel.WARNING,
                        message=(
                            f"Zoom level {not_found_str} not reachable. (Tested: {tested_str}"
                            f") Tiles might not be present at tested location: {centroid_x},"
                            f"{centroid_y}"
                        ),
                    )
                )
                for level, url, http_code, mime_type in sorted_failures:
                    messages.append(
                        Message(
                            level=MessageLevel.WARNING,
                            message=(
                                f"URL for zoom level {level} returned HTTP Code {http_code}: "
                                f"{url} MIME type: {mime_type}"
                            ),
                        )
                    )
            else:
                messages.append(
                    Message(
                        level=MessageLevel.ERROR,
                        message=(
                            f"No zoom level reachable. (Tested: {tested_str}"
                            f") Tiles might not be present at tested location: {centroid_x},"
                            f"{centroid_y}"
                        ),
                    )
                )
                for level, url, http_code, mime_type in sorted_failures:
                    messages.append(
                        Message(
                            level=MessageLevel.WARNING,
                            message=(
                                f"URL for zoom level {level} returned HTTP Code {http_code}: "
                                f"{url} MIME type: {mime_type}"
                            ),
                        )
                    )
        except (requests.RequestException, ET.ParseError, RuntimeError, ValueError, KeyError) as e:
            messages.append(
                Message(
                    level=MessageLevel.ERROR, message=f"Failed testing TMS source: Exception: {e}"
                )
            )

    # Collect metadata and geometry diagnostics before reporting and continuing the source batch.
    # pylint: disable-next=R0912,R0914,R0915
    def run(self, paths: list[Path], root: Path) -> int:
        failed = False
        spacesave = 0
        for path in paths:
            self.filename = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
            if self.filename.lower()[-8:] != ".geojson":
                self.logger.debug("%s is not a geojson file, skip", self.filename)
                continue
            if not path.exists():
                self.logger.debug("%s does not exist, skip", self.filename)
                continue
            try:
                self.logger.info("Processing %s", self.filename)
                messages: list[Message] = []
                source = load_json(path)
                try:
                    self.validator.validate(source)
                except ValidationError as e:
                    messages.append(
                        Message(
                            level=MessageLevel.ERROR,
                            message=f"{self.filename} JSON validation error: {e}",
                        )
                    )
                self.logger.info("Type: %s", source["properties"]["type"])
                if source.get("geometry") is not None:
                    geom = shape(source["geometry"])
                    if not geom.is_valid:
                        try:
                            reason = explain_validity(geom)
                            messages.append(
                                Message(
                                    level=MessageLevel.ERROR,
                                    message=f"{self.filename} invalid geometry: {reason}",
                                )
                            )
                            valid_geom = make_valid(geom)
                            valid_geom = eliutils.orient_geometry_rfc7946(valid_geom)
                            valid_geom_json = json.dumps(
                                mapping(valid_geom), sort_keys=False, ensure_ascii=False
                            )
                            messages.append(
                                Message(
                                    level=MessageLevel.ERROR,
                                    message=(
                                        f"{self.filename} please consider using corrected "
                                        f"geometry: {valid_geom_json}"
                                    ),
                                )
                            )
                            geom = valid_geom
                        except (ShapelyError, ValueError) as error:
                            self.logger.warning("Geometry check failed: %s", error)
                    oriented_geom = eliutils.orient_geometry_rfc7946(geom)
                    if not json.dumps(mapping(geom)) == json.dumps(mapping(oriented_geom)):
                        messages.append(
                            Message(
                                level=MessageLevel.ERROR,
                                message=(
                                    f"{self.filename} ring orientation does not "
                                    "correspond to GeoJSON RFC7946"
                                ),
                            )
                        )
                        oriented_geom_json = json.dumps(
                            mapping(oriented_geom), sort_keys=False, ensure_ascii=False
                        )
                        messages.append(
                            Message(
                                level=MessageLevel.ERROR,
                                message=(
                                    f"{self.filename} please consider using corrected "
                                    f"geometry: {oriented_geom_json}"
                                ),
                            )
                        )
                if "license_url" not in source["properties"]:
                    messages.append(
                        Message(
                            level=MessageLevel.ERROR,
                            message=f"{self.filename} has no license_url set",
                        )
                    )
                else:
                    try:
                        r = self.get_response(
                            source["properties"]["license_url"], headers=self.headers, verify=False
                        )
                        if not r.status_code == 200:
                            messages.append(
                                Message(
                                    level=MessageLevel.ERROR,
                                    message=(
                                        f"{self.filename}"
                                        ": license url "
                                        f"{source['properties']['license_url']}"
                                        " is not reachable: HTTP code: "
                                        f"{r.status_code}"
                                    ),
                                )
                            )
                    except requests.RequestException as e:
                        messages.append(
                            Message(
                                level=MessageLevel.ERROR,
                                message=(
                                    f"{self.filename}"
                                    ": license url "
                                    f"{source['properties']['license_url']}"
                                    " is not reachable: "
                                    f"{e}"
                                ),
                            )
                        )
                if "attribution" in source["properties"]:
                    if "url" in source["properties"]["attribution"]:
                        url = source["properties"]["attribution"]["url"]
                        reachable, status_code = self.test_url(url, self.headers)
                        if not reachable:
                            messages.append(
                                Message(
                                    level=MessageLevel.ERROR,
                                    message=(
                                        f"{self.filename}: could not retrieve attribution url "
                                        f"{url}: HTTP code: {status_code}"
                                    ),
                                )
                            )
                if "icon" in source["properties"] and source["properties"]["icon"].startswith(
                    "http"
                ):
                    url = source["properties"]["icon"]
                    try:
                        r = self.get_response(url, headers=self.headers, verify=False)
                        if not r.status_code == 200:
                            messages.append(
                                Message(
                                    level=MessageLevel.ERROR,
                                    message=(
                                        f"{self.filename}: icon url {url}"
                                        f" is not reachable: HTTP code: {r.status_code}"
                                    ),
                                )
                            )
                    except requests.RequestException as e:
                        messages.append(
                            Message(
                                level=MessageLevel.ERROR,
                                message=f"{self.filename}: icon url {url} is not reachable: {e}",
                            )
                        )
                if "privacy_policy_url" not in source["properties"]:
                    messages.append(
                        Message(
                            level=MessageLevel.ERROR,
                            message=(
                                f"{self.filename}"
                                " has no privacy_policy_url. Adding privacy policies to "
                                "sources is important to comply with legal requirements in "
                                "certain countries."
                            ),
                        )
                    )
                elif isinstance(source["properties"]["privacy_policy_url"], str):
                    reachable, status_code = self.test_url(
                        source["properties"]["privacy_policy_url"], self.headers
                    )
                    if not reachable:
                        messages.append(
                            Message(
                                level=MessageLevel.ERROR,
                                message=(
                                    f"{self.filename}"
                                    ": could not retrieve privacy policy url "
                                    f"{source['properties']['privacy_policy_url']}"
                                    ": HTTP code: "
                                    f"{status_code}"
                                ),
                            )
                        )
                elif not isinstance(source["properties"]["privacy_policy_url"], str) and (
                    not (
                        isinstance(source["properties"]["privacy_policy_url"], bool)
                        and (not source["properties"]["privacy_policy_url"])
                    )
                ):
                    messages.append(
                        Message(
                            level=MessageLevel.ERROR,
                            message=(
                                f"{self.filename}"
                                ": privacy_policy_url can either be an URL or false, not: '"
                                f"{source['properties']['privacy_policy_url']}"
                                "'."
                            ),
                        )
                    )
                if "icon" in source["properties"]:
                    if source["properties"]["icon"].startswith("data:"):
                        iconsize = len(source["properties"]["icon"].encode("utf-8"))
                        spacesave += iconsize
                        self.logger.warning(
                            "%s icon should be disembedded to save %s KB",
                            self.filename,
                            round(iconsize / 1024.0, 2),
                        )
                if "category" not in source["properties"]:
                    messages.append(
                        Message(
                            level=MessageLevel.ERROR,
                            message=f"{self.filename}: no category is specified.",
                        )
                    )
                geometry = source.get("geometry")
                if "world" not in self.filename:
                    if not isinstance(geometry, dict) or "type" not in geometry:
                        messages.append(
                            Message(
                                level=MessageLevel.ERROR,
                                message=(
                                    f"{self.filename} should have a valid geometry or be global"
                                ),
                            )
                        )
                    elif geometry["type"] not in {"Polygon", "MultiPolygon"}:
                        messages.append(
                            Message(
                                level=MessageLevel.ERROR,
                                message=(
                                    f"{self.filename} Geometry should be a Polygon or MultiPolygon"
                                ),
                            )
                        )
                    if "country_code" not in source["properties"]:
                        messages.append(
                            Message(
                                level=MessageLevel.ERROR,
                                message=f"{self.filename} should have a country_code or be global",
                            )
                        )
                elif "geometry" not in source:
                    messages.append(
                        Message(
                            level=MessageLevel.ERROR,
                            message=f"{self.filename} should have null geometry",
                        )
                    )
                elif source["geometry"] is not None:
                    messages.append(
                        Message(
                            level=MessageLevel.ERROR,
                            message=(
                                f"{self.filename} should have null geometry but it is "
                                f"{source['geometry']}"
                            ),
                        )
                    )
                if "user-agent" in source["properties"]["url"].lower():
                    messages.append(
                        Message(
                            level=MessageLevel.ERROR,
                            message=(
                                f"{self.filename} URL should not encode HTTP headers: "
                                f"{source['properties']['url']}"
                            ),
                        )
                    )
                if source["properties"]["type"] == "tms":
                    self.check_tms(source, messages)
                elif source["properties"]["type"] == "wms":
                    self.check_wms(source, messages)
                elif source["properties"]["type"] == "wms_endpoint":
                    self.check_wms_endpoint(source, messages)
                elif source["properties"]["type"] == "wmts":
                    self.check_wmts(source, messages)
                else:
                    messages.append(
                        Message(
                            level=MessageLevel.WARNING,
                            message=(
                                f"{self.filename}"
                                ": Imagery type "
                                f"{source['properties']['type']}"
                                " is currently not checked."
                            ),
                        )
                    )
                for msg in [msg for msg in messages if msg.level == MessageLevel.INFO]:
                    self.logger.info(msg.message)
                for msg in [msg for msg in messages if msg.level == MessageLevel.WARNING]:
                    self.logger.warning(msg.message)
                for msg in [msg for msg in messages if msg.level == MessageLevel.ERROR]:
                    self.logger.error(msg.message)
                if len([msg for msg in messages if msg.level == MessageLevel.ERROR]) > 0:
                    raise ValidationError("Errors occurred, see logs above.")
                self.logger.info("Finished processing %s", self.filename)
            except ValidationError:
                failed = True
            # Report unexpected checker failures per source and continue validating the remaining
            # sources.
            # pylint: disable-next=broad-exception-caught
            except Exception as e:
                failed = True
                self.logger.exception("Failed: %s", e)
        if spacesave > 0:
            self.logger.warning(
                "Disembedding all icons would save %s KB", round(spacesave / 1024.0, 2)
            )
        if failed:
            return 1
        return 0
