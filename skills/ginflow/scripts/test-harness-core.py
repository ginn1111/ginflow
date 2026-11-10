#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "core/ginflow-core/harness_core.py"

spec = importlib.util.spec_from_file_location("harness_core", CORE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

fields = module.parse_card_body(
    "Objective: Ship gate\nScope:\n- plugin\nAcceptance:\n- rejects bad completion\nLinks:\n- docs/specs/GATE-1.md"
)
assert fields == {
    "objective": "Ship gate",
    "scope": ["plugin"],
    "acceptance": ["rejects bad completion"],
    "links": ["docs/specs/GATE-1.md"],
}
print("ginflow harness core test passed")

with TemporaryDirectory() as temp_dir:
    target = Path(temp_dir)
    artifact = target / "docs/specs/GINFLOW-ROUTING.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("# Fixture\n")
    subprocess.run(["git", "init", "--quiet"], cwd=target, check=True)
    subprocess.run(["git", "add", str(artifact)], cwd=target, check=True)
    subprocess.run(
        [
            "git", "-c", "user.name=Ginflow Test", "-c",
            "user.email=ginflow-test@example.invalid", "commit", "--quiet",
            "-m", "Add fixture",
        ],
        cwd=target,
        check=True,
    )
    startup = module.startup_gate({
        "id": "START-1", "title": "Start", "objective": "x", "scope": ["x"],
        "acceptance": ["x"], "assignee": "ginb", "links": [str(artifact.relative_to(target))],
        "workspace": "dir:" + str(target), "status": "next",
    }, target, target)
    assert startup["route"] == "ready_to_start"
    assert startup["transition_required"] is True
print("ginflow startup gate test passed")
