"""Extract embedded PNG icons and update their source URLs."""

import json
from base64 import b64decode

from eli.common import get_logger


def run(paths: list[str], verbosity: int = 0) -> None:
    logger = get_logger(verbosity)
    spacesave = 0

    known_icons: dict[str, str] = {}

    for filename in paths:
        with open(filename, encoding="utf-8") as f:
            source = json.load(f)
            if "icon" in source["properties"]:
                if source["properties"]["icon"].startswith("data:image/png"):
                    iconsize = len(source["properties"]["icon"].encode("utf-8"))
                    spacesave += iconsize
                    logger.debug(
                        "%s icon will disembedded to save %s KB",
                        filename,
                        round(iconsize / 1024.0, 2),
                    )
                    if source["properties"]["icon"] in known_icons:
                        iconpath = known_icons[source["properties"]["icon"]]
                        logger.info(
                            "I already have a known icon for %s : I'll reuse %s", filename, iconpath
                        )
                    else:
                        iconpath = filename.replace(".geojson", ".png")
                        with open(iconpath, "wb") as ico:
                            ico.write(b64decode(source["properties"]["icon"].split(",")[1]))
                        known_icons[source["properties"]["icon"]] = iconpath
                    source["properties"]["icon"] = (
                        "https://osmlab.github.io/editor-layer-index/" + iconpath
                    )
                    with open(filename, "w", encoding="utf-8") as fw:
                        json.dump(source, fw, sort_keys=True, indent=4)
                else:
                    logger.debug(
                        "%s contains a good icon, %s", filename, source["properties"]["icon"]
                    )
    if spacesave > 0:
        logger.warning("Disembedding all icons saved %s KB", round(spacesave / 1024.0, 2))
