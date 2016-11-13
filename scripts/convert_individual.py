#!env python2
import json, sys, string, util, os
from xml.dom.minidom import parse
from collections import OrderedDict

if len(sys.argv) != 3:
    print("Usage: %s [JOSM XML file] [target directory]"  % __file__)
    print("Converts JOSM imagery XML file into individual source files for editor-layer-index.")
    exit(1)

dom = parse(sys.argv[1])

imageries = dom.getElementsByTagName('entry')

def strfn(filename):
    valid_chars = "-_()%s%s" % (string.ascii_letters, string.digits)
    return ''.join(c for c in filename if c in valid_chars)

entries = []

for imagery in imageries:
    entry = OrderedDict()
    entry['type'] = 'Feature'

    properties = entry['properties'] = OrderedDict()
    id_node = imagery.getElementsByTagName('id')
    if id_node:
        properties['id'] = id_node[0].childNodes[0].nodeValue
    properties['name'] = imagery.getElementsByTagName('name')[0].childNodes[0].nodeValue
    properties['type'] = imagery.getElementsByTagName('type')[0].childNodes[0].nodeValue
    properties['url']  = imagery.getElementsByTagName('url')[0].childNodes[0].nodeValue


    country_code_node = imagery.getElementsByTagName('country-code')
    if country_code_node:
        properties['country_code'] = country_code_node[0].childNodes[0].nodeValue

    projs = util.getprojs(imagery)
    if projs: properties['available_projections'] = projs

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
        properties['attribution'] = dict(text=attr_text, url=attr_url, required=attr_required)

    default = None

    is_default_node = imagery.getElementsByTagName('default')
    if is_default_node:
        default = bool(is_default_node[0].childNodes[0].nodeValue)

    if default is not None:
        properties['default'] = default

    icon = None

    icon_node = imagery.getElementsByTagName('icon')
    if icon_node:
        icon = icon_node[0].childNodes[0].nodeValue

    if icon_node:
        properties['icon'] = icon

    max_zoom_node = imagery.getElementsByTagName('max-zoom')
    if max_zoom_node:
        properties['max_zoom'] = max_zoom_node[0].childNodes[0].nodeValue

    min_zoom_node = imagery.getElementsByTagName('min-zoom')
    if min_zoom_node:
        properties['min_zoom'] = min_zoom_node[0].childNodes[0].nodeValue

    (bbox, rings) = util.getrings(imagery)

    if rings:
        entry['geometry'] = {}
        entry['geometry']['type'] = 'Polygon'
        entry['geometry']['coordinates'] = rings

    dir = os.path.join(sys.argv[2], properties['country_code']) if 'country_code' in properties else sys.argv[2]
    try:
        os.mkdir(dir)
    except OSError:
        pass
    open('%s/%s.geojson' % (dir, strfn(properties['name'])), 'w+').write(json.dumps(entry, indent=4))
