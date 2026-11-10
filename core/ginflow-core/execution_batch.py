"""Immutable AFK execution batch authorization around v2 cards."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from card_creation import create_execution_cards
from execution_package import validate_package


def canonical_digest(value: Mapping[str, Any]) -> str:
    """Hash canonical JSON so equivalent mappings bind same package content."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return sha256(encoded).hexdigest()


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _actor(actor: Any) -> None:
    if not isinstance(actor, Mapping) or not all(_text(actor.get(key)) for key in ("id", "profile", "claim")):
        raise ValueError("actor requires id, profile, and claim")
    if actor["claim"] != "execution:authorize":
        raise ValueError("actor claim is unauthorized")


def _collection(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def _boundaries(package: Mapping[str, Any], workspaces: Sequence[str], stop_conditions: Sequence[str]) -> None:
    units = package.get("units", [])
    if not _collection(units) or not units:
        raise ValueError("Ticket set is required")
    if not _collection(workspaces) or any(not _text(workspace) for workspace in workspaces):
        raise ValueError("workspaces are required")
    if len(set(workspaces)) != len(workspaces):
        raise ValueError("workspaces must be unique")
    allowed = set(workspaces)
    text_fields = {"objective", "workspace", "owner", "change_group", "risk", "escalation"}
    collection_fields = {"scope", "exclusions", "acceptance", "dependencies", "verification"}
    units_by_workspace: dict[str, list[Mapping[str, Any]]] = {}
    for unit in units:
        if not isinstance(unit, Mapping):
            raise ValueError("each Ticket must be a mapping")
        for field in text_fields | collection_fields:
            value = unit.get(field)
            valid = _text(value) if field in text_fields else _collection(value)
            if not valid:
                raise ValueError(f"Ticket {unit.get('key', '?')}.{field} is required")
        if unit["workspace"] not in allowed:
            raise ValueError(f"Ticket workspace is not authorized: {unit['workspace']}")
        units_by_workspace.setdefault(unit["workspace"], []).append(unit)

    for workspace, grouped_units in units_by_workspace.items():
        if len(grouped_units) < 2:
            continue
        if not all(_isolated_workspace(unit, workspace) for unit in grouped_units):
            raise ValueError("shared mutable workspace requires explicit isolation proof")
        paths = [Path(unit["workspace_isolation"]["path"]).expanduser().resolve() for unit in grouped_units]
        if len(set(paths)) != len(paths):
            raise ValueError("shared mutable workspace requires distinct isolation paths")

    if any(not _text(condition) for condition in stop_conditions):
        raise ValueError("stop_conditions must contain text")


def _isolated_workspace(unit: Mapping[str, Any], workspace: str) -> bool:
    """Accept explicit per-Ticket proof before allowing concurrent shared paths."""
    proof = unit.get("workspace_isolation")
    if not isinstance(proof, Mapping):
        return False
    kind = proof.get("kind")
    path = proof.get("path")
    if kind not in {"worktree", "isolated_workspace"} or not _text(path):
        return False
    try:
        isolated = Path(path).expanduser().resolve()
        shared = Path(workspace).expanduser().resolve()
    except (OSError, RuntimeError, TypeError, ValueError):
        return False
    # Nested worktrees (e.g. <repo>/.claude/worktrees/x) are valid; only the shared path itself is not isolation.
    return isolated != shared


def authorize_batch(package: Mapping[str, Any], *, actor: Mapping[str, Any], budget: Mapping[str, Any], stop_conditions: Sequence[str], workspaces: Sequence[str], baseline_commit: str, batch_number: int = 1) -> dict[str, Any]:
    """Authorize one immutable execution attempt without dispatch side effects."""
    if package.get("contract", {}).get("state") != "approved":
        raise ValueError("package must be approved")
    validation = validate_package(package)
    if not validation["valid"]:
        raise ValueError("invalid execution package: " + "; ".join(validation["errors"]))
    _actor(actor)
    if not isinstance(budget, Mapping) or not isinstance(budget.get("max_turns"), int) or budget["max_turns"] <= 0:
        raise ValueError("budget.max_turns must be positive")
    if not isinstance(stop_conditions, Sequence) or isinstance(stop_conditions, (str, bytes)) or not stop_conditions:
        raise ValueError("stop_conditions are required")
    if not _text(baseline_commit) or baseline_commit != package.get("baseline", {}).get("commit"):
        raise ValueError("baseline commit must match package baseline")
    _boundaries(package, workspaces, stop_conditions)
    initiative = package.get("initiative_key")
    if not _text(initiative):
        raise ValueError("initiative_key is required")
    return {
        "schema": "execution_batch",
        "batch_key": f"{initiative}/run-{batch_number}",
        "initiative_key": initiative,
        "package_revision": package.get("package_revision", f"{initiative}/pkg-1"),
        "package_digest": canonical_digest(package),
        "artifact_baseline": baseline_commit,
        "ticket_keys": sorted(str(unit["key"]) for unit in package["units"]),
        "workspaces": sorted(workspaces),
        "budget": deepcopy(dict(budget)),
        "stop_conditions": list(stop_conditions),
        "actor": deepcopy(dict(actor)),
        "immutable": True,
    }


def create_batch(package: Mapping[str, Any], *, actor: Mapping[str, Any], budget: Mapping[str, Any], stop_conditions: Sequence[str], workspaces: Sequence[str], baseline_commit: str, create_card: Callable[[dict[str, Any]], Mapping[str, Any]], batch_number: int = 1) -> dict[str, Any]:
    """Authorize and create legacy blocked cards, retaining batch lineage metadata."""
    batch = authorize_batch(package, actor=actor, budget=budget, stop_conditions=stop_conditions, workspaces=workspaces, baseline_commit=baseline_commit, batch_number=batch_number)
    enriched = deepcopy(dict(package))
    enriched["initiative_key"] = batch["initiative_key"]
    enriched["batch_metadata"] = batch
    def create_with_lineage(args: dict[str, Any]) -> Mapping[str, Any]:
        enriched_args = dict(args)
        enriched_args["metadata"] = {**args.get("metadata", {}), "initiative_key": batch["initiative_key"], "batch_key": batch["batch_key"], "package_digest": batch["package_digest"]}
        return create_card(enriched_args)
    cards = create_execution_cards(enriched, create_with_lineage)
    return {"batch": batch, "cards": cards}


__all__ = ["authorize_batch", "canonical_digest", "create_batch"]
