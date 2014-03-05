import json, sys

entries = []

for file in sys.argv[1:]:
    entry = json.load(open(file))
    if entry['type'] != 'wms':
       entries.append(json.load(open(file)))

print json.dumps(entries, indent=4)
