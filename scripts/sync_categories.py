import glob
import io
import json
import os
import xml.etree.ElementTree as ET
import requests

eli_path = r"sources"
out_path = r"/tmp/osm"

if not os.path.exists(out_path):
    os.mkdir(out_path)

# Get latest JOSM data
r = requests.get("https://josm.openstreetmap.de/maps")
xml = r.text

# From https://stackoverflow.com/questions/13412496/python-elementtree-module-how-to-ignore-the-namespace-of-xml-files-to-locate-ma
try:
    it = ET.iterparse(io.StringIO(xml))
    for _, el in it:
        _, _, el.tag = el.tag.rpartition('}')
    root = it.root
except:
    raise RuntimeError("Could not parse XML.")

# Parse all JOSM entries and find categories
josm_categories = {}
for entry in root.findall(".//entry"):

    id_el = entry.find("./id")
    if id_el is None:
        continue
    id = id_el.text

    country_code_el = entry.find("./country-code")
    if country_code_el is None:
        continue
    country_code = country_code_el.text

    category_el = entry.find("./category")
    if category_el is None:
        continue
    category = category_el.text

    josm_categories[(id, country_code)] = category

# Iterate over all ELI entries. If and ELI id matches with a JSOM id, and not category in ELI is set, use the JOSM id
for filename in glob.glob(os.path.join(eli_path, '**', '*.geojson'), recursive=True):
    path_split = filename.split(os.sep)
    sources_index = path_split.index("sources")

    path = path_split[sources_index + 1:]
    with open(filename, mode='r') as f:
        source = json.load(io.open(filename, encoding='utf-8'))
        if 'country_code' in source['properties']:
            country_code = source['properties']['country_code']
            source_id = source['properties']['id']
            if 'category' in source['properties']:
                category = source['properties']['category']
            else:
                category = None

            key = (source_id, country_code)

            if key in josm_categories:
                josm_category = josm_categories[key]

                if josm_category == category:
                    print("{}: Same category: {}".format(filename, category))
                    continue
                elif category is not None and not josm_category == category:
                    print("{}: Different category: ELI: {}, JOSM: {}. Do nothing.".format(filename, category, josm_category))
                    continue
                else:
                    print("{}: No ELI category, use JOSM category: {}".format(filename, josm_category))
                    source['properties']['category'] = josm_category

                    out_dir = os.path.join(out_path, *path[:-1])
                    if not os.path.exists(out_dir):
                        os.makedirs(out_dir)

                    out_file = os.path.join(out_path, *path)

                    with open(out_file, 'w', encoding='utf-8') as out:
                        json.dump(source, out, indent=4, sort_keys=False, ensure_ascii=False)
                        out.write("\n")


