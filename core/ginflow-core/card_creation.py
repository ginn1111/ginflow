"""Build blocked Kanban cards from an approved Ginflow v2 package."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from execution_package import validate_package


CreateCard = Callable[[dict[str, Any]], Mapping[str, Any]]


def _lines(values: Any) -> str:
    if isinstance(values, (list, tuple)):
        return "\n".join(f"- {value}" for value in values)
    return f"- {values}"


def _links(package: Mapping[str, Any], unit: Mapping[str, Any] | None = None) -> list[str]:
    if unit and isinstance(unit.get("document"), Mapping):
        return [unit["document"]["path_or_url"]]  # document replaces Contract/Spec/Plan links
    links = package.get("links", {})
    result = []
    if isinstance(links, Mapping):
        for key in ("contract", "spec"):
            value = links.get(key)
            if isinstance(value, str) and value.strip():
                result.append(value)
        if unit:
            plans = links.get("plans", {})
            value = plans.get(unit.get("key")) if isinstance(plans, Mapping) else None
            if isinstance(value, str) and value.strip():
                result.append(value)
    return result


def _body(
    package: Mapping[str, Any],
    objective: str,
    scope: Any,
    acceptance: Any,
    verification: Any,
    dependencies: Any,
    links: list[str],
) -> str:
    lines = [
        f"Objective: {objective}",
        "Scope:",
        _lines(scope),
        "Acceptance:",
        _lines(acceptance),
        "Dependencies:",
        _lines(dependencies) if dependencies else "- none",
        "Verification:",
        _lines(verification),
        "Links:",
        *[f"- {link}" for link in links],
        f"Package baseline: {package['baseline']['commit']}",
    ]
    return "\n".join(lines)


def create_execution_cards(
    package: Mapping[str, Any], create_card: CreateCard
) -> dict[str, Any]:
    """Create exactly one blocked card per unit, then one blocked integration card.

    ``create_card`` receives native create arguments and returns a mapping with an
    ``id``. Callback is injected so this seam stays independent of Hermes CLI/API.
    """
    if package.get("workflow_version") != 2:
        raise ValueError("workflow_version must be 2")
    if package.get("contract", {}).get("state") != "approved":
        raise ValueError("package must be approved before card creation")
    validation = validate_package(package)
    if not validation["valid"]:
        raise ValueError("invalid execution package: " + "; ".join(validation["errors"]))
    baseline = package["baseline"]

    units = package.get("units", [])
    plans = {plan.get("unit_key"): plan for plan in package.get("plans", [])}
    created: dict[str, str] = {}
    cards: list[Mapping[str, Any]] = []
    for unit in units:
        key = unit["key"]
        plan = plans.get(key)
        if plan is None:
            raise ValueError(f"missing plan for unit: {key}")
        dependency_ids = [created[dependency] for dependency in unit.get("dependencies", [])]
        args = {
            "title": f"{key} — {package['initiative_key']}",
            "body": _body(package, f"{package['contract']['objective']} ({key})", unit["scope"], unit["acceptance"], plan["verification"], unit.get("dependencies", []), _links(package, unit)),
            "assignee": unit["owner"],
            "workspace": f"dir:{unit['workspace']}",
            "initial_status": "blocked",
            "goal_mode": True,
            "goal_max_turns": unit.get("goal_max_turns", 20),
            "parents": dependency_ids,
            "metadata": {"unit_key": key, "package_baseline": baseline["commit"],
                         **({"document": dict(unit["document"])} if "document" in unit else {})},
        }
        card = create_card(args)
        card_id = card.get("id")
        if not card_id:
            raise ValueError(f"card creator returned no id for unit: {key}")
        created[key] = str(card_id)
        cards.append(card)

    integration = create_card({
        "title": f"{package['initiative_key']} — Integration",
        "body": _body(package, package["contract"]["objective"], package["contract"]["boundaries"], package["contract"]["acceptance"], package["contract"]["verification"], list(created), _links(package)),
        "assignee": package.get("integration_owner", package["contract"].get("owner", "ginb")),
        "workspace": f"dir:{package.get('integration_workspace', package['units'][0]['workspace'])}",
        "initial_status": "blocked",
        "goal_mode": True,
        "goal_max_turns": package.get("integration_goal_max_turns", 20),
        "parents": list(created.values()),
        "metadata": {"integration": True, "package_baseline": baseline["commit"]},
    })
    if not integration.get("id"):
        raise ValueError("card creator returned no integration card id")
    return {"unit_cards": cards, "integration_card": integration, "baseline": baseline["commit"]}


__all__ = ["create_execution_cards"]
