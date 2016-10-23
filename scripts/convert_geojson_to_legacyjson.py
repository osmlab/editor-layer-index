import json, sys

def convert_json_source(source):
    converted = {}
    extent_obj = {}

    geometry = source.get('geometry') or {}
    polygon_coords = geometry.get('coordinates') or []
    if polygon_coords:
        extent_obj['polygon'] = polygon_coords

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
    with open(file, 'rb') as f:
        features.append(convert_json_source(json.load(f)))

print json.dumps(
    features,
    indent=4,
    separators=(',', ': ')
)
