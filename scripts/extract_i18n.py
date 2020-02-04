#!/usr/bin/env python
"""Extracts imagery names for i18n"""
import io
import json
import yaml
import sys

data = {}
for file in sys.argv[1:]:
    with io.open(file, 'r') as f:
        source = json.load(f)
        props = source['properties']
        if 'i18n' in props and props['i18n']:
            layer_id = props['id']
            data[layer_id] = {}
            if 'name' in props:
                data[layer_id]['name'] = props['name']
            if 'description' in props:
                data[layer_id]['description'] = props['description']
            if 'attribution' in props:
                attr = props['attribution']
                data[layer_id]['attribution'] = {}
                if 'text' in attr:
                    data[layer_id]['attribution']['text'] = attr['text']

print(yaml.safe_dump(
    {'en': { 'imagery': data }},
    allow_unicode=True,
    default_flow_style=False,
    default_style='',

    width=99999
))
