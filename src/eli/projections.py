"""Projection-list policy shared by offline linting and live WMS maintenance.

Follow JOSM's SyncEditorLayerIndex.setupProj obsolete-code list. These are
catalogue recommendations, not permission to rewrite CRS tokens in requests.
"""

from collections.abc import Iterable
from urllib.parse import parse_qsl, urlsplit

OBSOLETE_PROJECTIONS = {
    "EPSG:3359": "EPSG:3404",
    "EPSG:3785": "EPSG:3857",
    "EPSG:31297": "EPSG:31287",
    "EPSG:31464": "EPSG:31468",
    "EPSG:54004": "EPSG:3857",
    "EPSG:102100": "EPSG:3857",
    "EPSG:102113": "EPSG:3857",
    "EPSG:900913": "EPSG:3857",
}


def unused_projections(codes: Iterable[str], url: str | None = None) -> set[str]:
    """Find JOSM-obsolete codes and redundant or pre-WMS-1.3 CRS:84.

    Also apply ELI's agreed policy: CRS:84 adds no useful choice when either
    EPSG:4326 or EPSG:3857 is available. Preserve a sole CRS:84 in WMS 1.3.
    """
    values = set(codes)
    unused = values.intersection(OBSOLETE_PROJECTIONS)
    if "CRS:84" in values:
        params = {k.lower(): v for k, v in parse_qsl(urlsplit(url).query)} if url else {}
        if values.intersection({"EPSG:4326", "EPSG:3857"}) or (
            url is not None and not params.get("version", "").startswith("1.3")
        ):
            unused.add("CRS:84")
    return unused


def useful_projections(codes: Iterable[str]) -> set[str]:
    """Filter a capabilities-derived list without inventing server support."""
    values = set(codes)
    return values - unused_projections(values)
