#!/usr/bin/env python
import json, sys, string, util, os
from xml.dom.minidom import parse
from collections import OrderedDict

if len(sys.argv) != 3:
    print("Usage: %s [JOSM XML file] [target directory]"  % __file__)
    print("Converts JOSM imagery XML file into individual source files for editor-layer-index.")
    print("Hint: the latest JOSM imagery XML file is at https://josm.openstreetmap.de/maps")
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
    properties['id'] = imagery.getElementsByTagName('id')[0].childNodes[0].nodeValue
    properties['name'] = imagery.getElementsByTagName('name')[0].childNodes[0].nodeValue
    properties['type'] = imagery.getElementsByTagName('type')[0].childNodes[0].nodeValue
    properties['url']  = imagery.getElementsByTagName('url')[0].childNodes[0].nodeValue

    date_node = imagery.getElementsByTagName('date')
    if date_node:
        date_values = date_node[0].childNodes[0].nodeValue.split(';')
        properties['start_date'] = date_values[0]
        if len(date_values) == 1:
            properties['end_date'] = date_values[0]
        elif len(date_values) == 2 and date_values[1] != '-':
            properties['end_date'] = date_values[1]

    if imagery.getAttribute('overlay') == "true":
        properties['overlay'] = True

    if imagery.getAttribute('eli-best') == "true":
        properties['best'] = True

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
        attribution_dict = dict()
        if attr_text:
            attribution_dict['text'] = attr_text
        if attr_url:
            attribution_dict['url'] = attr_url
        if attr_required:
            attribution_dict['required'] = attr_required
        properties['attribution'] = attribution_dict

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
        properties['max_zoom'] = int(max_zoom_node[0].childNodes[0].nodeValue)

    min_zoom_node = imagery.getElementsByTagName('min-zoom')
    if min_zoom_node:
        properties['min_zoom'] = int(min_zoom_node[0].childNodes[0].nodeValue)

    permission_ref_node = imagery.getElementsByTagName('permission-ref')
    if permission_ref_node:
        properties['license_url'] = permission_ref_node[0].childNodes[0].nodeValue

    description_node = imagery.getElementsByTagName('description')
    if description_node:
        properties['description'] = description_node[0].childNodes[0].nodeValue

    (bbox, rings) = util.getrings(imagery)

    if rings:
        entry['geometry'] = {}
        entry['geometry']['type'] = 'Polygon'
        entry['geometry']['coordinates'] = rings
    else:
        print("Entry {} doesn't have a geometry".format(properties['id']))

    if not os.path.exists(sys.argv[2]):
        os.makedirs(sys.argv[2])
    directory = os.path.join(sys.argv[2], properties['country_code'].lower()) if 'country_code' in properties else sys.argv[2]
    if not os.path.exists(directory):
        os.makedirs(directory)
    output = json.dumps(entry, ensure_ascii=False, separators=(',', ':'))
    if sys.version_info.major == 2:
        output = output.encode('utf8')
    open('%s/%s.geojson' % (directory, strfn(properties['name'])), 'w+').write(output)
