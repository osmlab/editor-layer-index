import json, sys

entries = []

for file in sys.argv[1:]:
    with open(file, 'rb') as f:
        entries.append(json.load(f))

print json.dumps(
    entries,
    indent=4,
    separators=(',', ': ')
)
