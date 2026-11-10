#!/usr/bin/env python3
"""kanban_block pre_tool_call guard: kind/required_action checks, trace-gated."""
import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins"))
br = importlib.import_module("ginflow-gate.block_routing")
br._load_task = lambda task_id, board: {"workspace_path": "/nonexistent"}


def call(args, tool="kanban_block"):
    return br._pre_tool_call(tool, args, "t_1")


os.environ["GINFLOW_LOG"] = "1"
for bad in ({"reason": "r"}, {"reason": "r", "kind": "bogus"}):
    res = call(bad)
    assert res and res["action"] == "block", bad
    assert all(k in res["message"] for k in ("needs_input", "capability", "transient", "dependency")), res
for kind in ("needs_input", "capability"):
    res = call({"kind": kind, "reason": "need key"})
    assert res and "required_action" in res["message"], res
    assert call({"kind": kind, "reason": "need key\nrequired_action: add API key"}) is None
assert call({"kind": "transient", "reason": "flaky"}) is None
assert call({"kind": "dependency", "reason": "waiting"}) is None
assert call({"reason": "r"}, tool="kanban_complete") is None
assert "Required action: add API key." in br.build_message("t", "x\nrequired_action: add API key", "p", 1)

os.environ["GINFLOW_LOG"] = "0"  # trace off: inactive
assert call({"reason": "r"}) is None
assert call({"kind": "needs_input", "reason": "r"}) is None
print("PASS: kanban_block guard")
