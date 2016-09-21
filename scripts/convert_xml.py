import json, sys, string, util
import xml.etree.cElementTree as ET

root = ET.Element("imagery")

sources = []
for file in sys.argv[1:]:
    with open(file, 'rb') as f:
        sources.append(json.load(f))

for source in sources:
    props = source['properties']
    entry = ET.SubElement(root, "entry")

    name = ET.SubElement(entry, "name")
    name.text = props['name']

    type = ET.SubElement(entry, "type")
    type.text = props['type']

    url = ET.SubElement(entry, "url")
    url.text = props['url']

    if props.get('best') == True:
        #entry.set('best', 'true')
        best = ET.SubElement(entry, "best")

    if 'available_projections' in props:
        projections = ET.SubElement(entry, "projections")
        for projection in props['available_projections']:
            code = ET.SubElement(projections, "code")
            code.text = projection

    if 'attribution' in props:
        attribution = props['attribution']

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

    if 'icon' in props:
        icon = ET.SubElement(entry, "icon")
        icon.text = props['icon']

    if 'country_code' in props:
        country_code = ET.SubElement(entry, "country-code")
        country_code.text = props['country_code']

    if 'min_zoom' in props:
        min_zoom = ET.SubElement(entry, "min-zoom")
        min_zoom.text = str(props['min_zoom'])

    if 'max_zoom' in props:
        max_zoom = ET.SubElement(entry, "max-zoom")
        max_zoom.text = str(props['max_zoom'])

    geometry = source.get('geometry')
    if geometry:
        bounds = ET.SubElement(entry, "bounds")

        for ring in geometry['coordinates']:
            shape = ET.SubElement(bounds, "shape")
            for p in ring:
                point = ET.SubElement(shape, "point")
                point.set('lon', str(round(p[0],6)))
                point.set('lat', str(round(p[1],6)))

util.indent(root)

tree = ET.ElementTree(root)
with open("imagery.xml", 'wb') as f:
    tree.write(f)
