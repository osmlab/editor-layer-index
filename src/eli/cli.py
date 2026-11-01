"""The single command-line interface for ELI maintainers and CI."""

import argparse
import asyncio
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

from eli.common import discover, load_json


def repository_root(value: str | None) -> Path:
    if value:
        root = Path(value).resolve()
    else:
        root = next(
            (p for p in (Path.cwd(), *Path.cwd().parents) if (p / "schema.json").is_file()),
            Path.cwd(),
        )
    if not (root / "schema.json").is_file() or not (root / "sources").is_dir():
        raise ValueError(f"Not an ELI data repository: {root}; use --root")
    return root


def changed_sources(root: Path, base: str, head: str) -> list[Path]:
    merge_base = subprocess.check_output(
        ["git", "merge-base", base, head], cwd=root, text=True
    ).strip()
    output = subprocess.check_output(
        [
            "git",
            "diff",
            "--name-only",
            "-z",
            "--diff-filter=ACMR",
            merge_base,
            head,
            "--",
            "sources",
        ],
        cwd=root,
    )
    return sorted(
        (
            root / value.decode("utf-8", errors="surrogateescape")
            for value in output.split(b"\0")
            if value
        ),
        key=lambda p: p.as_posix(),
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Build, validate, and maintain the Editor Layer Index"
    )
    result.add_argument(
        "--root", help="ELI data repository (default: nearest ancestor of the current directory)"
    )
    commands = result.add_subparsers(dest="command", required=True)
    check = commands.add_parser(
        "check", help="Validate sources; strict mode also contacts imagery servers"
    )
    check.add_argument("paths", nargs="*", help="GeoJSON files or directories (default: sources)")
    check.add_argument("--known-failures", help="Exact, expiring HTTP failures to report as known")
    check.add_argument("--report", help="Write strict diagnostics as JSON")
    check.add_argument("--strict", action="store_true", help="Also run live strict checks")
    check.add_argument(
        "--changed-from", help="Check only sources changed since the merge base with this Git ref"
    )
    check.add_argument("--head", default="HEAD", help="Head ref for --changed-from")
    check.add_argument("-v", "--verbose", action="count", default=0)
    for name, help_text in (
        ("build", "Generate all four public outputs"),
        ("site", "Assemble the complete public site"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--output-dir", default="build" if name == "build" else "build/site")
        if name == "site":
            command.add_argument(
                "--build-dir", help="Reuse outputs from an existing build instead of rebuilding"
            )
    sync = commands.add_parser(
        "sync-wms", help="Contact WMS servers and rewrite selected source files in place"
    )
    sync.add_argument("paths", nargs="*")
    translations = commands.add_parser(
        "translations", help="Push source strings or pull translations with Transifex"
    )
    translations.add_argument("action", choices=("push", "pull"))
    legacy = commands.add_parser(
        "convert-legacy", help="Export selected GeoJSON sources as legacy JSON to stdout"
    )
    legacy.add_argument("paths", nargs="*")
    legacy.add_argument("-b", "--bbox", action="store_true")
    legacy.add_argument("-t", "--tms-only", action="store_true")
    legacy.add_argument("-r", "--remove-polygons", action="store_true")
    for name, help_text in (
        ("geojsonify", "Convert legacy JSON source files to GeoJSON IN PLACE"),
        ("unembed-icons", "Write PNG icons and rewrite source icon URLs IN PLACE"),
        ("audit-urls", "Report redirects and HTTPS opportunities; does not write files"),
    ):
        utility = commands.add_parser(name, help=help_text, description=help_text)
        utility.add_argument("paths", nargs="*")
        utility.add_argument("-v", "--verbose", action="count", default=0)
    josm = commands.add_parser(
        "import-josm", help="Convert JOSM XML into source files in the destination directory"
    )
    josm.add_argument("xml")
    josm.add_argument("--output-dir", required=True)
    categories = commands.add_parser(
        "sync-categories", help="Fetch JOSM categories; write changed sources to a directory"
    )
    categories.add_argument("--sources", default="sources")
    categories.add_argument("--output-dir", required=True)
    minzoom = commands.add_parser(
        "minzoom", help="Interactively preview tiles and rewrite selected sources' minimum zoom"
    )
    minzoom.add_argument("paths", nargs="*")
    minzoom.add_argument("--output-dir", default="min_zoom_results")
    publish = commands.add_parser(
        "publish-git", help="CI: commit and push a verified build for Git consumers"
    )
    publish.add_argument("--build-dir", required=True)
    publish.add_argument("--expected-head", required=True)
    return result


def resolve_path(root: Path, value: str) -> Path:
    """Resolve a command path relative to the selected data repository."""
    path = Path(value)
    return path if path.is_absolute() else root / path


def source_paths(args: argparse.Namespace, root: Path) -> list[Path]:
    """Select nonempty source inputs for maintenance commands."""
    paths = discover(args.paths, root)
    if not paths:
        raise ValueError("No sources found")
    return paths


def _run_publish_git(args: argparse.Namespace, root: Path) -> int:
    from eli.publish import publish

    publish(root, resolve_path(root, args.build_dir), args.expected_head)
    return 0


def _run_check(args: argparse.Namespace, root: Path) -> int:
    from eli.check import run

    if args.changed_from:
        if args.paths:
            raise ValueError("--changed-from cannot be combined with paths")
        paths = [
            p
            for p in changed_sources(root, args.changed_from, args.head)
            if p.suffix == ".geojson" and p.is_file()
        ]
        if not paths:
            print("No changed GeoJSON sources.")
            return 0
    else:
        paths = discover(args.paths, root)
    if (args.known_failures or args.report) and not args.strict:
        raise ValueError("--known-failures and --report require --strict")
    status = run(paths, root, args.verbose)
    if (status and not args.report) or not args.strict:
        return status
    from eli.known_failures import KnownFailures
    from eli.strict import StrictChecker

    checker = StrictChecker(root, max(2, args.verbose))
    checker.known_failures = KnownFailures(
        resolve_path(root, args.known_failures) if args.known_failures else None
    )
    checker.report_path = resolve_path(root, args.report) if args.report else None
    return int(bool(checker.run(paths, root) or status))


def _run_build(args: argparse.Namespace, root: Path) -> int:
    command = args.command
    from tempfile import TemporaryDirectory

    from eli.build import assemble_site, build

    output = resolve_path(root, args.output_dir)
    if command == "build":
        build(root, output)
    elif args.build_dir:
        assemble_site(root, resolve_path(root, args.build_dir), output)
    else:
        with TemporaryDirectory(prefix="eli-generated-") as temporary:
            generated = Path(temporary)
            build(root, generated)
            assemble_site(root, generated, output)
    return 0


def _run_translations(args: argparse.Namespace, root: Path) -> int:
    client = shutil.which("tx")
    if client is None:
        raise ValueError(
            "Install the Transifex CLI and configure its credentials before using this command"
        )
    if args.action == "push":
        from tempfile import TemporaryDirectory

        from eli.build import build

        with TemporaryDirectory(prefix="eli-translations-") as temporary:
            generated = Path(temporary)
            build(root, generated)
            shutil.copy2(generated / "i18n/en.yaml", root / "i18n/en.yaml")
    tx_args = ["push", "-s"] if args.action == "push" else ["pull", "-a", "--use-git-timestamps"]
    return subprocess.call([client, *tx_args], cwd=root)


def _run_import_josm(args: argparse.Namespace, root: Path) -> int:
    from eli.import_josm import run as import_josm

    import_josm(str(resolve_path(root, args.xml)), str(resolve_path(root, args.output_dir)))
    return 0


def _run_sync_categories(args: argparse.Namespace, root: Path) -> int:
    from eli.sync_categories import run as sync_categories

    sync_categories(str(resolve_path(root, args.sources)), str(resolve_path(root, args.output_dir)))
    return 0


def _run_sync_wms(args: argparse.Namespace, root: Path) -> int:
    paths = source_paths(args, root)
    from eli.sync_wms import WMSSync

    syncer = WMSSync()
    asyncio.run(syncer.start_processing(paths))
    return int(syncer.failures > 0)


def _run_convert_legacy(args: argparse.Namespace, root: Path) -> int:
    paths = source_paths(args, root)
    from eli.exporters import LegacyOptions, legacy_text

    print(
        legacy_text(
            [load_json(p, rounded=True) for p in paths],
            LegacyOptions(args.bbox, args.tms_only, args.remove_polygons),
        ),
        end="",
    )
    return 0


def _run_geojsonify(args: argparse.Namespace, root: Path) -> int:
    paths = source_paths(args, root)
    from eli.geojsonify import convert

    for p in paths:
        p.write_text(
            json.dumps(convert(load_json(p)), indent=4, separators=(",", ": ")) + "\n",
            encoding="utf-8",
        )
    return 0


def _run_unembed_icons(args: argparse.Namespace, root: Path) -> int:
    paths = source_paths(args, root)
    import os

    from eli.unembed_icons import run as unembed_icons

    previous = Path.cwd()
    try:
        os.chdir(root)
        unembed_icons([str(p.relative_to(root)) for p in paths], args.verbose)
    finally:
        os.chdir(previous)
    return 0


def _run_audit_urls(args: argparse.Namespace, root: Path) -> int:
    paths = source_paths(args, root)
    from eli.audit_urls import check_url

    for p in paths:
        data = load_json(p)
        for feature in data.get("features", [data]):
            props = feature["properties"]
            for url in (
                props.get("url"),
                props.get("icon"),
                props.get("license_url"),
                props.get("attribution", {}).get("url"),
            ):
                if isinstance(url, str):
                    check_url(url, bool(args.verbose))
    return 0


def _run_minzoom(args: argparse.Namespace, root: Path) -> int:
    paths = source_paths(args, root)
    from eli.minzoom import MinZoom

    helper = MinZoom(str(resolve_path(root, args.output_dir)))
    for p in paths:
        helper.start_processing(str(p))
    return 0


def execute(args: argparse.Namespace, root: Path) -> int:
    """Dispatch a parsed command to its focused implementation."""
    handlers = {
        "publish-git": _run_publish_git,
        "check": _run_check,
        "build": _run_build,
        "site": _run_build,
        "translations": _run_translations,
        "import-josm": _run_import_josm,
        "sync-categories": _run_sync_categories,
        "sync-wms": _run_sync_wms,
        "convert-legacy": _run_convert_legacy,
        "geojsonify": _run_geojsonify,
        "unembed-icons": _run_unembed_icons,
        "audit-urls": _run_audit_urls,
        "minzoom": _run_minzoom,
    }
    return handlers[args.command](args, root)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return execute(args, repository_root(args.root))
    # The CLI converts unexpected failures into a nonzero exit status and a user-facing error.
    # pylint: disable-next=broad-exception-caught
    except Exception as error:
        logging.getLogger("eli").error("%s", error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
