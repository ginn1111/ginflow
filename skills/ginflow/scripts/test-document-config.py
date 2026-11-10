#!/usr/bin/env python3
"""Document provider config: strict validation, adaptive resolution, migration."""
import importlib.util
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("pc", ROOT / "skills/ginflow/lib/project_config.py")
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)

T1, P1 = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
SM = {k: f"S-{k}" for k in pc.STATUS_KEYS}
GH = {"provider": "github", "github": {"repo": "o/n"}, "status_map": SM}
LN = {"provider": "linear", "linear": {"team": T1, "project": P1}, "status_map": SM}


def project(documents=None, extra=""):
    d = Path(tempfile.mkdtemp(prefix="ginflow-docs-")).resolve()
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    (d / ".ginflow.yaml").write_text(f"version: 1\nginflow:\n  board: b\n  workspace: {d}\n{extra}")
    if documents:
        pc.set_documents(d, documents)
    return d


def stops(fn, needle):
    try:
        fn()
    except pc.DocumentConfigError as exc:
        assert needle in str(exc), str(exc)
        return
    raise AssertionError(f"expected stop: {needle}")


def bad(block, needle):
    assert needle in (pc.documents_block_error(block) or ""), (block, needle)


def main():
    # config validation
    for ok in ({"provider": "adaptive"}, {"provider": "local"}, GH, LN):
        assert pc.documents_block_error(ok) is None, ok
    bad("x", "mapping")
    bad({"provider": "jira"}, "provider must be")
    bad({"provider": "local", "x": 1}, "unknown")
    bad({"provider": "local", "status_map": SM}, "not allowed")
    bad({**GH, "github": {"repo": "bad"}}, "owner/name")
    bad({**GH, "status_map": {**SM, "start": ""}}, "start")
    bad({**GH, "status_map": {k: v for k, v in SM.items() if k != "complete"}}, "complete")
    bad({**GH, "status_map": {**SM, "x": "y"}}, "unknown")
    bad({"provider": "github", "github": {"repo": "o/n"}}, "status_map is required")
    bad({**LN, "linear": {"team": "ENG"}}, "stable Linear ID")
    bad({**LN, "linear": {"project": P1}}, "team")

    # save preserves unrelated keys, no credentials needed
    d = project(extra="  worker:\n    profile: p\n    provider: q\n    model: m\n")
    pc.set_documents(d, GH)
    data = pc.load_config(d)
    assert data["ginflow"]["worker"]["model"] == "m" and data["ginflow"]["documents"]["github"]["repo"] == "o/n"
    assert pc.documents_error(d) is None
    stops(lambda: pc.set_documents(d, {"provider": "x"}), "provider must be")
    assert pc.load_config(d) == data  # failed save leaves file unchanged

    # explicit provider report
    rep = pc.resolve_documents(project(LN))
    assert rep["effective"] == {"provider": "linear", "team": T1, "project": P1}, rep
    assert rep["destination"].startswith("linear:") and rep["readiness"] == "ready"

    # adaptive: no evidence, precedence, conflict, linked, canonical refs
    d = project({"provider": "adaptive"})
    stops(lambda: pc.resolve_documents(d), "no ginflow-docs evidence")
    (d / "AGENTS.md").write_text("x\nginflow-docs: provider=github repo=a/b\n")
    (d / ".hermes.md").write_text("ginflow-docs: provider=local\n")
    rep = pc.resolve_documents(d)
    assert rep["effective"] == {"provider": "github", "repo": "a/b"} and rep["evidence"] == {"file": "AGENTS.md", "line": 2}
    assert rep["configured"] == "adaptive"
    (d / "AGENTS.md").unlink()
    assert pc.resolve_documents(d)["effective"]["provider"] == "local"
    (d / ".hermes.md").unlink()
    (d / "L.md").write_text("ginflow-docs: provider=github repo=a/b\n")
    (d / "R.md").write_text("ginflow-docs: provider=local\n")
    assert pc.resolve_documents(d, linked_docs=["L.md"], canonical_refs=["R.md"])["effective"]["repo"] == "a/b"
    assert pc.resolve_documents(d, canonical_refs=["R.md"])["effective"]["provider"] == "local"
    (d / "L2.md").write_text("ginflow-docs: provider=local\n")
    stops(lambda: pc.resolve_documents(d, linked_docs=["L.md", "L2.md"]), "conflicting")
    (d / "AGENTS.md").write_text("ginflow-docs: provider=jira\n")
    stops(lambda: pc.resolve_documents(d), "provider must be")
    (d / "AGENTS.md").write_text("ginflow-docs: provider=github\n")
    stops(lambda: pc.resolve_documents(d, origin=lambda w: None), "GitHub repo")
    assert pc.resolve_documents(d, origin=lambda w: "x/y")["effective"]["repo"] == "x/y"

    # Linear name resolution via injected resolver
    (d / "AGENTS.md").write_text("ginflow-docs: provider=linear team=ENG\n")
    stops(lambda: pc.resolve_documents(d), "stable ID")
    rep = pc.resolve_documents(d, linear_resolver=lambda kind, name: T1)
    assert rep["effective"] == {"provider": "linear", "team": T1}
    stops(lambda: pc.resolve_documents(d, linear_resolver=lambda k, n: "not-an-id"), "stable ID")

    # readiness fails closed; save never needs it
    assert pc.resolve_documents(project(GH), readiness=lambda p: "run gh auth login")["readiness"] == "run gh auth login"
    stops(lambda: pc.require_ready("github", lambda p: "run gh auth login"), "gh auth login")
    pc.require_ready("github", lambda p: None)
    pc.require_ready("local", lambda p: "never")

    # migration: preview, approval, backup, ignored, malformed stays read-only
    d = project()
    (d / ".ginflow.yaml").write_text("version: 0\nboard: old\n")
    new = {"version": 1, "ginflow": {"board": "b", "workspace": str(d), "documents": GH}}
    stops(lambda: pc.set_documents(d, GH), "version")
    preview = pc.preview_migration(d, new)
    assert "-version: 0" in preview and "+version: 1" in preview
    before = (d / ".ginflow.yaml").read_text()
    stops(lambda: pc.apply_migration(d, new, approved=False), "approval")
    assert (d / ".ginflow.yaml").read_text() == before
    backup = pc.apply_migration(d, new, approved=True, now=lambda: "20260101T000000Z")
    assert backup.read_text() == before and backup.parent == d / ".ginflow" / "migrations"
    assert pc.context_error(d) is None and pc.documents_error(d) is None
    ignored = subprocess.run(["git", "-C", str(d), "check-ignore", "-q", str(backup)])
    assert ignored.returncode == 0
    stops(lambda: pc.apply_migration(d, {"version": 1, "ginflow": {"documents": {"provider": "x"}}}, approved=True), "provider must be")
    print("PASS: document config")


if __name__ == "__main__":
    main()
