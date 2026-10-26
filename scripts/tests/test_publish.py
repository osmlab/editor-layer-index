import subprocess

import pytest

from publish import OUTPUTS, publish


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def write_outputs(repo, value):
    for name in OUTPUTS:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)


@pytest.fixture
def repository(tmp_path, monkeypatch):
    remote = tmp_path / "remote.git"
    repo = tmp_path / "publisher"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "init", "-b", "gh-pages", str(repo)], check=True, capture_output=True)
    git(repo, "config", "user.name", "Publisher Test")
    git(repo, "config", "user.email", "publisher@example.com")
    git(repo, "config", "commit.gpgsign", "false")
    (repo / "source.txt").write_text("source")
    (repo / ".gitignore").write_text("imagery.id.json\n")
    write_outputs(repo, "old output")
    git(repo, "add", "--force", ".")
    git(repo, "commit", "-m", "Initial source and output")
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "origin", "HEAD:refs/heads/gh-pages")
    expected = git(repo, "rev-parse", "HEAD")
    write_outputs(repo, "tested output")
    monkeypatch.chdir(repo)
    return repo, remote, expected


def test_fresh_candidate_publishes_exact_outputs(repository):
    repo, remote, expected = repository
    (repo / "unrelated.txt").write_text("must stay local")
    assert publish(expected)
    tip = git(remote, "rev-parse", "refs/heads/gh-pages")
    assert git(remote, "rev-parse", f"{tip}^") == expected
    assert git(remote, "show", "-s", "--format=%an <%ae>", tip) == "Publisher Test <publisher@example.com>"
    assert git(remote, "show", f"{tip}:source.txt") == "source"
    assert "Deploy" in git(remote, "show", "-s", "--format=%s", tip)
    for name in OUTPUTS:
        assert git(remote, "show", f"{tip}:{name}") == "tested output"
    assert "unrelated.txt" not in git(remote, "ls-tree", "--name-only", tip)


def advance_remote(repo, remote, expected, deployment=False):
    tree = git(repo, "rev-parse", f"{expected}^{{tree}}")
    newer = git(repo, "commit-tree", tree, "-p", expected, "-m", "Deploy newer output" if deployment else "New source")
    git(repo, "push", "origin", f"{newer}:refs/heads/race-fixture")
    git(remote, "update-ref", "refs/heads/gh-pages", newer)
    return newer


@pytest.mark.parametrize("deployment", [False, True])
def test_superseded_candidate_is_skipped(repository, deployment):
    repo, remote, expected = repository
    newer = advance_remote(repo, remote, expected, deployment)
    assert not publish(expected)
    assert git(remote, "rev-parse", "refs/heads/gh-pages") == newer
    assert git(repo, "rev-parse", "HEAD") == expected


def test_race_after_precheck_cannot_overwrite_newer_revision(repository, monkeypatch):
    repo, remote, expected = repository
    newer = advance_remote(repo, remote, expected)
    git(remote, "update-ref", "refs/heads/gh-pages", expected)
    hook = repo / ".git/hooks/pre-push"
    hook.write_text('#!/bin/sh\ngit --git-dir="$ELI_TEST_REMOTE" update-ref refs/heads/gh-pages "$ELI_TEST_NEWER"\n')
    hook.chmod(0o755)
    monkeypatch.setenv("ELI_TEST_REMOTE", str(remote))
    monkeypatch.setenv("ELI_TEST_NEWER", newer)
    assert not publish(expected)
    assert git(remote, "rev-parse", "refs/heads/gh-pages") == newer


def test_push_failure_is_not_reported_as_stale(repository):
    repo, remote, expected = repository
    hook = repo / ".git/hooks/pre-push"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    with pytest.raises(RuntimeError, match="Publication failed"):
        publish(expected)
    assert git(remote, "rev-parse", "refs/heads/gh-pages") == expected


def test_unchanged_outputs_need_no_publication(repository):
    repo, remote, expected = repository
    write_outputs(repo, "old output")
    assert not publish(expected)
    assert git(remote, "rev-parse", "refs/heads/gh-pages") == expected


def test_wrong_checkout_is_rejected(repository):
    repo, remote, expected = repository
    git(repo, "commit", "--allow-empty", "-m", "Untested source")
    with pytest.raises(RuntimeError, match="Checkout does not match"):
        publish(expected)
    assert git(remote, "rev-parse", "refs/heads/gh-pages") == expected


def test_preexisting_staged_changes_are_rejected(repository):
    repo, remote, expected = repository
    (repo / "source.txt").write_text("untested")
    git(repo, "add", "source.txt")
    with pytest.raises(RuntimeError, match="empty staging area"):
        publish(expected)
    assert git(remote, "rev-parse", "refs/heads/gh-pages") == expected
