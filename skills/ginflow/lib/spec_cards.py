"""Spec front matter -> Kanban card data. Stdlib only."""
from __future__ import annotations

import re
from pathlib import Path

KEY_RE = re.compile(r"^[A-Z][A-Z0-9]*(-[A-Z0-9]+)*-\d+$")
SEP = " \u2014 "


def front_matter(text: str) -> dict:
    # ponytail: flat `key: value` and `[a, b]` only; use a YAML parser if specs need nesting.
    m = re.match(r"---\n(.*?)\n---(?:\n|$)", text, re.S)
    out: dict = {}
    for line in (m.group(1).splitlines() if m else []):
        k, sep, v = line.partition(":")
        if not sep or line[:1] in " #":
            continue
        v = re.sub(r"\s+#.*$", "", v).strip()
        out[k.strip()] = [i.strip() for i in v[1:-1].split(",") if i.strip()] if v.startswith("[") else v
    return out


def section(text: str, name: str) -> str | None:
    m = re.search(rf"^## {re.escape(name)}[ \t]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else None


def load_spec(path: Path, root: Path) -> tuple[dict | None, list[str]]:
    """Return (spec, problems). Spec is None when problems exist."""
    text = path.read_text(encoding="utf-8")
    fm, errs, name = front_matter(text), [], str(path)
    key = fm.get("card", "")
    if not isinstance(key, str) or not KEY_RE.match(key):
        return None, [f"{name}: front matter `card` missing or not a valid key"]
    plan = root / "docs" / "plans" / f"{key}.md"
    if not plan.is_file():
        errs.append(f"{name}: missing plan docs/plans/{key}.md")
    if not fm.get("assignee") or not isinstance(fm["assignee"], str):
        errs.append(f"{name}: front matter `assignee` missing")
    blocked = fm.get("blocked_by", [])
    if not isinstance(blocked, list):
        errs.append(f"{name}: `blocked_by` must be a list like [KEY-1]")
        blocked = []
    for b in blocked:
        if not KEY_RE.match(b):
            errs.append(f"{name}: invalid blocked_by key {b!r}")
    problem, desired = section(text, "Problem"), section(text, "Desired behavior")
    acceptance = [m.group(1).strip() for m in re.finditer(r"^- \[[ xX]\]\s*(.+)$", section(text, "Acceptance criteria") or "", re.M)]
    if not problem:
        errs.append(f"{name}: missing ## Problem section")
    if not acceptance:
        errs.append(f"{name}: missing ## Acceptance criteria checklist")
    if not fm.get("scope"):
        errs.append(f"{name}: front matter `scope` missing")
    if errs:
        return None, errs
    h1 = re.search(r"^# (.+)$", text, re.M)
    title = re.sub(rf"^Spec\s*\u2014\s*(?:{re.escape(key)}:\s*)?", "", h1.group(1).strip()) if h1 else key
    para = " ".join((desired or problem or "").split("\n\n")[0].split())
    objective = re.split(r"(?<=[.!?])\s", para, maxsplit=1)[0]
    rel = lambda p: str(p.relative_to(root))
    links = [rel(path.resolve()), rel(plan)]
    return {
        "key": key, "assignee": fm["assignee"], "blocked_by": blocked, "title": f"{key}{SEP}{title}",
        "body": "\n".join([f"Objective: {objective}", "Scope:", f"- {fm['scope']}", "Acceptance:",
                           *[f"- {a}" for a in acceptance], "Links:", *[f"- {l}" for l in links]]),
        "links": links,
    }, []


def order(specs: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Topological key order; blocked_by keys outside `specs` are ignored. Returns (order, cycle_keys)."""
    pending = {k: {d for d in s["blocked_by"] if d in specs} for k, s in specs.items()}
    done: list[str] = []
    while pending:
        ready = sorted(k for k, deps in pending.items() if not deps - set(done))
        if not ready:
            return done, sorted(pending)
        for k in ready:
            done.append(k)
            del pending[k]
    return done, []


if __name__ == "__main__":
    assert front_matter("---\ncard: A-1\nblocked_by: [A-0, B-2]  # x\n---\n") == {"card": "A-1", "blocked_by": ["A-0", "B-2"]}
    mk = lambda *d: {"blocked_by": list(d)}
    assert order({"A-1": mk(), "A-2": mk("A-1"), "A-3": mk("A-1", "A-2")}) == (["A-1", "A-2", "A-3"], [])
    assert order({"A-1": mk("A-2"), "A-2": mk("A-1")})[1] == ["A-1", "A-2"]
    print("PASS: spec_cards")
