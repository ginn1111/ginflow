#!/usr/bin/env python3
"""kanban_request_review reviewer injection from ginflow.reviewer.profile."""
import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("gate", ROOT / "plugins/ginflow-gate/gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

CARD = {"id": "t_x", "title": "t", "objective": "o", "scope": ["s"], "acceptance": ["a"],
        "links": ["l"], "assignee": "ginb"}


def run(config, args):
    with tempfile.TemporaryDirectory() as d:
        if config is not None:
            (Path(d) / ".ginflow.yaml").write_text(config.format(d=d))
        gate.load_card = lambda *_a, **_k: CARD | {"workspace": f"dir:{d}"}
        gate.validate_completion = lambda *_a: None
        return gate.pre_tool_call("kanban_request_review", {"task_id": "t_x", "metadata": {}} | args)


CFG = "version: 1\nginflow:\n  board: b\n  workspace: {d}\n  reviewer:\n    profile: gintary\n"
assert run(CFG, {}) == {"action": "modify", "args": {"reviewer": "gintary"}}
assert run(CFG, {"reviewer": "other"}) is None  # explicit wins
assert run("version: 1\nginflow:\n  board: b\n  workspace: {d}\n", {}) is None  # no reviewer block
assert run(None, {}) is None  # no config file
print("PASS: reviewer injection")
