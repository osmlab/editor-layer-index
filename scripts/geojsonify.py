#!env python2
"""
This script was used to convert the old-style layer source file JSON to GeoJSON
files. It's kept around for posterity and is no longer used regularly.
"""
import json
import os

def convert(old_obj):
    new_obj = {
        "type": "Feature",
        "properties": {},
        "geometry": None,
    }

    for f in ['name', 'type', 'url', 'min_zoom', 'max_zoom', 'license_url', 'id',
            'description', 'country_code', 'default', 'best', 'start_date', 'end_date',
            'overlay', 'available_projections', 'attribution', 'icon']:
        thing = old_obj.get(f)
        if thing:
            new_obj['properties'][f] = thing

    extent = old_obj.get('extent')
    if extent:
        thing = extent.get('min_zoom')
        if thing:
            new_obj['properties']['min_zoom'] = thing
        thing = extent.get('max_zoom')
        if thing:
            new_obj['properties']['max_zoom'] = thing

        polygon = extent.get('polygon')
        if polygon:
            for ring in polygon:
                # Close the ring on the polygon
                if ring[0] != ring[-1]:
                    ring.append(ring[0])

            new_obj['geometry'] = {
                "type": "Polygon",
                "coordinates": polygon
            }

        bbox = extent.get('bbox')
        if bbox and not polygon:
            new_obj['geometry'] = {
                "type": "Polygon",
                "coordinates": [
                    [
                        [bbox['min_lon'], bbox['min_lat']],
                        [bbox['min_lon'], bbox['max_lat']],
                        [bbox['max_lon'], bbox['max_lat']],
                        [bbox['max_lon'], bbox['min_lat']],
                        [bbox['min_lon'], bbox['min_lat']],
                    ]
                ]
            }

    return new_obj

for root, dirs, files in os.walk("sources"):
    for file in files:
        fname = os.path.join(root, file)
        with open(fname, 'r') as f:
            old_obj = json.load(f)
        new_obj = convert(old_obj)
        with open(fname, 'w') as f:
            json.dump(new_obj, f, indent=4, separators=(',', ': '))
            f.write('\n')

