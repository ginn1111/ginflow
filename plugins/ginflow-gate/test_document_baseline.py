#!/usr/bin/env python3
"""document_baseline gate tests for local provider documents."""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core/ginflow-core"))
from provider_document import build_provider_document, write_local_document  # noqa: E402

spec = importlib.util.spec_from_file_location("ginflow_gate_gate_doc", ROOT / "plugins/ginflow-gate/gate.py")
assert spec and spec.loader
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

PACKAGE = {
    "key": "DOC-1", "objective": "ship", "scope": ["core"], "acceptance": ["ok"],
    "contract": "c", "spec": "s", "plan": ["p"], "verification": ["make test"],
}
DOC = "docs/work-units/DOC-1.md"


def git(target, *args):
    return subprocess.run(["git", *args], cwd=target, text=True, capture_output=True, check=True).stdout.strip()


def main():
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        git(target, "init", "-q")
        git(target, "config", "user.name", "t")
        git(target, "config", "user.email", "t@example.test")
        doc = build_provider_document("local", PACKAGE, {})
        assert write_local_document(doc, target)["status"] == "written"
        git(target, "add", DOC)
        git(target, "commit", "-qm", "doc")
        commit = git(target, "rev-parse", "HEAD")
        card = {
            "id": "T-1", "title": "t", "objective": "o", "scope": ["s"], "acceptance": ["a"],
            "workspace": f"dir:{target}", "assignee": "ginb", "links": [DOC],
        }

        def meta(baseline, result="passed"):
            m = {
                "verification_result": {"commit": commit, "command": "make test", "result": result},
                "artifact_baseline": {"commit": commit, "paths": [DOC]},
            }
            if baseline is not None:
                m["document_baseline"] = baseline
            return m

        good = {"content_hash": doc["content_hash"], "commit": commit}
        assert gate.validate_completion(card, meta(good)) is None
        assert "document_baseline" in gate.validate_completion(card, meta(None))
        assert "content_hash" in gate.validate_completion(card, meta({"commit": commit}))
        assert "does not match" in gate.validate_completion(card, meta({**good, "content_hash": "0" * 64}))
        assert "passed" in gate.validate_completion(card, meta(good, "failed"))
        assert "not committed" in gate.validate_completion(card, meta({**good, "commit": "deadbeef"}))
        # drifted: committed content changed after hash was recorded
        (target / DOC).write_text(doc["body"] + "edit\n")
        git(target, "commit", "-qam", "drift")
        new = git(target, "rev-parse", "HEAD")
        drift = meta(good) | {"verification_result": {"commit": new, "command": "make test", "result": "passed"},
                              "artifact_baseline": {"commit": new, "paths": [DOC]}}
        assert gate.validate_completion(card, drift | {"document_baseline": {**good, "commit": new}}) \
            and "does not match" in gate.validate_completion(card, drift | {"document_baseline": {**good, "commit": new}})
        # uncommitted-only document: never in git
        (target / "docs/work-units/DOC-2.md").write_text(doc["body"])
        other = card | {"links": ["docs/work-units/DOC-2.md"]}
        assert "not committed" in gate.validate_completion(other, meta({**good, "commit": new}) | {
            "artifact_baseline": {"commit": commit, "paths": ["docs/work-units/DOC-2.md"]}})
    print("document baseline gate tests passed")


if __name__ == "__main__":
    main()
