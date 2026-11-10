"""Append-only human Review Cycle contract."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from hashlib import sha256
import json
from typing import Any

SEVERITIES = frozenset({"blocking", "high", "medium", "low", "informational"})
DISPOSITIONS = frozenset({"accept", "enhance", "reject", "defer"})
STATES = frozenset({"open", "resolved", "accepted_risk", "not_applicable"})
OUTCOMES = frozenset({"approved_for_mr", "enhancement_requested", "rejected", "resume_execution", "reshape_required", "stopped"})


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _base_errors(record: Mapping[str, Any]) -> list[str]:
    errors = []
    if record.get("schema") != "review_cycle":
        errors.append("schema must be review_cycle")
    for field in ("review_key", "initiative_key", "batch_key"):
        if not _text(record.get(field)):
            errors.append(f"{field} is required")
    actor = record.get("actor")
    if not isinstance(actor, Mapping) or actor.get("claim") != "review:decide" or not all(_text(actor.get(key)) for key in ("id", "profile")):
        errors.append("actor claim is unauthorized")
    commits = record.get("commits")
    if not isinstance(commits, Mapping) or not all(_text(commits.get(key)) for key in ("baseline", "result", "target")):
        errors.append("exact commits are required")
    if record.get("aggregate_decision") not in OUTCOMES:
        errors.append("aggregate_decision is unsupported")
    revision = record.get("revision")
    if not isinstance(revision, int) or revision < 1:
        errors.append("revision must be a positive integer")
    return errors


def validate_review(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return stable validation result for one review revision."""
    if not isinstance(record, Mapping):
        return {"valid": False, "errors": ["review must be a mapping"]}
    errors = _base_errors(record)
    evidence = record.get("evidence")
    if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes)) or not evidence:
        errors.append("evidence is required")
        evidence = []
    evidence_ids = {item.get("id") for item in evidence if isinstance(item, Mapping) and _text(item.get("id"))}
    for item in evidence:
        if not isinstance(item, Mapping) or not all(_text(item.get(field)) for field in ("id", "kind")):
            errors.append("evidence is malformed")
    findings = record.get("findings", [])
    if not isinstance(findings, Sequence) or isinstance(findings, (str, bytes)):
        errors.append("findings must be a list")
        findings = []
    for finding in findings:
        refs = finding.get("evidence_ids") if isinstance(finding, Mapping) else None
        paths = finding.get("paths") if isinstance(finding, Mapping) else None
        confidence = finding.get("confidence") if isinstance(finding, Mapping) else None
        if not isinstance(finding, Mapping) or finding.get("severity") not in SEVERITIES or finding.get("state") not in STATES or not _text(confidence) or not isinstance(paths, Sequence) or isinstance(paths, (str, bytes)) or not isinstance(refs, Sequence) or isinstance(refs, (str, bytes)):
            errors.append("finding is malformed")
            continue
        if any(not _text(path) for path in paths):
            errors.append("finding paths are malformed")
            continue
        if not isinstance(finding.get("producer"), str) or not _text(finding.get("producer")):
            errors.append("finding producer is required")
            continue
        if not _text(finding.get("title")):
            errors.append("finding title is required")
            continue
        if finding.get("state") == "accepted_risk" and not _text(finding.get("reason")):
            errors.append("accepted risk reason is required")
        if finding.get("severity") in {"blocking", "high"} and finding.get("state") not in {"resolved", "not_applicable", "accepted_risk"} and record.get("aggregate_decision") == "approved_for_mr":
            errors.append("finding blocks approved_for_mr")
        if any(not _text(ref) for ref in refs) or not set(refs) <= evidence_ids:
            errors.append("finding references unsupported evidence")
    change_groups = record.get("change_groups")
    if not isinstance(change_groups, Sequence) or isinstance(change_groups, (str, bytes)):
        errors.append("change_groups must be a list")
        change_groups = []
    groups = {item.get("key") for item in change_groups if isinstance(item, Mapping) and _text(item.get("key"))}
    dispositions = record.get("dispositions", [])
    if not isinstance(dispositions, Sequence) or isinstance(dispositions, (str, bytes)):
        errors.append("dispositions must be a list")
        dispositions = []
    for disposition in dispositions:
        if not isinstance(disposition, Mapping) or disposition.get("disposition") not in DISPOSITIONS or disposition.get("change_group") not in groups:
            errors.append("disposition is malformed")
    if record.get("aggregate_decision") == "approved_for_mr" and record.get("deviations"):
        errors.append("deviations block approved_for_mr")
    return {"valid": not errors, "errors": errors}


def _digest(record: Mapping[str, Any]) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return sha256(canonical).hexdigest()


def append_revision(record: Mapping[str, Any], *, actor: Mapping[str, Any], revision: int | None = None, previous_digest: str | None = None) -> dict[str, Any]:
    """Create one immutable review revision; caller supplies prior binding for later revisions."""
    candidate = deepcopy(dict(record))
    if candidate.get("immutable") or candidate.get("revision_digest"):
        raise ValueError("append requires an uncommitted review revision")
    expected_revision = revision or candidate.get("revision")
    if not isinstance(expected_revision, int) or expected_revision < 1:
        raise ValueError("revision must be a positive integer")
    if previous_digest is not None and not _text(previous_digest):
        raise ValueError("previous_digest is required for appended revisions")
    candidate["revision"] = expected_revision
    if dict(actor) != dict(candidate.get("actor", {})):
        raise ValueError("review actor mismatch")
    result = validate_review(candidate)
    if not result["valid"]:
        raise ValueError("invalid review: " + "; ".join(result["errors"]))
    if previous_digest is not None:
        candidate["previous_revision_digest"] = previous_digest
    candidate["revision_digest"] = _digest(candidate)
    candidate["immutable"] = True
    return candidate


def append_review_revision(previous: Mapping[str, Any], revision: Mapping[str, Any], *, actor: Mapping[str, Any]) -> dict[str, Any]:
    """Append a new revision while retaining a digest link to the prior revision."""
    if not previous.get("immutable") or not _text(previous.get("revision_digest")):
        raise ValueError("previous review must be immutable")
    candidate = deepcopy(dict(revision))
    next_revision = previous.get("revision", 0) + 1
    return append_revision(candidate, actor=actor, revision=next_revision, previous_digest=previous["revision_digest"])


__all__ = ["append_revision", "append_review_revision", "validate_review"]
