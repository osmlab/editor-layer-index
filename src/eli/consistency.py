"""Deterministic checks for contradictory source metadata and recommendations."""

import calendar
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pycountry
from pyproj import Geod
from shapely import STRtree, orient_polygons
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from eli.common import JSON

GEOD = Geod(ellps="WGS84")
COUNTRY_DIRECTORY_EXCEPTIONS = {"PR": {"US"}}
MIN_OVERLAP_FRACTION = 0.10
MIN_OVERLAP_KM2 = 1.0


def date_bounds(value: str) -> tuple[date, date]:
    """Interpret partial dates as inclusive intervals, validating the calendar."""
    parts = [int(part) for part in value.split("-")]
    year = parts[0]
    month = parts[1] if len(parts) > 1 else 1
    day = parts[2] if len(parts) > 2 else 1
    first = date(year, month, day)
    last_month = month if len(parts) > 1 else 12
    last_day = day if len(parts) > 2 else calendar.monthrange(year, last_month)[1]
    return first, date(year, last_month, last_day)


def metadata_errors(source: JSON, path: Path, root: Path) -> list[str]:
    """Find facts that cannot simultaneously be true; never guess replacements."""
    props = source["properties"]
    errors = []
    if "category" not in props:
        errors.append("Missing category")
    dates = {}
    for key in ("start_date", "end_date"):
        if key in props:
            try:
                dates[key] = date_bounds(props[key])
            except ValueError:
                errors.append(f"{key} is not a real calendar date: {props[key]}")
    if "start_date" in dates and "end_date" in dates:
        if dates["start_date"][0] > dates["end_date"][1]:
            errors.append("start_date is after end_date")
    # The tile consumer defaults to zooms 0..20; other service types have no
    # implicit upper zoom, so only compare explicitly supplied bounds there.
    maximum = props.get("max_zoom", 20 if props["type"] == "tms" else None)
    if maximum is not None and props.get("min_zoom", 0) > maximum:
        errors.append("min_zoom is greater than max_zoom")
    relative = path.relative_to(root) if path.is_relative_to(root) else path
    parts = relative.parts
    if len(parts) >= 4 and parts[0] == "sources":
        country = parts[2].upper()
        if pycountry.countries.get(alpha_2=country) is not None:
            declared = props.get("country_code")
            if declared not in {country, "ZZ", "XN"} | COUNTRY_DIRECTORY_EXCEPTIONS.get(
                country, set()
            ):
                errors.append(f"country_code {declared} disagrees with directory {parts[2]}")
    if props["type"] == "wms":
        errors.extend(wms_errors(props))
    return errors


# WMS and ArcGIS have different required parameters and CRS encodings.
# pylint: disable-next=too-many-branches
def wms_errors(props: JSON) -> list[str]:
    """Check standard WMS and ArcGIS export queries, preserving vendor options."""
    url = urlsplit(props["url"])
    params: dict[str, list[str]] = {}
    for key, value in parse_qsl(url.query, keep_blank_values=True):
        params.setdefault(key.lower(), []).append(value)
    errors = []
    arcgis = "bboxsr" in params or "imagesr" in params
    required = (
        {"bbox", "bboxsr", "imagesr", "size"}
        if arcgis
        else {"service", "request", "version", "format", "width", "height", "bbox"}
    )
    missing = required - params.keys()
    if not arcgis and not params.keys() & {"crs", "srs"}:
        missing.add("crs/srs")
    if missing:
        errors.append("Missing WMS query parameters: " + ", ".join(sorted(missing)))
    if arcgis and not url.path.lower().endswith(("/export", "/exportimage")):
        errors.append("ArcGIS image URL must use /export or /exportImage, not service metadata")
    for key, values in params.items():
        if (
            key in required | {"crs", "srs", "styles", "layers", "format", "f"}
            and len(set(values)) > 1
        ):
            errors.append(f"Conflicting values for WMS query parameter {key}")
    for key in ("bboxsr", "imagesr") if arcgis else ("crs", "srs"):
        for value in params.get(key, []):
            if "{proj}" in value or "{wkid}" in value:
                continue
            fixed = value.upper()
            if re.fullmatch(r"\d+", fixed):
                fixed = "EPSG:" + fixed
            if set(props.get("available_projections", [])) - {fixed}:
                errors.append(f"{key} fixes the CRS to {value} despite other available_projections")
    if not arcgis:
        for key, expected in (("service", "wms"), ("request", "getmap")):
            if key in params and any(v.lower() != expected for v in params[key]):
                errors.append(f"WMS {key} must be {expected}")
    return errors


def area_km2(geometry: BaseGeometry) -> float:
    """Measure polygon area on WGS84, independently of ring winding."""
    return abs(GEOD.geometry_area_perimeter(orient_polygons(geometry))[0]) / 1_000_000


def best_overlaps(sources: list[JSON]) -> list[tuple[str, str, float, float]]:
    """Find significant overlaps of best footprints (ratio of the smaller area).

    Global recommendations have no footprint to compare. Only finite regional
    geometries participate; touching borders and small slivers do not conflict.
    """
    selected = sorted(
        (s for s in sources if s["properties"].get("best") and s.get("geometry")),
        key=lambda s: s["properties"]["id"],
    )
    geometries = [shape(s["geometry"]) for s in selected]
    areas = [area_km2(g) for g in geometries]
    tree = STRtree(geometries)
    overlaps = []
    for i, geometry in enumerate(geometries):
        for index in sorted(tree.query(geometry, predicate="intersects")):
            j = int(index)
            if j <= i:
                continue
            intersection = geometry.intersection(geometries[j])
            if intersection.area == 0:
                continue
            area = area_km2(intersection)
            smaller = min(areas[i], areas[j])
            fraction = area / smaller if smaller else 0
            if area >= MIN_OVERLAP_KM2 and fraction >= MIN_OVERLAP_FRACTION:
                overlaps.append(
                    (
                        selected[i]["properties"]["id"],
                        selected[j]["properties"]["id"],
                        area,
                        fraction,
                    )
                )
    return overlaps


def source_fingerprint(source: JSON) -> str:
    """Bind a legacy exception to exact source content, never just an ID or URL."""
    payload = json.dumps(source, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def baseline_allows(baseline: JSON, message: str, sources: list[JSON]) -> bool:
    """A changed source must resolve its existing contradictions to pass."""
    expected = {s["properties"]["id"]: source_fingerprint(s) for s in sources}
    return bool(baseline.get("failures", {}).get(message) == expected)
