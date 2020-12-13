import argparse
import glob
import json
import os
import yaml


parser = argparse.ArgumentParser(description="Extracts imagery names for i18n")

parser.add_argument(
    "output_path",
    metavar="output_path",
    type=str,
    nargs="?",
    help="Path generated config file will be written to.",
)

parser.add_argument(
    "sources",
    metavar="sources",
    type=str,
    nargs="?",
    help="Relative path to sources directory",
)

arguments = parser.parse_args()

data = {}
for filename in glob.glob(
    os.path.join(arguments.sources, "**", "*.geojson"), recursive=True
):
    with open(filename, "r") as f:
        source = json.load(f)
        props = source["properties"]
        if "i18n" in props and props["i18n"]:
            layer_id = props["id"]
            data[layer_id] = {}
            if "name" in props:
                data[layer_id]["name"] = props["name"]
            if "description" in props:
                data[layer_id]["description"] = props["description"]
            if "attribution" in props:
                attr = props["attribution"]
                data[layer_id]["attribution"] = {}
                if "text" in attr:
                    data[layer_id]["attribution"]["text"] = attr["text"]

with open(arguments.output_path, "w") as f:
    f.write(
        yaml.safe_dump(
            {"en": {"imagery": data}},
            allow_unicode=True,
            default_flow_style=False,
            default_style="",
            width=99999,
        )
    )
