"""Build outputs and assemble the complete public site before publication."""

import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from eli.artifacts import OUTPUTS, validate_artifacts, validate_build, validate_geometry
from eli.common import JSON, discover, load_json
from eli.exporters import geojson_text, legacy_text, translation_text, xml_bytes


def export_source(path: Path, original: JSON) -> JSON:
    """Retain original coordinates when historical rounding would damage topology."""
    validate_geometry(original["geometry"])
    rounded = load_json(path, rounded=True)
    try:
        validate_geometry(rounded["geometry"])
    except ValueError:
        rounded["geometry"] = original["geometry"]
    if rounded["properties"]["type"] not in {"wms", "wmts"}:
        rounded["properties"].pop("available_projections", None)
    return rounded


def generation_time() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    now = datetime.fromtimestamp(int(epoch), UTC) if epoch is not None else datetime.now(UTC)
    return now.strftime("%Y-%m-%d %H:%M:%S")


def validate_output(root: Path, output: Path) -> None:
    output = output.resolve()
    root = root.resolve()
    if output == root or root.is_relative_to(output):
        raise ValueError("Output must not replace the repository or its parents")
    for name in ("sources", "src", "tests", "site", "i18n", ".git", ".github", ".tx"):
        protected = root / name
        if output == protected or output.is_relative_to(protected):
            raise ValueError(f"Output overlaps repository inputs: {output}")


def build(root: Path, output: Path) -> None:
    validate_output(root, output)
    paths = discover([], root)
    if not paths:
        raise ValueError("No sources found")
    sources = [load_json(path) for path in paths]
    rounded = [export_source(path, source) for path, source in zip(paths, sources, strict=True)]
    # Translations historically use unrounded input.
    rendered = {
        "imagery.geojson": geojson_text(rounded, generation_time()).encode("utf-8"),
        "imagery.json": legacy_text(rounded).encode("utf-8"),
        "imagery.xml": xml_bytes(rounded),
        "i18n/en.yaml": translation_text(sources).encode("utf-8"),
    }
    validate_artifacts(root, rendered, sources)
    output.mkdir(parents=True, exist_ok=True)
    previous = {
        name: (output / name).read_bytes() if (output / name).exists() else None
        for name in rendered
    }
    with TemporaryDirectory(prefix=".eli-build-", dir=output.parent) as temporary:
        staging = Path(temporary)
        for name, data in rendered.items():
            path = staging / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        replaced: list[str] = []
        try:
            for name in rendered:
                destination = output / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staging / name, destination)
                replaced.append(name)
        except BaseException:
            for name in reversed(replaced):
                prior_data = previous[name]
                if prior_data is None:
                    (output / name).unlink(missing_ok=True)
                else:
                    (output / name).write_bytes(prior_data)
            raise


def assemble_site(root: Path, generated: Path, output: Path) -> None:
    """Assemble from an existing build, so deployment and Git use identical bytes."""
    validate_output(root, output)
    if generated.resolve() == output.resolve() or generated.resolve().is_relative_to(
        output.resolve()
    ):
        raise ValueError("Site output must not contain the generated input directory")
    validate_build(root, generated)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".eli-site-", dir=output.parent) as temporary:
        staging = Path(temporary) / "site"
        staging.mkdir()
        # Preserve public documents, source URLs, icons, and all translations.
        for name in ("site", "sources", "i18n"):
            shutil.copytree(root / name, staging / name)
        for path in root.iterdir():
            if path.is_file() and (
                path.suffix.lower() in {".md", ".html", ".json"} or path.name == "LICENSE"
            ):
                shutil.copy2(path, staging / path.name)
        for name in OUTPUTS:
            shutil.copy2(generated / name, staging / name)
        (staging / ".nojekyll").touch()
        backup = Path(temporary) / "previous"
        if output.exists():
            output.rename(backup)
        try:
            staging.rename(output)
        except BaseException:
            if backup.exists():
                backup.rename(output)
            raise
