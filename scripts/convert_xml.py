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

            # Rounding to the nearest ~10cm
            if 'bbox' in extent:
                bounds.set('min-lat', str(round(extent['bbox']['min_lat'],6)))
                bounds.set('min-lon', str(round(extent['bbox']['min_lon'],6)))
                bounds.set('max-lat', str(round(extent['bbox']['max_lat'],6)))
                bounds.set('max-lon', str(round(extent['bbox']['max_lon'],6)))

            if 'polygon' in extent:
                for ring in extent['polygon']:
                    shape = ET.SubElement(bounds, "shape")
                    for p in ring:
                        point = ET.SubElement(shape, "point")
                        point.set('lon', str(round(p[0],6)))
                        point.set('lat', str(round(p[1],6)))

util.indent(root)

tree = ET.ElementTree(root)
tree.write("imagery.xml")
