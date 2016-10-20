import json, sys, util
from xml.dom.minidom import parse

source_features = []
for file in sys.argv[1:]:
    with open(file, 'rb') as f:
        source_features.append(json.load(f))

collection = {
    "type": "FeatureCollection",
    "features": source_features
}

print json.dumps(
    collection,
    indent=4,
    separators=(',', ': ')
)
