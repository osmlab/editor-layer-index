"""Typed diagnostic records and transport state shared by strict protocol checks."""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import magic
import requests
from requests.models import Response
from shapely.geometry import Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from eli.common import get_logger, request_get, schema_validator
from eli.image_validation import image_payload
from eli.libeli import eliutils


class MessageLevel(Enum):
    """Severity of a strict source-validation diagnostic."""

    INFO = 1
    WARNING = 2
    ERROR = 3


@dataclass
class Message:
    """One strict source-validation diagnostic."""

    level: MessageLevel
    message: str
    code: str = ""
    url: str = ""
    status: int | None = None


class ValidationContext:
    """Own the logger, schema, transport helpers, and current source of one check run."""

    def __init__(self, root: Path, verbosity: int = 2) -> None:
        self.filename = ""
        self._responses: dict[tuple[str, str], Response | requests.RequestException] = {}
        self.logger = get_logger(verbosity)
        self.validator = schema_validator(root)
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; MSIE 6.0; OpenStreetMap Editor Layer Index CI check)"
            )
        }

    def get_response(self, url: str, **kwargs: Any) -> Response:
        """Send one bounded HTTP request; expose a single transport seam for tests."""
        key = (url, json.dumps(kwargs, sort_keys=True))
        cached = self._responses.get(key)
        if isinstance(cached, requests.RequestException):
            raise cached
        if cached is not None:
            return cached
        try:
            response = request_get(url, **kwargs)
        except requests.RequestException as error:
            self._responses[key] = error
            raise
        self._responses[key] = response
        return response

    def log_messages(self, messages: list[Message]) -> None:
        """Attribute every provider diagnostic to its source exactly once."""
        for level, log in (
            (MessageLevel.INFO, self.logger.info),
            (MessageLevel.WARNING, self.logger.warning),
            (MessageLevel.ERROR, self.logger.error),
        ):
            for diagnostic in messages:
                if diagnostic.level == level:
                    text = diagnostic.message
                    log(text if text.startswith(self.filename) else f"{self.filename}: {text}")

    def get_http_headers(self, source: Any) -> dict[str, str]:
        """Extract http headers from source"""
        custom_headers: dict[str, str] = {}
        custom_headers.update(self.headers)
        if "custom-http-headers" in source["properties"]:
            key = source["properties"]["custom-http-headers"]["header-name"]
            value = source["properties"]["custom-http-headers"]["header-value"]
            custom_headers[key] = value
        return custom_headers

    def max_area_outside_bbox(
        self, geom: BaseGeometry, bbox: eliutils.BoundingBox | list[eliutils.BoundingBox]
    ) -> float:
        """Calculate the percentage of geometry outside the provided bounding boxes.

        Parameters
        ----------
        geom : Polygon | MultiPolygon
            The geometry to check
        bbox : eliutils.BoundingBox | List[eliutils.BoundingBox]
            The BoundingBox to check against

        Returns
        -------
        float
            The maximal percentage of the area of geom that is not within a provided BoundingBox
        """
        if isinstance(bbox, list):
            geoms: list[Polygon] = [
                box(minx=bb.west, miny=bb.south, maxx=bb.east, maxy=bb.north) for bb in bbox
            ]
            bbox_geom = unary_union(geoms)
        else:
            bbox_geom = box(minx=bbox.west, miny=bbox.south, maxx=bbox.east, maxy=bbox.north)
        geom_outside_bbox = geom.difference(bbox_geom)
        return float(geom_outside_bbox.area / geom.area * 100.0)

    def get_text_encoded(
        self, url: str, headers: dict[str, str] | None
    ) -> tuple[Response, str | None]:
        """Fetch url and encode content based on encoding defined in XML when possible

        Parameters
        ----------
        url : str
            The URL to fetch
        headers : Optional[Dict[str, str]]
            Optional HTTP headers

        Returns
        -------
        Tuple[Response, Optional[str]]
            The Respone and encoded content
        """
        r = self.get_response(url, headers=headers, verify=False)
        if not r.status_code == 200:
            return (r, None)
        encoding = eliutils.search_encoding(r.text)
        if encoding is not None:
            try:
                r.encoding = encoding
                return (r, r.text)
            except LookupError, UnicodeError:
                pass
        r.encoding = r.apparent_encoding
        return (r, r.text)

    def test_url(self, url: str, headers: dict[str, str] | None = None) -> tuple[bool, int]:
        """Check if URL returns HTTP code 200

        Parameters
        ----------
        url : str
            The URL to test
        headers : Optional[Dict[str, str]], optional
            Optional HTTP headers, by default None

        Returns
        -------
        bool, int
            True if URL returns HTTP code 200 and HTTP status code
        """
        try:
            r = self.get_response(url, headers=headers, verify=False)
            if r.status_code == 200:
                return (True, r.status_code)
            return (False, r.status_code)
        except requests.RequestException as e:
            self.logger.error(
                "%s: Could not retrieve url: %s: %s: %s",
                self.filename,
                url,
                type(e).__name__,
                str(e).replace(url, "[request URL]"),
            )
        return (False, -1)

    def test_image(
        self, url: str, headers: dict[str, str] | None = None
    ) -> tuple[bool, int, str | None]:
        """Check if URL returns an image

        Parameters
        ----------
        url : str
            The URL to test
        headers : Optional[Dict[str, str]], optional
            Optional HTTP headers, by default None

        Returns
        -------
        bool, int
            True if URL returns an image  and HTTP status code
        """
        try:
            r = self.get_response(url, headers=headers, verify=False)
            if not r.status_code == 200:
                return (False, r.status_code, None)
            filetype: str = magic.from_buffer(r.content, mime=True)
            valid, _ = image_payload(r.content)
            return (
                valid and filetype in {"image/png", "image/jpeg", "image/webp"},
                r.status_code,
                filetype,
            )
        except (requests.RequestException, magic.MagicException) as e:
            self.logger.error(
                "%s: Could not retrieve url: %s: %s: %s",
                self.filename,
                url,
                type(e).__name__,
                str(e).replace(url, "[request URL]"),
            )
        return (False, -1, None)
