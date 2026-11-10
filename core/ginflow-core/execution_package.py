"""Deterministic validation seam for minimal Ginflow v2 packages."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


CONTRACT_STATES = frozenset({"draft", "approved", "active", "completed", "cancelled"})
ARTIFACT_STATES = frozenset({"draft", "approved", "active", "completed", "superseded", "cancelled"})
REQUIRED_UNIT_FIELDS = ("key", "plan_key", "owner", "scope", "acceptance", "workspace")
REQUIRED_CONTRACT_FIELDS = ("key", "objective", "boundaries", "exclusions", "acceptance", "verification")
REQUIRED_SPEC_FIELDS = ("key", "behavior", "interfaces", "rules", "edge_cases", "constraints")
REQUIRED_PLAN_FIELDS = ("key", "unit_key", "state", "steps", "verification")


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _utc(value: Any) -> bool:
    if not _text(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _document_errors(units: Sequence[Any]) -> list[str]:
    """Validate provider-neutral `document` refs; legacy packages without any pass."""
    mappings = [u for u in units if isinstance(u, Mapping) and _text(u.get("key"))]
    if not any("document" in u for u in mappings):
        return []
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for unit in mappings:
        key = str(unit["key"])
        ref = unit.get("document")
        if ref is None:
            errors.append(f"unit {key}.document is required")
            continue
        if not isinstance(ref, Mapping) or set(ref) != {"provider", "id", "path_or_url"} or not all(
            _text(value) for value in ref.values()
        ):
            errors.append(f"unit {key}.document must be one {{provider, id, path_or_url}} reference")
            continue
        pair = (ref["provider"], ref["id"])
        if pair in seen:
            errors.append(f"unit {key}.document duplicates another unit's document")
        seen.add(pair)
        if ref["provider"] == "local" and (ref["id"] != key or not ref["path_or_url"].endswith(f"/{key}.md")):
            errors.append(f"unit {key}.document does not match unit")
    return errors


def shape_package(
    initiative_key: str,
    contract: Mapping[str, Any],
    spec: Mapping[str, Any],
    units: Sequence[Mapping[str, Any]],
    plans: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, Any],
) -> dict[str, Any]:
    """Build one draft package without dispatching work or mutating inputs."""
    return {
        "workflow_version": 2,
        "initiative_key": initiative_key,
        "contract": {**deepcopy(dict(contract)), "state": "draft"},
        "spec": {**deepcopy(dict(spec)), "state": "draft"},
        "units": deepcopy(list(units)),
        "plans": [{**deepcopy(dict(plan)), "state": "draft"} for plan in plans],
        "baseline": deepcopy(dict(baseline)),
    }


def approve_package(
    package: Mapping[str, Any], approver: str, approved_at: str | None = None
) -> dict[str, Any]:
    """Approve complete package once; reject incomplete packages."""
    candidate = deepcopy(dict(package))
    timestamp = approved_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    contract = candidate.get("contract")
    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")
    candidate["contract"] = {
        **contract, "state": "approved", "approval": {"approver": approver, "approved_at": timestamp}
    }
    if isinstance(candidate.get("spec"), Mapping):
        candidate["spec"] = {**candidate["spec"], "state": "approved"}
    candidate["plans"] = [
        {**plan, "state": "approved"} for plan in candidate.get("plans", [])
    ]
    result = validate_package(candidate)
    if not result["valid"]:
        raise ValueError("incomplete execution package: " + "; ".join(result["errors"]))
    return candidate


def validate_package(package: Mapping[str, Any]) -> dict[str, Any]:
    """Return stable validation result for one approved v2 package.

    Validator accepts mappings so callers can load JSON/YAML without coupling
    this core seam to a serialization library.
    """
    errors: list[str] = []
    if not isinstance(package, Mapping):
        return {"valid": False, "errors": ["package must be a mapping"]}

    if package.get("workflow_version") != 2:
        errors.append("workflow_version must be 2")
    if not _text(package.get("initiative_key")):
        errors.append("initiative_key is required")

    contract = package.get("contract")
    if not isinstance(contract, Mapping):
        errors.append("contract must be a mapping")
    else:
        if contract.get("state") != "approved":
            errors.append("contract.state must be approved")
        if contract.get("state") not in CONTRACT_STATES:
            errors.append("contract.state is invalid")
        for field in REQUIRED_CONTRACT_FIELDS:
            value = contract.get(field)
            if not (_text(value) if field in {"key", "objective"} else isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and bool(value)):
                errors.append(f"contract.{field} is required")
        approval = contract.get("approval")
        if not isinstance(approval, Mapping):
            errors.append("contract.approval must be a mapping")
        else:
            if not _text(approval.get("approver")):
                errors.append("contract.approval.approver is required")
            if not _utc(approval.get("approved_at")):
                errors.append("contract.approval.approved_at must be RFC3339 with timezone")

    spec = package.get("spec")
    if not isinstance(spec, Mapping):
        errors.append("spec must be a mapping")
    else:
        if spec.get("state") != "approved":
            errors.append("spec.state must be approved")
        if spec.get("state") not in ARTIFACT_STATES:
            errors.append("spec.state is invalid")
        for field in REQUIRED_SPEC_FIELDS:
            value = spec.get(field)
            if not (_text(value) if field == "key" else isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and bool(value)):
                errors.append(f"spec.{field} is required")

    units = package.get("units")
    plans = package.get("plans")
    if not isinstance(units, Sequence) or isinstance(units, (str, bytes)) or not units:
        errors.append("units must be a non-empty list")
        units = []
    if not isinstance(plans, Sequence) or isinstance(plans, (str, bytes)) or not plans:
        errors.append("plans must be a non-empty list")
        plans = []

    unit_keys: set[str] = set()
    plan_keys: set[str] = set()
    dependencies: dict[str, list[str]] = {}
    for unit in units:
        if not isinstance(unit, Mapping):
            errors.append("each unit must be a mapping")
            continue
        key = unit.get("key")
        if not _text(key):
            errors.append("unit.key is required")
            continue
        key = str(key)
        if key in unit_keys:
            errors.append(f"duplicate unit key: {key}")
        unit_keys.add(key)
        for field in REQUIRED_UNIT_FIELDS[1:]:
            value = unit.get(field)
            if not (_text(value) if field in {"plan_key", "owner", "workspace"} else isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and bool(value)):
                errors.append(f"unit {key}.{field} is required")
        deps = unit.get("dependencies", [])
        if not isinstance(deps, Sequence) or isinstance(deps, (str, bytes)):
            errors.append(f"unit {key}.dependencies must be a list")
            deps = []
        dependencies[key] = [str(dep) for dep in deps]

    for plan in plans:
        if not isinstance(plan, Mapping):
            errors.append("each plan must be a mapping")
            continue
        key = plan.get("key")
        if not _text(key):
            errors.append("plan.key is required")
            continue
        key = str(key)
        if key in plan_keys:
            errors.append(f"duplicate plan key: {key}")
        plan_keys.add(key)
        for field in REQUIRED_PLAN_FIELDS:
            value = plan.get(field)
            if field == "unit_key":
                valid = value in unit_keys
            elif field in {"key", "state"}:
                valid = _text(value)
            else:
                valid = isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and bool(value)
            if not valid:
                errors.append(f"plan {key}.{field} is required")
        if plan.get("state") != "approved":
            errors.append(f"plan {key}.state must be approved")
        if plan.get("unit_key") not in unit_keys:
            errors.append(f"plan {key}.unit_key must reference a unit")

    errors.extend(_document_errors(units))

    for key, deps in dependencies.items():
        for dep in deps:
            if dep not in unit_keys:
                errors.append(f"unit {key} dependency must reference a unit: {dep}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in visiting:
            errors.append("unit dependencies must be acyclic")
            return
        if key in visited:
            return
        visiting.add(key)
        for dep in dependencies.get(key, []):
            if dep in unit_keys:
                visit(dep)
        visiting.remove(key)
        visited.add(key)

    for key in sorted(unit_keys):
        visit(key)

    baseline = package.get("baseline")
    if not isinstance(baseline, Mapping):
        errors.append("baseline must be a mapping")
    else:
        if not _text(baseline.get("commit")):
            errors.append("baseline.commit is required")
        verification = baseline.get("verification")
        if not isinstance(verification, Mapping):
            errors.append("baseline.verification must be a mapping")
        elif not _text(verification.get("command")) or verification.get("result") != "passed":
            errors.append("baseline.verification must contain passing command evidence")

    return {"valid": not errors, "errors": errors}


__all__ = ["ARTIFACT_STATES", "CONTRACT_STATES", "validate_package"]
