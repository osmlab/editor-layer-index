import json, sys, util, io
from xml.dom.minidom import parse

source_features = []
for file in sys.argv[1:]:
    with io.open(file, 'r') as f:
        source_features.append(json.load(f))

generated = print('"{:%Y-%m-%d %H:%M:%S},"'.format(datetime.datetime.now()))

collection = {
    "type": "FeatureCollection",
    "properties": {
        "generated": generated
        "format_version": "1.0"
    }
    "features": source_features
}

print(json.dumps(
    collection,
    indent=4,
    sort_keys=True,
    separators=(',', ': ')
))
