#!/usr/bin/env python
import json
import sys
import io
from datetime import datetime

source_features = []
for file in sys.argv[1:]:
    with io.open(file, 'r') as f:
        # simplify all floats to 6 decimal points
        source_features.append(json.load(f, parse_float=lambda x: round(float(x), 6)))

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
