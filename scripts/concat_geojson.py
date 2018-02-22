#!/usr/bin/env python
import json
import sys
import util
import io
from datetime import datetime
from xml.dom.minidom import parse

source_features = []
for file in sys.argv[1:]:
    with io.open(file, 'r') as f:
        source_features.append(json.load(f))

generated = '{:%Y-%m-%d %H:%M:%S}'.format(datetime.utcnow())
version = "1.0"

collection = {
    "type": "FeatureCollection",
    "meta": {
        "generated": generated,
        "format_version": version
    },
    "features": source_features
}

print(json.dumps(collection, sort_keys=True, separators=(',', ':')
                 ))
