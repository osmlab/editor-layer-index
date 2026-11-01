"""Import JOSM XML entries as individual source files."""

import json
import os
import string
from collections import OrderedDict
from typing import Any
from xml.dom.minidom import Node, parse

from eli import xmlutil as util


def value(node: Node) -> str:
    if node.nodeValue is None:
        raise ValueError("Missing XML text")
    return node.nodeValue


# Mirror optional JOSM fields while preserving source-property insertion order.
# pylint: disable-next=R0912,R0914,R0915
def run(xml: str, output: str) -> None:
    dom = parse(xml)

    imageries = dom.getElementsByTagName("entry")

    def strfn(filename: str) -> str:
        valid_chars = f"-_(){string.ascii_letters}{string.digits}"
        return "".join(c for c in filename if c in valid_chars)

    for imagery in imageries:
        entry: dict[str, Any] = OrderedDict()
        entry["type"] = "Feature"

        properties: dict[str, Any] = OrderedDict()
        entry["properties"] = properties
        properties["id"] = value(imagery.getElementsByTagName("id")[0].childNodes[0])
        properties["name"] = value(imagery.getElementsByTagName("name")[0].childNodes[0])
        properties["type"] = value(imagery.getElementsByTagName("type")[0].childNodes[0])
        properties["url"] = value(imagery.getElementsByTagName("url")[0].childNodes[0])

        date_node = imagery.getElementsByTagName("date")
        if date_node:
            date_values = value(date_node[0].childNodes[0]).split(";")
            properties["start_date"] = date_values[0]
            if len(date_values) == 1:
                properties["end_date"] = date_values[0]
            elif len(date_values) == 2 and date_values[1] != "-":
                properties["end_date"] = date_values[1]

        if imagery.getAttribute("overlay") == "true":
            properties["overlay"] = True

        if imagery.getAttribute("eli-best") == "true":
            properties["best"] = True

        country_code_node = imagery.getElementsByTagName("country-code")
        if country_code_node:
            properties["country_code"] = value(country_code_node[0].childNodes[0])

        projs = util.getprojs(imagery)
        if projs:
            properties["available_projections"] = projs

        attr_text = None
        attr_required = None
        attr_url = None

        attr_text_node = imagery.getElementsByTagName("attribution-text")
        if attr_text_node:
            attr_text = value(attr_text_node[0].childNodes[0])
            attr_required = bool(attr_text_node[0].getAttribute("mandatory"))

        attr_url_node = imagery.getElementsByTagName("attribution-url")
        if attr_url_node:
            attr_url = value(attr_url_node[0].childNodes[0])

        if any((attr_text, attr_required, attr_url)):
            attribution_dict: dict[str, Any] = {}
            if attr_text:
                attribution_dict["text"] = attr_text
            if attr_url:
                attribution_dict["url"] = attr_url
            if attr_required:
                attribution_dict["required"] = attr_required
            properties["attribution"] = attribution_dict

        default = None

        is_default_node = imagery.getElementsByTagName("default")
        if is_default_node:
            default = bool(value(is_default_node[0].childNodes[0]))

        if default is not None:
            properties["default"] = default

        icon = None

        icon_node = imagery.getElementsByTagName("icon")
        if icon_node:
            icon = value(icon_node[0].childNodes[0])

        if icon_node:
            properties["icon"] = icon

        max_zoom_node = imagery.getElementsByTagName("max-zoom")
        if max_zoom_node:
            properties["max_zoom"] = int(value(max_zoom_node[0].childNodes[0]))

        min_zoom_node = imagery.getElementsByTagName("min-zoom")
        if min_zoom_node:
            properties["min_zoom"] = int(value(min_zoom_node[0].childNodes[0]))

        permission_ref_node = imagery.getElementsByTagName("permission-ref")
        if permission_ref_node:
            properties["license_url"] = value(permission_ref_node[0].childNodes[0])

        description_node = imagery.getElementsByTagName("description")
        if description_node:
            properties["description"] = value(description_node[0].childNodes[0])

        rings = util.getrings(imagery)[1]

        if rings:
            entry["geometry"] = {}
            entry["geometry"]["type"] = "Polygon"
            entry["geometry"]["coordinates"] = rings
        else:
            print(f"Entry {properties['id']} doesn't have a geometry")

        if not os.path.exists(output):
            os.makedirs(output)
        directory = (
            os.path.join(output, properties["country_code"].lower())
            if "country_code" in properties
            else output
        )
        if not os.path.exists(directory):
            os.makedirs(directory)
        encoded = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
        with open(
            f"{directory}/{strfn(properties['name'])}.geojson", "w", encoding="utf-8"
        ) as target:
            target.write(encoded)
