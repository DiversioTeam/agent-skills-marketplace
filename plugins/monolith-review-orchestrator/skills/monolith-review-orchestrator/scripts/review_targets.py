"""Shared review-target metadata for monolith review orchestration helpers."""

from __future__ import annotations

from typing import Final, TypedDict


class ReviewTargetConfig(TypedDict):
    alias: str
    submodule_path: str | None


REVIEW_TARGETS: Final[dict[tuple[str, str], ReviewTargetConfig]] = {
    ("DiversioTeam", "monolith"): {
        "alias": "mono",
        "submodule_path": None,
    },
    ("DiversioTeam", "Django4Lyfe"): {
        "alias": "bk",
        "submodule_path": "backend",
    },
    ("DiversioTeam", "Diversio-Frontend"): {
        "alias": "fe",
        "submodule_path": "frontend",
    },
    ("DiversioTeam", "Optimo-Frontend"): {
        "alias": "of",
        "submodule_path": "optimo-frontend",
    },
    ("DiversioTeam", "diversio-ds"): {
        "alias": "ds",
        "submodule_path": "design-system",
    },
    ("DiversioTeam", "infrastructure"): {
        "alias": "infra",
        "submodule_path": "infrastructure",
    },
    ("DiversioTeam", "diversio-serverless"): {
        "alias": "sls",
        "submodule_path": "diversio-serverless",
    },
    ("DiversioTeam", "agent-skills-marketplace"): {
        "alias": "asm",
        "submodule_path": "agent-skills-marketplace",
    },
}

KNOWN_V1_REPOS: Final[frozenset[str]] = frozenset(
    repo for _owner, repo in REVIEW_TARGETS
)


def format_known_review_targets() -> str:
    return ", ".join(
        f"{owner}/{repo}" for owner, repo in sorted(REVIEW_TARGETS)
    )
