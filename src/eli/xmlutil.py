"""JOSM XML DOM helpers used by the source importer."""

from xml.dom.minidom import Element


def textelem(element: Element, tag: str) -> str | None:
    matches = element.getElementsByTagName(tag)
    if matches and matches[0].childNodes:
        return matches[0].childNodes[0].nodeValue
    return None


def getprojs(element: Element) -> list[str] | None:
    nodes = element.getElementsByTagName("projections")
    if (
        nodes
        and isinstance(nodes[0].parentNode, Element)
        and nodes[0].parentNode.tagName != "mirror"
    ):
        result: list[str] = []
        for code in nodes[0].getElementsByTagName("code"):
            text = code.childNodes[0].nodeValue
            if text is not None:
                result.append(text)
        return result
    return None


def getrings(
    element: Element,
) -> tuple[dict[str, float] | None, list[list[tuple[float, float]]] | None]:
    nodes = element.getElementsByTagName("bounds")
    if not nodes:
        return None, None
    bounds = nodes[0]
    bbox = {
        "min_lat": float(bounds.getAttribute("min-lat")),
        "max_lat": float(bounds.getAttribute("max-lat")),
        "min_lon": float(bounds.getAttribute("min-lon")),
        "max_lon": float(bounds.getAttribute("max-lon")),
    }
    rings = [
        [
            (float(point.getAttribute("lon")), float(point.getAttribute("lat")))
            for point in ring.getElementsByTagName("point")
        ]
        for ring in bounds.getElementsByTagName("shape")
    ]
    return bbox, rings
