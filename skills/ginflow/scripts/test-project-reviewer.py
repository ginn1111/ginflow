#!/usr/bin/env python3
"""Project reviewer config: validate against profiles, fail closed."""
import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("pc", ROOT / "skills/ginflow/lib/project_config.py")
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)

PROFILES = ["default", "ginb", "gintary"]


def project(extra=""):
    d = Path(tempfile.mkdtemp(prefix="ginflow-reviewer-")).resolve()
    (d / ".ginflow.yaml").write_text(
        f"version: 1\nginflow:\n  board: b\n  workspace: {d}\n{extra}"
    )
    return d


def main():
    t = project("  reviewer:\n    profile: gintary\n")
    assert pc.reviewer_error(t, PROFILES) is None
    assert pc.configured_reviewer(t) == "gintary"
    t = project()
    assert pc.reviewer_error(t, PROFILES) is None
    assert pc.configured_reviewer(t) is None
    for extra, needle in [
        ("  reviewer:\n    profile: nobody\n", "not an installed"),
        ("  reviewer: gintary\n", "must be a mapping"),
        ("  reviewer:\n    profile: ''\n", "non-empty"),
        ("  reviewer:\n    profile: gintary\n    x: 1\n", "unknown"),
    ]:
        assert needle in pc.reviewer_error(project(extra), PROFILES), extra
    print("PASS: project reviewer config")


if __name__ == "__main__":
    main()
