"""Update Git consumers with the exact outputs used by Pages."""

import os
import shutil
import subprocess
from pathlib import Path

from eli.artifacts import OUTPUTS, validate_build


def git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=root, text=True).strip()


def publish(root: Path, generated: Path, expected_head: str) -> str:
    if git(root, "rev-parse", "HEAD") != expected_head:
        raise ValueError("Checkout does not match the expected build commit")
    remote = git(root, "ls-remote", "origin", "refs/heads/gh-pages").split()[0]
    if remote != expected_head:
        raise ValueError("gh-pages advanced during the build; the newer run will publish")
    if git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Refusing to publish from a checkout with tracked modifications")
    validate_build(root, generated)
    for name in OUTPUTS:
        shutil.copy2(generated / name, root / name)
    subprocess.run(["git", "add", "--", *OUTPUTS], cwd=root, check=True)
    if git(root, "diff", "--cached", "--name-only"):
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=github-actions[bot]",
                "-c",
                "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                "commit",
                "-m",
                f"Deploy generated imagery from {expected_head}",
            ],
            cwd=root,
            check=True,
        )
        # A normal fast-forward push rejects concurrent source commits without overwriting them.
        subprocess.run(["git", "push", "origin", "HEAD:refs/heads/gh-pages"], cwd=root, check=True)
    head = git(root, "rev-parse", "HEAD")
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a", encoding="utf-8") as stream:
            stream.write(f"head={head}\n")
    return head
