"""Shared filesystem, validation, and logging helpers."""

import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import colorlog
import requests
from jsonschema import Draft4Validator, ValidationError

type JSON = dict[str, Any]


def discover(paths: list[str], root: Path) -> list[Path]:
    """Expand directories once, with stable ordering and no shell globbing."""
    selected: set[Path] = set()
    for value in paths or ["sources"]:
        path = Path(value)
        path = path if path.is_absolute() else root / path
        if not path.exists():
            raise FileNotFoundError(path)
        if path.is_dir():
            selected.update(p for p in path.rglob("*.geojson") if p.is_file())
        elif path.suffix.lower() == ".geojson":
            selected.add(path)
        else:
            raise ValueError(f"Expected a GeoJSON file or directory: {path}")
    return sorted(
        selected,
        key=lambda p: p.relative_to(root).as_posix() if p.is_relative_to(root) else p.as_posix(),
    )


def reject_duplicates(pairs: list[tuple[str, Any]]) -> JSON:
    result: JSON = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"duplicate key: {key!r}")
        result[key] = value
    return result


def load_json(path: Path, *, rounded: bool = False) -> JSON:
    with path.open(encoding="utf-8") as stream:
        value: Any = json.load(
            stream,
            object_pairs_hook=reject_duplicates,
            parse_float=(lambda text: round(float(text), 5)) if rounded else float,
        )
    if not isinstance(value, dict):
        raise ValidationError(f"Expected a JSON object: {path}")
    return value


def schema_validator(root: Path) -> Draft4Validator:
    return Draft4Validator(load_json(root / "schema.json"))


def get_logger(verbosity: int = 0) -> logging.Logger:
    logging.getLogger("charset_normalizer").setLevel(logging.WARNING)
    logger = logging.getLogger("eli")
    logger.setLevel(max(4 - verbosity, 0) * 10)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(colorlog.ColoredFormatter())
        logger.addHandler(handler)
    logger.propagate = False
    return logger


def request_get(url: str, **kwargs: Any) -> requests.Response:
    """Retain each caller's TLS policy while bounding every synchronous request."""
    timeout = kwargs.pop("timeout", (5, 20))
    return requests.get(url, timeout=timeout, **kwargs)


SOURCE_METADATA_FIELDS = (
    "license_url",
    "id",
    "description",
    "country_code",
    "default",
    "best",
    "start_date",
    "end_date",
    "overlay",
    "available_projections",
    "attribution",
    "icon",
)


def canonical_request_url(url: str) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Compare query order without changing layer/style values or actual requests."""
    parts = urlsplit(url)
    return (
        parts._replace(query="", fragment="").geturl(),
        tuple(sorted(parse_qsl(parts.query, keep_blank_values=True))),
    )
