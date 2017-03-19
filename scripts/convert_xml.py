import json, sys, string, util, io
import xml.etree.cElementTree as ET

root = ET.Element("imagery")

sources = []
for file in sys.argv[1:]:
    with io.open(file, 'r') as f:
        sources.append(json.load(f))


def add_source(source):
    props = source['properties']
    entry = ET.SubElement(root, "entry")

    name = ET.SubElement(entry, "name")
    name.text = props['name']

    name = ET.SubElement(entry, "id")
    name.text = props['id']

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

    if 'description' in props:
        description = ET.SubElement(entry, "description")
        description.text = props['description']

    if 'min_zoom' in props:
        min_zoom = ET.SubElement(entry, "min-zoom")
        min_zoom.text = str(props['min_zoom'])

    if 'max_zoom' in props:
        max_zoom = ET.SubElement(entry, "max-zoom")
        max_zoom.text = str(props['max_zoom'])

    geometry = source.get('geometry')
    if geometry:
        def coord_str(coord):
            return "{0:.6f}".format(coord)
        bounds = ET.SubElement(entry, "bounds")
        lons = [p[0] for ring in geometry['coordinates'] for p in ring]
        lats = [p[1] for ring in geometry['coordinates'] for p in ring]
        bounds.set('min-lon', coord_str(min(lons)))
        bounds.set('min-lat', coord_str(min(lats)))
        bounds.set('max-lon', coord_str(max(lons)))
        bounds.set('max-lat', coord_str(max(lats)))

        for ring in geometry['coordinates']:
            shape = ET.SubElement(bounds, "shape")
            for p in ring:
                point = ET.SubElement(shape, "point")
                point.set('lon', coord_str(p[0]))
                point.set('lat', coord_str(p[1]))

for source in sources:
    try:
        add_source(source)
    except StandardError:
        print('Failed to convert %s' % source)
        pass

util.indent(root)

tree = ET.ElementTree(root)
with io.open("imagery.xml", mode='wb') as f:
    tree.write(f, encoding='utf-8', xml_declaration=True)
