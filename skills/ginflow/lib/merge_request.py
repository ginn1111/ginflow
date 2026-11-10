"""Provider-neutral merge-request intent contract."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any


def build_mr_intent(review: Mapping[str, Any], *, title: str, body: str, reviewers: list[str] | None = None, labels: list[str] | None = None, draft: bool = True) -> dict[str, Any]:
    """Prepare MR intent only from fresh, immutable, safe review evidence."""
    required = ("initiative_key", "review_key", "revision_digest", "source_ref", "source_commit", "target_ref", "target_commit")
    missing = [field for field in required if not isinstance(review.get(field), str) or not review[field]]
    if missing:
        raise ValueError("missing MR provenance: " + ", ".join(missing))
    verification = review.get("verification")
    if not isinstance(verification, Mapping) or verification.get("commit") != review["source_commit"] or verification.get("result") != "passed":
        raise ValueError("verification must pass against source commit")
    if review.get("dirty"):
        raise ValueError("dirty state blocks MR intent")
    if review.get("secret_exposure"):
        raise ValueError("known secret exposure blocks MR intent")
    if not review.get("changed_paths_covered"):
        raise ValueError("changed paths must be covered")
    if review.get("blocking_findings", 0) or review.get("high_findings", 0):
        raise ValueError("unresolved findings block MR intent")
    merge = review.get("merge_evidence")
    if not isinstance(merge, Mapping) or merge.get("commit") != review["source_commit"] or merge.get("target") != review["target_commit"] or merge.get("conflicts") is not False:
        raise ValueError("local merge evidence is stale or missing")
    if not isinstance(title, str) or not title.strip() or not isinstance(body, str) or not body.strip():
        raise ValueError("title and body are required")
    return {
        "schema": "merge_request_intent",
        "initiative_key": review["initiative_key"],
        "review_key": review["review_key"],
        "revision_digest": review["revision_digest"],
        "source_ref": review["source_ref"],
        "source_commit": review["source_commit"],
        "target_ref": review["target_ref"],
        "target_commit": review["target_commit"],
        "title": title.strip(),
        "body": body.strip(),
        "lineage": {"initiative_key": review["initiative_key"], "review_key": review["review_key"]},
        "change_groups": deepcopy(review.get("change_groups", [])),
        "verification": deepcopy(dict(verification)),
        "risks": deepcopy(review.get("risks", [])),
        "reviewers": list(reviewers or []),
        "labels": list(labels or []),
        "draft": bool(draft),
        "publication_status": "not_published",
    }


__all__ = ["build_mr_intent"]
