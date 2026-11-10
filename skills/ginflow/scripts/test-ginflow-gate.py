#!/usr/bin/env python3
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "plugins/ginflow-gate/__init__.py"

spec = importlib.util.spec_from_file_location(
    "ginflow_gate", PLUGIN, submodule_search_locations=[str(PLUGIN.parent)]
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules["ginflow_gate"] = module
spec.loader.exec_module(module)
validate_completion = module.validate_completion

card = {
    "id": "GATE-1",
    "title": "Gate",
    "objective": "Enforce completion",
    "scope": ["plugin"],
    "acceptance": ["bad completion rejected"],
    "workspace": "dir:/tmp/target",
    "status": "running",
    "assignee": "worker",
    "links": ["docs/specs/GATE-1.md"],
}
setattr(module.gate, "load_card", lambda task_id, board=None: card)

for tool_name in ("kanban_request_review", "kanban_complete"):
    blocked = module.pre_tool_call(tool_name, {"task_id": "GATE-1", "metadata": {}}, "", profile="worker")
    assert blocked["action"] == "block"
    assert blocked["message"].startswith("ginflow-gate: ")

    setattr(module.gate, "validate_completion", lambda card, metadata: None)
    allowed = module.pre_tool_call(
        tool_name,
        {
            "task_id": "GATE-1",
            "metadata": {
                "verification_result": {"commit": "abc", "command": "make test", "result": "passed"},
                "artifact_baseline": {"commit": "abc", "paths": ["docs/specs/GATE-1.md"]},
            },
        },
        "",
        profile="worker",
    )
    assert allowed is None

    setattr(module.gate, "validate_completion", lambda card, metadata: "linked artifact drift: docs/specs/GATE-1.md")
    blocked = module.pre_tool_call(
        tool_name,
        {
            "task_id": "GATE-1",
            "metadata": {
                "verification_result": {"commit": "abc", "command": "make test", "result": "passed"},
                "artifact_baseline": {"commit": "abc", "paths": ["docs/specs/GATE-1.md"]},
            },
        },
        "",
    )
    assert blocked["action"] == "block"
    assert "drift" in blocked["message"]

setattr(module.gate, "load_card", lambda task_id, board=None: (_ for _ in ()).throw(RuntimeError("DB unavailable")))
failed_closed = module.pre_tool_call("kanban_request_review", {"task_id": "GATE-1", "metadata": {}}, "")
assert failed_closed["action"] == "block"
assert "validation failed closed" in failed_closed["message"]

with tempfile.TemporaryDirectory(prefix="ginflow-gate-") as directory:
    target = Path(directory)
    brief = target / "docs/specs/GATE-1.md"
    brief.parent.mkdir(parents=True)
    brief.write_text("---\nstatus: completed\n---\n# Gate\n\n**Status: stale**\n")
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    subprocess.run(["git", "config", "user.name", "Ginflow Test"], cwd=target, check=True)
    subprocess.run(["git", "config", "user.email", "ginflow@example.test"], cwd=target, check=True)
    subprocess.run(["git", "add", "docs/specs/GATE-1.md"], cwd=target, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=target, check=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=target, text=True, capture_output=True, check=True
    ).stdout.strip()
    committed_card = card | {"workspace": f"dir:{target}"}
    metadata = {
        "verification_result": {"commit": commit, "command": "make test", "result": "passed"},
        "artifact_baseline": {"commit": commit, "paths": ["docs/specs/GATE-1.md"]},
    }
    assert validate_completion(committed_card, metadata) is None
    metadata["verification_result"]["commit"] = "mismatch"
    assert "must match" in validate_completion(committed_card, metadata)

print("ginflow gate rejection test passed")
