#!/usr/bin/env python
import json
import sys
import io
from datetime import datetime

source_features = []
for file in sys.argv[1:]:
    with io.open(file, 'r') as f:
        # simplify all floats to 5 decimal points
        source_features.append(json.load(f, parse_float=lambda x: round(float(x), 5)))

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

output = json.dumps(collection, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
if sys.version_info.major == 2:
    output = output.encode('utf8')
print(output)
