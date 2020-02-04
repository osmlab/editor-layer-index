#!/usr/bin/env python

import json
import io
from argparse import ArgumentParser
import colorlog
from base64 import b64decode

parser = ArgumentParser(description='Checks ELI sourcen for validity and common errors')
parser.add_argument('path', nargs='+', help='Path of files to check.')
parser.add_argument("-v", "--verbose", dest="verbose_count",
                    action="count", default=0,
                    help="increases log verbosity for each occurence.")
arguments = parser.parse_args()
logger = colorlog.getLogger()
# Start off at Error, reduce by one level for each -v argument
logger.setLevel(max(4 - arguments.verbose_count, 0) * 10)
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter())
logger.addHandler(handler)

spacesave = 0

knownIcons = {}

for filename in arguments.path:
    with io.open(filename, 'r', encoding='utf-8') as f:
        source = json.load(f)
        if 'icon' in source['properties']:
            if source['properties']['icon'].startswith("data:image/png"):
                iconsize = len(source['properties']['icon'].encode('utf-8'))
                spacesave += iconsize
                logger.debug("{} icon will disembedded to save {} KB".format(filename, round(iconsize/1024.0, 2)))
                if source['properties']['icon'] in knownIcons:
                    iconpath = knownIcons[source['properties']['icon']]
                    logger.info("I already have a known icon for {} : I'll reuse {}".format(filename, iconpath))
                else:
                    iconpath = filename.replace('.geojson', '.png')
                    with open(iconpath, "wb") as ico:
                        ico.write(b64decode(source['properties']['icon'].split(",")[1]))
                    knownIcons[source['properties']['icon']] = iconpath
                source['properties']['icon'] = "https://osmlab.github.io/editor-layer-index/"+iconpath
                with io.open(filename, 'w', encoding='utf-8') as fw:
                    json.dump(source, fw, sort_keys=True, indent=4)
            else:
                logger.debug("{} contains a good icon, {}".format(filename, source['properties']['icon']))
if spacesave > 0:
    logger.warning("Disembedding all icons saved {} KB".format(round(spacesave/1024.0, 2)))
