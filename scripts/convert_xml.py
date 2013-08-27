import json, sys, string, util
import xml.etree.cElementTree as ET

root = ET.Element("imagery")

for file in sys.argv[1:]:
    source = json.load(open(file))
    entry = ET.SubElement(root, "entry")

    name = ET.SubElement(entry, "name")
    name.text = source['name']

    type = ET.SubElement(entry, "type")
    type.text = source['type']

    url = ET.SubElement(entry, "url")
    url.text = source['url']

    if 'available_projections' in source:
        projections = ET.SubElement(entry, "projections")
        for projection in source['available_projections']:
            code = ET.SubElement(projections, "code")
            code.text = projection

    if 'attribution' in source:
        attribution = source['attribution']

        if attribution.get('text'):
            text = ET.SubElement(entry, "attribution-text")
            if attribution.get('required'):
                text.set('mandatory', 'true')
            text.text = attribution['text']

        if attribution.get('url'):
            url = ET.SubElement(entry, "attribution-url")
            url.text = attribution['url']

    if source.get('default', False):
        default = ET.SubElement(entry, "default")
        default.text = 'true'

    if 'icon' in source:
        icon = ET.SubElement(entry, "icon")
        icon.text = source['icon']

    if 'extent' in source:
        extent = source['extent']

        if 'min_zoom' in extent:
            min_zoom = ET.SubElement(entry, "min-zoom")
            min_zoom.text = str(extent['min_zoom'])

        if 'max_zoom' in extent:
            max_zoom = ET.SubElement(entry, "max-zoom")
            max_zoom.text = str(extent['max_zoom'])

        if 'bbox' in extent or 'polygon' in extent:
            bounds = ET.SubElement(entry, "bounds")

            if 'bbox' in extent:
                bounds.set('min-lat', str(extent['bbox']['min_lat']))
                bounds.set('min-lon', str(extent['bbox']['min_lon']))
                bounds.set('max-lat', str(extent['bbox']['max_lat']))
                bounds.set('max-lon', str(extent['bbox']['max_lon']))

            if 'polygon' in extent:
                for ring in extent['polygon']:
                    shape = ET.SubElement(bounds, "shape")
                    for p in ring:
                        point = ET.SubElement(shape, "point")
                        point.set('lon', str(p[0]))
                        point.set('lat', str(p[1]))

util.indent(root)

tree = ET.ElementTree(root)
tree.write("imagery.xml")
