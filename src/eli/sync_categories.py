"""Copy source files updated with missing JOSM categories to a destination."""

import json
from pathlib import Path

from eli.common import discover, load_json, request_get
from eli.libeli.eliutils import parse_xml


def run(sources: str, output: str) -> None:
    directory = Path(sources).resolve()
    destination = Path(output).resolve()
    response = request_get("https://josm.openstreetmap.de/maps")
    response.raise_for_status()
    root = parse_xml(response.text)
    categories: dict[tuple[str, str], str] = {}
    for entry in root.findall(".//entry"):
        identifier = entry.findtext("id")
        country = entry.findtext("country-code")
        category = entry.findtext("category")
        if identifier is not None and country is not None and category is not None:
            categories[identifier, country] = category
    for path in discover([str(directory)], directory):
        source = load_json(path)
        props = source["properties"]
        category = categories.get((props["id"], props.get("country_code", "")))
        if category is None or props.get("category") is not None:
            continue
        props["category"] = category
        target = destination / path.relative_to(directory)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(source, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{path}: no ELI category, use JOSM category: {category}")
