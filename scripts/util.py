def getprojs(elem):
    o = []
    projs_node = elem.getElementsByTagName('projections')
    if projs_node:
        o = []
        for proj_node in projs_node[0].getElementsByTagName('code'):
            code = proj_node.childNodes[0].nodeValue
            o.append(code)
        return o

def textelem(elem, y):
    e = elem.getElementsByTagName(y)
    if e: return e[0].childNodes[0].nodeValue
    else: return None

def getrings(elem):
    bounds_node = elem.getElementsByTagName('bounds')
    if bounds_node:
        min_lat = float(bounds_node[0].getAttribute('min-lat'))
        min_lon = float(bounds_node[0].getAttribute('min-lon'))
        max_lat = float(bounds_node[0].getAttribute('max-lat'))
        max_lon = float(bounds_node[0].getAttribute('max-lon'))
        bbox = dict(min_lat=min_lat, min_lon=min_lon, max_lat=max_lat, max_lon=max_lon)
        rings = []
        shape_nodes = bounds_node[0].getElementsByTagName('shape')
        for shape_node in shape_nodes:
            ring = []
            point_nodes = shape_node.getElementsByTagName('point')
            for point in point_nodes:
                lat = float(point.getAttribute('lat'))
                lon = float(point.getAttribute('lon'))
                ring.append((lon, lat))
            rings.append(ring)
        return bbox, rings
    return None, None

def indent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i
