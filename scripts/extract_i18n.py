"""Extracts imagery names for i18n"""
import io
import json
import sys

i18n_strings = dict()
for file in sys.argv[1:]:
    with io.open(file, 'r') as f:
        source = json.load(f)
        props = source['properties']
        if 'i18n' in props and props['i18n']:
            layer_id = props['id']
            if 'name' in props:
                i18n_strings[layer_id + '.name'] = props['name']
            if 'description' in props:
                i18n_strings[layer_id + '.description'] = props['description']
            if 'attribution' in props:
                attr = props['attribution']
                if 'text' in attr:
                    i18n_strings[layer_id + '.attribution.text'] = attr['text']

print(json.dumps(
    i18n_strings,
    indent=4,
    sort_keys=True,
    separators=(',', ': ')
))
