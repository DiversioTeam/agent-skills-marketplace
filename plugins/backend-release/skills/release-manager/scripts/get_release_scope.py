#!/usr/bin/env python3
"""Print immutable Git scope evidence; never fetch, check out, tag, or deploy."""

import argparse
import json
import os
import subprocess
from typing import TypedDict


class ReleaseScope(TypedDict):
    base_sha: str
    source_sha: str
    tree_changed: bool
    source_only_commits: list[str]


def get_git_environment() -> dict[str, str]:
    # Scope belongs to the current checkout, not inherited Git overrides.
    return {
        name: value for name, value in os.environ.items() if not name.startswith("GIT_")
    }


def get_git_output(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], text=True, env=get_git_environment()
    ).strip()


def get_release_scope(base_revision: str, source_revision: str) -> ReleaseScope:
    if get_git_output("rev-parse", "--is-shallow-repository") == "true":
        raise ValueError(
            "Full Git history is required; fetch missing history before checking scope."
        )
    base_sha = get_git_output(
        "rev-parse", "--verify", "--end-of-options", f"{base_revision}^{{commit}}"
    )
    source_sha = get_git_output(
        "rev-parse", "--verify", "--end-of-options", f"{source_revision}^{{commit}}"
    )
    if subprocess.run(
        ["git", "merge-base", base_sha, source_sha],
        stdout=subprocess.DEVNULL,
        env=get_git_environment(),
    ).returncode:
        raise ValueError(
            "Cannot establish common history for the selected commits; stop and inspect the repository."
        )
    base_tree = get_git_output("rev-parse", f"{base_sha}^{{tree}}")
    source_tree = get_git_output("rev-parse", f"{source_sha}^{{tree}}")
    return {
        "base_sha": base_sha,
        "source_sha": source_sha,
        "tree_changed": base_tree != source_tree,
        # Ancestry evidence, not a claim that every commit's patch is unshipped.
        "source_only_commits": get_git_output(
            "rev-list", "--reverse", "--topo-order", f"{base_sha}..{source_sha}", "--"
        ).splitlines(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", help="Target ref or recorded full commit SHA")
    parser.add_argument("source", help="Candidate ref or recorded full commit SHA")
    arguments = parser.parse_args()
    try:
        print(json.dumps(get_release_scope(arguments.base, arguments.source), indent=2))
    except (ValueError, subprocess.CalledProcessError, FileNotFoundError) as error:
        parser.exit(1, f"Cannot get release scope: {error}\n")
