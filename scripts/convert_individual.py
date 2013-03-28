import json, sys, string, util
from xml.dom.minidom import parse

dom = parse(sys.argv[1])

imageries = dom.getElementsByTagName('entry')

def strfn(filename):
    valid_chars = "-_()%s%s" % (string.ascii_letters, string.digits)
    return ''.join(c for c in filename if c in valid_chars)

entries = []

for imagery in imageries:
    entry = {}

    entry['name'] = imagery.getElementsByTagName('name')[0].childNodes[0].nodeValue
    entry['type'] = imagery.getElementsByTagName('type')[0].childNodes[0].nodeValue
    entry['url']  = imagery.getElementsByTagName('url')[0].childNodes[0].nodeValue

    projs = util.getprojs(imagery)
    if projs: entry['available_projections'] = projs

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
        entry['extent'] = dict()

        if max_zoom:
            entry['extent']['max_zoom'] = max_zoom
        if min_zoom:
            entry['extent']['min_zoom'] = min_zoom
        if bbox:
            entry['extent']['bbox'] = bbox
        if rings:
            entry['extent']['polygon'] = rings

    open('%s/%s.json' % (sys.argv[2], strfn(entry['name'])), 'w+').write(json.dumps(entry, indent=4))
