import json, sys, io

def convert_json_source(source):
    converted = {}
    extent_obj = {}

    geometry = source.get('geometry') or {}
    polygon_coords = geometry.get('coordinates') or []
    if polygon_coords:
        extent_obj['polygon'] = polygon_coords
        # generate bbox from polygon coordinates as a stop gap         
        min_lon = 180
        max_lon = -180
        min_lat = 90
        max_lat = -90
        for ring in polygon_coords:
            for coord in ring:
                if coord[0] < min_lon:
                    min_lon = coord[0]
                if coord[0] > max_lon:
                    max_lon = coord[0]
                if coord[1] < min_lat:
                    min_lat = coord[1]
                if coord[1] > max_lat:
                    max_lat = coord[1]
        bbox_obj = {}
        bbox_obj['min_lon'] = min_lon
        bbox_obj['max_lon'] = max_lon
        bbox_obj['min_lat'] = min_lat
        bbox_obj['max_lat'] = max_lat
        extent_obj['bbox'] = bbox_obj

    properties = source.get('properties') or {}
    for f in ['name', 'type', 'url', 'license_url', 'id', 'description',
            'country_code', 'default', 'best', 'start_date', 'end_date',
            'overlay', 'available_projections', 'attribution', 'icon']:
        thing = properties.get(f)
        if thing is not None:
            converted[f] = thing

    for f in ['min_zoom', 'max_zoom']:
        thing = properties.get(f)
        if thing is not None:
            extent_obj[f] = thing

    if extent_obj:
        converted['extent'] = extent_obj

    return converted

features = []
for file in sys.argv[1:]:
    with io.open(file, 'r') as f:
        features.append(convert_json_source(json.load(f)))

print(json.dumps(
    features,
    indent=4,
    sort_keys=True,
    separators=(',', ': ')
))
