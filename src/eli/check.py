"""Offline source validation."""

import warnings
from pathlib import Path

from jsonschema import ValidationError
from shapely.geometry import shape
from shapely.validation import explain_validity

from eli.common import canonical_request_url, get_logger, load_json, schema_validator
from eli.libeli.geometry import validate_polygon_coordinates
from eli.projections import unused_projections


# Independent schema, URL, and geometry checks accumulate diagnostics in one source pass.
# pylint: disable-next=R0912,R0914,R0915
def run(paths: list[Path], root: Path, verbosity: int = 0) -> int:
    logger = get_logger(max(verbosity, 1))
    validator = schema_validator(root)
    seen_ids: set[str] = set()
    seen_urls: dict[tuple[str, tuple[tuple[str, str], ...]], str] = {}
    failed = False
    spacesave = 0
    tested_sources_count = 0
    for path in paths:
        filename = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)

        if filename.lower()[-8:] != ".geojson":
            logger.debug("%s is not a geojson file, skip", filename)
            continue

        if not path.exists():
            logger.debug("%s does not exist, skip", filename)
            continue

        if ":" in filename:
            raise ValidationError(f'Filename contains invalid ":" character: {filename}')

        try:
            # dict_raise_on_duplicates raises error on duplicate keys in geojson
            source = load_json(path)

            # jsonschema validate
            validator.validate(source)

            if "properties" not in source:
                logger.exception("%s missing properties", filename)
                raise ValidationError(f"{filename} missing properties")

            sourceid = source["properties"]["id"]
            if sourceid in seen_ids:
                raise ValidationError(f"Id {sourceid} used multiple times")
            seen_ids.add(sourceid)

            request_url = canonical_request_url(source["properties"]["url"])
            if request_url in seen_urls:
                logger.warning("%s duplicates imagery URL of %s", filename, seen_urls[request_url])
            seen_urls[request_url] = filename
            if (
                source["properties"]["type"] not in {"wms", "wmts"}
                and "available_projections" in source["properties"]
            ):
                logger.warning(
                    "%s: available_projections only makes sense for selected WMS/WMTS layers",
                    filename,
                )

            # {z} instead of {zoom}
            if "{z}" in source["properties"]["url"]:
                raise ValidationError("{z} found instead of {zoom} in tile url")

            projections = source["properties"].get("available_projections", [])
            if len(projections) != len(set(projections)):
                raise ValidationError("available_projections contains duplicate codes")
            unused = unused_projections(projections, source["properties"]["url"])
            if unused:
                logger.warning(
                    "%s: projections not useful: %s", filename, ", ".join(sorted(unused))
                )
            policy = source["properties"].get("privacy_policy_url")
            if policy is True or (
                isinstance(policy, str) and policy.strip().lower() in {"none", "false", "null", ""}
            ):
                raise ValidationError("privacy_policy_url must be a URL or the boolean false")

            # Check for license url. Too many missing to mark as required in schema.
            if "license_url" not in source["properties"]:
                logger.debug("%s has no license_url", filename)

            if "attribution" not in source["properties"]:
                logger.debug("%s has no attribution", filename)

            # Check for big fat embedded icons
            if "icon" in source["properties"]:
                if source["properties"]["icon"].startswith("data:"):
                    iconsize = len(source["properties"]["icon"].encode("utf-8"))
                    spacesave += iconsize
                    warnings.warn(
                        (
                            f"{filename} icon should be disembedded to save "
                            f"{round(iconsize / 1024.0, 2)} KB"
                        )
                    )

            # Validate that url has the tokens we expect
            params = []

            # tms
            if source["properties"]["type"] == "tms":
                if "max_zoom" in source["properties"]:
                    if source["properties"]["max_zoom"] == 20:
                        logger.warning("Useless max_zoom parameter in %s", filename)
                if "available_projections" in source["properties"]:
                    warnings.warn(f"Senseless available_projections parameter in {filename}")
                if "min_zoom" in source["properties"]:
                    if source["properties"]["min_zoom"] == 0:
                        logger.warning("Useless min_zoom parameter in %s", filename)
                params = ["{zoom}", "{x}", "{y}"]

            # wms: {proj}, {bbox}, {width}, {height}
            elif source["properties"]["type"] == "wms":
                if "available_projections" not in source["properties"]:
                    raise ValidationError(f"Missing available_projections parameter in {filename}")
                params = ["{proj}", "{bbox}", "{width}", "{height}"]

            # wmts:
            if source["properties"]["type"] == "wmts":
                for tms_url_parameter in ["{zoom}", "{x}", "{y}", "{-y}"]:
                    if tms_url_parameter in source["properties"]["url"]:
                        raise ValidationError(
                            f"wmts URL should not contain tms parameter {tms_url_parameter} in URL"
                        )
                if "available_projections" not in source["properties"]:
                    raise ValidationError(f"Missing available_projections parameter in {filename}")
                if (
                    "available_projections" in source["properties"]
                    and "EPSG:3857" in source["properties"]["available_projections"]
                ):
                    logger.warning(
                        "WMTS source supports EPSG:3857, could this be tms? %s", filename
                    )

            source_url_excl_synonyms = (
                source["properties"]["url"].replace("{-y}", "{y}").replace("{wkid}", "{proj}")
            )
            missingparams = [x for x in params if x not in source_url_excl_synonyms]
            if missingparams:
                raise ValidationError(f"Missing parameter in {filename}: {missingparams}")

            # Check for double brackets
            if "{{" in source["properties"]["url"] or "}}" in source["properties"]["url"]:
                raise ValidationError(
                    f"{filename}: Double {{{{ or }}}} in URL: {source['properties']['url']}"
                )

            # If we're not global we must have a geometry.
            # The geometry itself is validated by jsonschema
            if "world" not in filename:
                if not isinstance(source.get("geometry"), dict) or "type" not in source["geometry"]:
                    raise ValidationError(f"{filename} should have a valid geometry or be global")
                if source["geometry"]["type"] not in {"Polygon", "MultiPolygon"}:
                    raise ValidationError(
                        f"{filename} should have a Polygon or MultiPolygon geometry"
                    )
                if "country_code" not in source["properties"]:
                    raise ValidationError(f"{filename} should have a country or be global")

                try:
                    validate_polygon_coordinates(source["geometry"], check_winding=True)
                except ValueError as e:
                    raise ValidationError(f"{filename} geometry is not valid: {e}") from e

                geom = shape(source["geometry"])
                # Check validity of geometries
                if not geom.is_valid:
                    raise ValidationError(
                        f"{filename} geometry is not valid: {explain_validity(geom)}"
                    )

                min_lon, min_lat, max_lon, max_lat = geom.bounds
                within_bounds = True
                for lon in [min_lon, max_lon]:
                    if lon < -180.0 or lon > 180.0:
                        within_bounds = False
                for lat in [min_lat, max_lat]:
                    if lat < -90.0 or lat > 90.0:
                        within_bounds = False
                if not within_bounds:
                    raise ValidationError(
                        f"{filename} contains invalid coordinates.: Geometry extent: "
                        f"{','.join(map(str, [min_lon, min_lat, max_lon, max_lat]))}"
                    )
            else:
                if "geometry" not in source:
                    raise ValidationError(f"{filename} should have null geometry")
                if source["geometry"] is not None:
                    raise ValidationError(
                        f"{filename} should have null geometry but it is {source['geometry']}"
                    )
            tested_sources_count += 1
        except ValidationError as e:
            failed = True
            logger.exception("Error in %s : %s", filename, e)
    if spacesave > 0:
        logger.warning("Disembedding all icons would save %s KB", round(spacesave / 1024.0, 2))

    print(f"Checked {tested_sources_count} sources.")
    if failed or tested_sources_count == 0:
        return 1

    return 0
