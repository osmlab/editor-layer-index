import json, sys, util
from xml.dom.minidom import parse

dom = parse(sys.argv[1])

imageries = dom.getElementsByTagName('entry')

collection = {
    "type": "FeatureCollection",
    "features": []
}

for imagery in imageries:
    entry = {
        "type": "Feature",
        "properties": {}
    }

    entry['properties']['name'] = imagery.getElementsByTagName('name')[0].childNodes[0].nodeValue
    entry['properties']['type'] = imagery.getElementsByTagName('type')[0].childNodes[0].nodeValue
    entry['properties']['url']  = imagery.getElementsByTagName('url')[0].childNodes[0].nodeValue

    projs = util.getprojs(imagery)
    if projs: entry['properties']['available_projections'] = projs

    attr_text = None
    attr_required = None
    attr_url = None

    attr_text_node = imagery.getElementsByTagName('attribution-text')
    if attr_text_node:
        attr_text = attr_text_node[0].childNodes[0].nodeValue
        attr_required = bool(attr_text_node[0].getAttribute('mandatory'))

    attr_url_node = imagery.getElementsByTagName('attribution-url')
    if attr_url_node:
        attr_url = attr_url_node[0].childNodes[0].nodeValue

    if any((attr_text, attr_required, attr_url)):
        entry['properties']['attribution'] = dict(text=attr_text, url=attr_url, required=attr_required)

    default = None

    is_default_node = imagery.getElementsByTagName('default')
    if is_default_node:
        default = bool(is_default_node[0].childNodes[0].nodeValue)

    max_zoom = None
    min_zoom = None
    bbox = None
    rings = None

    max_zoom_node = imagery.getElementsByTagName('max-zoom')
    if max_zoom_node:
        max_zoom = max_zoom_node[0].childNodes[0].nodeValue

    min_zoom_node = imagery.getElementsByTagName('min-zoom')
    if min_zoom_node:
        min_zoom = min_zoom_node[0].childNodes[0].nodeValue

    bounds_node = imagery.getElementsByTagName('bounds')
    if bounds_node:
        shape_nodes = bounds_node[0].getElementsByTagName('shape')
        if not len(shape_nodes):
            min_lat = float(bounds_node[0].getAttribute('min-lat'))
            min_lon = float(bounds_node[0].getAttribute('min-lon'))
            max_lat = float(bounds_node[0].getAttribute('max-lat'))
            max_lon = float(bounds_node[0].getAttribute('max-lon'))
            entry['geometry'] = {
                    "type": "Polygon",
                    "coordinates": [[
                        [min_lon, min_lat],
                        [min_lon, max_lat],
                        [max_lon, max_lat],
                        [max_lon, min_lat],
                        [min_lon, min_lat]]]
                    }
        else:
            rings = []
            for shape_node in shape_nodes:
                ring = []

                point_nodes = shape_node.getElementsByTagName('point')
                for point in point_nodes:
                    lat = float(point.getAttribute('lat'))
                    lon = float(point.getAttribute('lon'))
                    ring.append((lon, lat))
                ring.append(ring[0])
                rings.append(ring)
            entry['geometry'] = {
                "type": "Polygon",
                "coordinates": rings
            }
        collection['features'].append(entry)

    # if any((max_zoom, min_zoom, bbox, rings)):
    #     entry['extent'] = dict()

    #     if max_zoom:
    #         entry['extent']['max_zoom'] = max_zoom
    #     if min_zoom:
    #         entry['extent']['min_zoom'] = min_zoom
    #     if bbox:
    #         entry['extent']['bbox'] = bbox
    #     if rings:
    #         entry['extent']['polygon'] = rings

print json.dumps(collection, indent=4)
