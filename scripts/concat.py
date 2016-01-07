import json, sys

entries = []

for file in sys.argv[1:]:
    entries.append(json.load(open(file, 'rb')))

print json.dumps(entries, indent=4)
