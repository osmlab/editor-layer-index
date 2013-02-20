import json
from xml.dom.minidom import parse

dom = parse('josm-imagery.xml')

imageries = dom.getElementsByTagName('entry')

for imagery in imageries:
    entry = {}

    entry['name'] = imagery.getElementsByTagName('name')[0].childNodes[0].nodeValue
    entry['type'] = imagery.getElementsByTagName('type')[0].childNodes[0].nodeValue
    entry['url']  = imagery.getElementsByTagName('url')[0].childNodes[0].nodeValue

    projs_node = imagery.getElementsByTagName('projections')
    if projs_node:
        entry['available_projections'] = []
        for proj_node in projs_node[0].getElementsByTagName('code'):
            code = proj_node.childNodes[0].nodeValue
            entry['available_projections'].append(code)

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
        entry['attribution'] = dict(text=attr_text, url=attr_url, required=attr_required)

    default = None

    is_default_node = imagery.getElementsByTagName('default')
    if is_default_node:
        default = bool(is_default_node[0].childNodes[0].nodeValue)

    if default is not None:
        entry['default'] = default

    icon = None

    icon_node = imagery.getElementsByTagName('icon')
    if icon_node:
        icon = icon_node[0].childNodes[0].nodeValue

    if icon_node:
        entry['icon'] = icon

    max_zoom = None
    min_zoom = None

    max_zoom_node = imagery.getElementsByTagName('max-zoom')
    if max_zoom_node:
        max_zoom = max_zoom_node[0].childNodes[0].nodeValue

    min_zoom_node = imagery.getElementsByTagName('min-zoom')
    if min_zoom_node:
        min_zoom = min_zoom_node[0].childNodes[0].nodeValue

    bounds_node = imagery.getElementsByTagName('bounds')
    if bounds_node:
        min_lat = bounds_node[0].getAttribute('min-lat')
        min_lon = bounds_node[0].getAttribute('min-lon')
        max_lat = bounds_node[0].getAttribute('max-lat')
        max_lon = bounds_node[0].getAttribute('max-lon')

        shape_nodes = bounds_node.getElementsByTagName('shape')
        for shape_node in shape_nodes:


    if any((max_zoom, min_zoom)):
        entry['extent'] = dict(max_zoom=max_zoom, min_zoom=min_zoom)

    print json.dumps(entry)