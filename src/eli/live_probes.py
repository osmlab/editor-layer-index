"""Render actual imagery and validate image payloads, rather than just metadata."""

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import mercantile
import requests
from shapely.geometry import box, shape

from eli.common import JSON
from eli.image_validation import image_payload
from eli.known_failures import KnownFailures
from eli.libeli.eliutils import BoundingBox
from eli.libeli.wmshelper import get_bbox
from eli.strict_context import Message, MessageLevel, ValidationContext


def sample_bounds(source: JSON) -> list[BoundingBox]:
    """Choose up to three interior samples, including disjoint/irregular footprints."""
    geom = shape(source["geometry"]) if source.get("geometry") else box(-1, 48, 1, 50)
    west, south, east, north = geom.bounds
    samples = [geom.representative_point()]
    for left, right in ((west, (west + east) / 2), ((west + east) / 2, east)):
        part = geom.intersection(box(left, south, right, north))
        if not part.is_empty:
            point = part.representative_point()
            if not any(point.equals(old) for old in samples):
                samples.append(point)
    return [
        BoundingBox(
            max(-180, p.x - 0.002),
            min(180, p.x + 0.002),
            max(-90, p.y - 0.002),
            min(90, p.y + 0.002),
        )
        for p in samples
        if -90 < p.y < 90
    ]


def render_url(url: str, crs: str, bounds: BoundingBox) -> str:
    """Preserve layer/style/vendor parameters and honour WMS axis ordering."""
    params = {k.lower(): v for k, v in parse_qsl(urlsplit(url).query)}
    esri = "request" not in params
    bbox = get_bbox(crs, bounds, "1.1.1" if esri else params.get("version", "1.3.0"))
    projection = crs.split(":")[-1] if esri else crs
    return (
        url.replace("{bbox}", bbox)
        .replace("{proj}", projection)
        .replace("{wkid}", crs.split(":")[-1])
        .replace("{width}", "256")
        .replace("{height}", "256")
    )


class LiveProbes(ValidationContext):
    """Actual image probes shared by WMS, ArcGIS, icons, and TMS sampling."""

    known_failures: KnownFailures | None = None
    report_path: Path | None = None

    def probe_image(
        self, url: str, headers: dict[str, str], *, icon: bool = False
    ) -> tuple[bool, bool, int]:
        try:
            response = self.get_response(url, headers=headers, verify=False)
            if response.status_code != 200:
                return False, False, response.status_code
            valid, blank = image_payload(response.content, allow_svg=icon)
            return valid, blank, response.status_code
        except requests.RequestException:
            return False, False, -1

    def check_rendering(self, source: JSON, messages: list[Message]) -> None:
        """Probe configured CRSs plus 4326/3857, even when not advertised."""
        props = source["properties"]
        listed = set(props.get("available_projections", []))
        for crs in sorted(listed | {"EPSG:4326", "EPSG:3857"}):
            results = []
            failures: list[Message] = []
            for bounds in sample_bounds(source):
                if crs == "EPSG:3857" and (bounds.south < -85.0511 or bounds.north > 85.0511):
                    messages.append(
                        Message(MessageLevel.INFO, "3857 sample outside Mercator latitude range")
                    )
                    continue
                try:
                    url = render_url(props["url"], crs, bounds)
                    valid, blank, status = self.probe_image(url, self.get_http_headers(source))
                    results.append((valid, blank))
                    if not valid:
                        failures.append(
                            Message(
                                MessageLevel.ERROR if crs in listed else MessageLevel.INFO,
                                f"{crs} image probe failed: HTTP code: {status} {url}",
                                code="image-probe",
                                url=url,
                                status=status,
                            )
                        )
                except (ValueError, RuntimeError) as error:
                    messages.append(
                        Message(
                            MessageLevel.ERROR, f"Cannot construct {crs} image request: {error}"
                        )
                    )
            if any(valid for valid, _ in results):
                for failure in failures:
                    if failure.level == MessageLevel.ERROR:
                        failure.level = MessageLevel.WARNING
                        failure.message = "Partial coverage: " + failure.message
            messages.extend(failures)
            if any(valid for valid, _ in results):
                messages.append(
                    Message(MessageLevel.INFO, f"{crs}: actual image request succeeded")
                )
            if results and all(valid and blank for valid, blank in results):
                messages.append(
                    Message(
                        MessageLevel.WARNING, f"{crs}: all interior image samples are uniform/blank"
                    )
                )
            if crs not in listed and any(valid for valid, _ in results):
                messages.append(
                    Message(
                        MessageLevel.WARNING,
                        f"{crs} returns an image but is not listed in available_projections",
                    )
                )

    def check_icon(self, source: JSON, messages: list[Message]) -> None:
        url = source["properties"].get("icon", "")
        if not url.startswith(("https://", "http://")):
            return
        valid, _, status = self.probe_image(url, self.headers, icon=True)
        if not valid:
            messages.append(
                Message(
                    MessageLevel.ERROR,
                    f"Icon is not a usable image: HTTP code: {status} {url}",
                    code="icon",
                    url=url,
                    status=status,
                )
            )

    def recover_tile(self, source: JSON, zoom: int, parameters: dict[str, Any]) -> bool:
        """Try other interior locations before calling a whole zoom unavailable."""
        for bounds in sample_bounds(source)[1:]:
            tile = mercantile.tile(
                (bounds.west + bounds.east) / 2, (bounds.south + bounds.north) / 2, zoom
            )
            url = source["properties"]["url"].replace("{x}", str(tile.x))
            url = url.replace("{-y}", str(2**zoom - 1 - tile.y))
            url = url.replace("{!y}", str(2 ** (zoom - 1) - 1 - tile.y))
            url = url.replace("{y}", str(tile.y)).replace("{zoom}", str(zoom)).format(**parameters)
            if self.test_image(url, self.get_http_headers(source))[0]:
                return True
        return False

    def classify_diagnostics(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Report known failures visibly without hiding unrelated failures."""
        records = []
        for diagnostic in messages:
            known_reason = self.known_failures.classify(diagnostic) if self.known_failures else None
            records.append(
                {
                    "source": self.filename,
                    "level": diagnostic.level.name,
                    "message": diagnostic.message,
                    "known_failure": known_reason,
                    "code": diagnostic.code,
                    "url": diagnostic.url,
                    "status": diagnostic.status,
                }
            )
            if known_reason:
                diagnostic.level = MessageLevel.WARNING
                diagnostic.message = f"Known failure ({known_reason}): {diagnostic.message}"
        return records

    def write_report(self, records: list[dict[str, Any]], *, complete: bool = True) -> None:
        if self.report_path:
            self.report_path.parent.mkdir(parents=True, exist_ok=True)
            self.report_path.write_text(
                json.dumps(
                    {
                        "diagnostics": records,
                        "complete": complete,
                        "unused_known_failures": self.known_failures.unused_rules()
                        if self.known_failures
                        else [],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
