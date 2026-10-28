"""Exercise changed-source discovery and concurrent Git publication."""

import subprocess
from pathlib import Path

import pytest

from eli.artifacts import OUTPUTS
from eli.build import build
from eli.cli import changed_sources, main
from eli.publish import publish


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def initialize(root: Path) -> str:
    git(root, "init", "-b", "gh-pages")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.org")
    git(root, "config", "commit.gpgsign", "false")
    git(root, "add", ".")
    git(root, "commit", "-m", "Initial")
    return git(root, "rev-parse", "HEAD")


def test_changed_paths_rename_delete_spaces_and_merge_base(data_root: Path, source: Path) -> None:
    base = initialize(data_root)
    renamed = source.with_name("renamed file.geojson")
    git(data_root, "mv", str(source), str(renamed))
    deleted = data_root / "sources/deleted.geojson"
    deleted.write_text("{}")
    git(data_root, "add", ".")
    git(data_root, "commit", "-m", "Rename and add")
    deleted.unlink()
    git(data_root, "add", ".")
    git(data_root, "commit", "-m", "Delete")
    assert changed_sources(data_root, base, "HEAD") == [renamed]
    assert main(["--root", str(data_root), "check", "--changed-from", base]) == 0
    assert main(["--root", str(data_root), "check", "--strict", "--changed-from", "HEAD"]) == 0


def test_changed_paths_uses_merge_base(data_root: Path, source: Path) -> None:
    initialize(data_root)
    git(data_root, "checkout", "-b", "other")
    base_only = data_root / "sources/base-only.geojson"
    base_only.write_text("{}")
    git(data_root, "add", ".")
    git(data_root, "commit", "-m", "Base-only change")
    git(data_root, "checkout", "gh-pages")
    source.write_text(source.read_text() + "\n")
    git(data_root, "add", ".")
    git(data_root, "commit", "-m", "Head change")
    assert changed_sources(data_root, "other", "HEAD") == [source]


@pytest.mark.usefixtures("source")
def test_publish_exact_bytes_and_reject_stale_head(
    data_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    head = initialize(data_root)
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    git(data_root, "remote", "add", "origin", str(remote))
    git(data_root, "push", "origin", "gh-pages")
    generated = tmp_path / "generated"
    build(data_root, generated)
    for name in OUTPUTS:
        (data_root / name).parent.mkdir(parents=True, exist_ok=True)
    published = publish(data_root, generated, head)
    assert git(data_root, "ls-remote", "origin", "refs/heads/gh-pages").split()[0] == published
    for name in OUTPUTS:
        assert (data_root / name).read_bytes() == (generated / name).read_bytes()
    # A second checkout advancing the remote must not be overwritten.
    other = tmp_path / "other"
    subprocess.run(
        ["git", "clone", "--branch", "gh-pages", str(remote), str(other)],
        check=True,
        capture_output=True,
    )
    git(other, "config", "user.name", "Other")
    git(other, "config", "user.email", "other@example.org")
    git(other, "config", "commit.gpgsign", "false")
    (other / "new-source.txt").write_text("new work")
    git(other, "add", ".")
    git(other, "commit", "-m", "Concurrent work")
    git(other, "push", "origin", "gh-pages")
    with pytest.raises(ValueError, match="advanced"):
        publish(data_root, generated, published)
    assert git(data_root, "ls-remote", "origin", "refs/heads/gh-pages").split()[0] == git(
        other, "rev-parse", "HEAD"
    )


@pytest.mark.usefixtures("source")
def test_publish_rejects_corrupted_build_before_changing_git(
    data_root: Path, tmp_path: Path
) -> None:
    head = initialize(data_root)
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    git(data_root, "remote", "add", "origin", str(remote))
    git(data_root, "push", "origin", "gh-pages")
    generated = tmp_path / "generated"
    build(data_root, generated)
    previous = {
        name: (data_root / name).read_bytes() if (data_root / name).exists() else None
        for name in OUTPUTS
    }
    (generated / "imagery.xml").write_bytes(b"<broken")
    with pytest.raises(ValueError, match="imagery.xml"):
        publish(data_root, generated, head)
    assert git(data_root, "rev-parse", "HEAD") == head
    assert git(data_root, "status", "--porcelain", "--untracked-files=no") == ""
    assert git(data_root, "ls-remote", "origin", "refs/heads/gh-pages").split()[0] == head
    assert previous == {
        name: (data_root / name).read_bytes() if (data_root / name).exists() else None
        for name in OUTPUTS
    }
