import json, sys, util
from xml.dom.minidom import parse

dom = parse(sys.argv[1])

imageries = dom.getElementsByTagName('entry')

for imagery in imageries:

    entry = {
        'name': util.textelem(imagery, 'name'),
        'type': util.textelem(imagery, 'type'),
        'url': util.textelem(imagery, 'url'),
        'overlay': util.textelem(imagery, 'overlay'),
        'description': util.textelem(imagery, 'description'),
        'icon': util.textelem(imagery, 'icon')
    }

    entry = dict(filter(lambda x: x[1], entry.items()))

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

    (bbox, rings) = util.getrings(imagery)

    if any((max_zoom, min_zoom, bbox, rings)):
        entry['extent'] = {}
        if max_zoom:
            entry['extent']['max_zoom'] = max_zoom
        if min_zoom:
            entry['extent']['min_zoom'] = min_zoom
        if bbox:
            entry['extent']['bbox'] = bbox
        if rings:
            entry['extent']['polygon'] = rings

    print json.dumps(entry, indent=4)
