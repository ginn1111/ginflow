#!/usr/bin/env python3
"""kanban_request_review reviewer injection from ginflow.reviewer.profile."""
import importlib
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins"))
gate = importlib.import_module("ginflow-gate.gate")

CARD = {"id": "t_x", "title": "t", "objective": "o", "scope": ["s"], "acceptance": ["a"],
        "links": ["l"], "assignee": "ginb"}


def run(config, args):
    with tempfile.TemporaryDirectory() as d:
        if config is not None:
            (Path(d) / ".ginflow.yaml").write_text(config.format(d=d))
        gate.load_card = lambda *_a, **_k: CARD | {"workspace": f"dir:{d}"}
        gate.validate_completion = lambda *_a: None
        return gate.pre_tool_call("kanban_request_review", {"task_id": "t_x", "metadata": {}} | args)


CFG = "ginflow:\n  board: b\n  workspace: {d}\n  reviewer:\n    profile: gintary\n"
assert run(CFG, {}) == {"action": "modify", "args": {"reviewer": "gintary"}}
assert run(CFG, {"reviewer": "other"}) is None  # explicit wins
assert run("ginflow:\n  board: b\n  workspace: {d}\n", {}) is None  # no reviewer block
assert run(None, {}) is None  # no config file
print("PASS: reviewer injection")
