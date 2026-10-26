"""Publish generated files only while the remote branch still matches the tested revision."""

import argparse
import subprocess


OUTPUTS = ["imagery.geojson", "imagery.json", "imagery.xml", "imagery.id.json", "i18n/en.yaml"]


def git(*args, check=True):
    return subprocess.run(["git", *args], check=check, capture_output=True, text=True)


def publish(expected_revision, remote="origin", branch="gh-pages"):
    ref = f"refs/heads/{branch}"
    git("check-ref-format", ref)
    expected = git("rev-parse", "--verify", f"{expected_revision}^{{commit}}").stdout.strip()
    if git("rev-parse", "HEAD").stdout.strip() != expected:
        raise RuntimeError("Checkout does not match the tested revision")
    if git("diff", "--cached", "--quiet", check=False).returncode != 0:
        raise RuntimeError("Publication requires an initially empty staging area")

    def remote_revision():
        return git("ls-remote", "--exit-code", "--refs", remote, ref).stdout.split()[0]

    # The branch also contains deployment commits. Equality rejects both newer
    # source changes and an earlier successful publication of this candidate.
    if remote_revision() != expected:
        print("Skipping publication: the remote branch has moved beyond this candidate.")
        return False

    git("add", "--force", "--", *OUTPUTS)
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        print("No generated files changed.")
        return False
    # Use the caller's Git identity; automation configures it in the workflow.
    git("commit", "-m", f"Deploy generated imagery from {expected}")

    # This commit's parent is exactly the tested revision. The explicit lease
    # makes the update conditional on that revision still being the remote tip;
    # never rebase stale generated data onto a newer source/deployment commit.
    result = git("push", f"--force-with-lease={ref}:{expected}", remote, f"HEAD:{ref}", check=False)
    if result.returncode:
        if remote_revision() != expected:
            print("Skipping publication: the remote branch changed during the push.")
            return False
        raise RuntimeError(f"Publication failed:\n{result.stdout}{result.stderr}")
    print(f"Published generated imagery from {expected}.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("expected_revision", help="The exact source revision that passed the build and tests")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="gh-pages")
    args = parser.parse_args()
    publish(args.expected_revision, args.remote, args.branch)
