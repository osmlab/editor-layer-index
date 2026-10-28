"""Convert legacy source dictionaries to GeoJSON features."""

from eli.common import JSON, SOURCE_METADATA_FIELDS


def convert(old_obj: JSON) -> JSON:
    new_obj: JSON = {"type": "Feature", "properties": {}, "geometry": None}
    for f in [
        "name",
        "type",
        "url",
        "min_zoom",
        "max_zoom",
        *SOURCE_METADATA_FIELDS,
    ]:
        thing = old_obj.get(f)
        if thing:
            new_obj["properties"][f] = thing
    extent = old_obj.get("extent")
    if extent:
        thing = extent.get("min_zoom")
        if thing:
            new_obj["properties"]["min_zoom"] = thing
        thing = extent.get("max_zoom")
        if thing:
            new_obj["properties"]["max_zoom"] = thing
        polygon = extent.get("polygon")
        if polygon:
            for ring in polygon:
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
            new_obj["geometry"] = {"type": "Polygon", "coordinates": polygon}
        bbox = extent.get("bbox")
        if bbox and (not polygon):
            new_obj["geometry"] = {
                "type": "Polygon",
                "coordinates": [
                    [
                        [bbox["min_lon"], bbox["min_lat"]],
                        [bbox["min_lon"], bbox["max_lat"]],
                        [bbox["max_lon"], bbox["max_lat"]],
                        [bbox["max_lon"], bbox["min_lat"]],
                        [bbox["min_lon"], bbox["min_lat"]],
                    ]
                ],
            }
    return new_obj
