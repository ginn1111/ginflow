"""Spec front matter -> card data (CLOUD-1.4). Pure parsing; no Kanban or git access."""
from __future__ import annotations

import re
from pathlib import Path

KEY = re.compile(r"^[A-Z][A-Z0-9]*(-[A-Z0-9]+)*-\d+(\.\d+)*$")
ISSUE = re.compile(r"^([\w.-]+)/([\w.-]+)#(\d+)$")


class SpecError(ValueError):
    """A spec cannot become a card; the message is the `fail <file>:` reason."""


def front_matter(text: str) -> tuple[dict, str]:
    """(front matter dict, body). Front matter must start at byte 0."""
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        raise SpecError("no YAML front matter at byte 0")
    raw, body = m.groups()
    try:
        import yaml  # optional
        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            raise SpecError("front matter is not a mapping")
        return data, body
    except ImportError:
        pass
    except Exception as exc:  # yaml.YAMLError and friends: fall back to the minimal parser
        if isinstance(exc, SpecError):
            raise
    data = {}
    for line in raw.splitlines():
        if ":" not in line or line.startswith((" ", "#")):
            continue
        k, v = line.split(":", 1)
        v = re.sub(r"\s+#.*$", "", v).strip()
        if v.startswith("[") and v.endswith("]"):
            data[k.strip()] = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
        else:
            data[k.strip()] = v.strip("'\"")
    return data, body


def split_top(text: str) -> list[str]:
    """Split on `, ` outside parentheses."""
    out, depth, cur, i = [], 0, "", 0
    while i < len(text):
        ch = text[i]
        depth += (ch == "(") - (ch == ")" and depth > 0)
        if ch == "," and depth == 0 and text[i + 1:i + 2] == " ":
            out.append(cur.strip())
            cur, i = "", i + 2
            continue
        cur += ch
        i += 1
    out.append(cur.strip())
    return [x for x in out if x]


def section(body: str, name: str) -> list[str]:
    lines, grab = [], False
    for line in body.splitlines():
        if line.startswith("## "):
            grab = line[3:].strip().lower() == name.lower()
            continue
        if grab:
            lines.append(line)
    return lines


def first_sentence(lines: list[str]) -> str:
    fence = False
    for line in lines:
        if line.strip().startswith("```"):
            fence = not fence
            continue
        text = re.sub(r"^\s*(?:[-*]\s+|[A-Z]\d+\.\s+)", "", line).strip()
        if fence or not text:
            continue
        m = re.match(r"^(.*?[.!?])(?:\s|$)", text)
        return (m.group(1) if m else text).strip()
    return ""


def parse_issue(value) -> tuple[str, str, int] | None:
    if value in (None, ""):
        return None
    m = ISSUE.match(str(value))
    if not m:
        raise SpecError(f"issue {value!r} is not owner/repo#n")
    return m.group(1), m.group(2), int(m.group(3))


def load_spec(path: Path, repo: Path | None = None) -> dict:
    """Parse one spec; raise SpecError on the first problem. `repo` makes link paths relative."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecError(f"unreadable: {exc}") from exc
    fm, body = front_matter(text)
    key = fm.get("card")
    if not isinstance(key, str) or not KEY.match(key):
        raise SpecError(f"card {key!r} is missing or not a Card key")
    assignee = fm.get("assignee")
    if not isinstance(assignee, str) or not assignee.strip():
        raise SpecError("assignee is missing")
    blocked = fm.get("blocked_by") or []
    if isinstance(blocked, str):
        blocked = [blocked]
    if not isinstance(blocked, list) or not all(isinstance(b, str) and KEY.match(b) for b in blocked):
        raise SpecError(f"blocked_by {blocked!r} must be a list of Card keys")
    issue = parse_issue(fm.get("issue"))
    for needed in ("Problem", "Acceptance criteria"):
        if not any(line.startswith("## ") and line[3:].strip().lower() == needed.lower() for line in body.splitlines()):
            raise SpecError(f"missing section ## {needed}")
    acceptance = [re.sub(r"^\[[ xX]\]\s*", "", line.strip()[2:]).strip()
                  for line in section(body, "Acceptance criteria") if line.strip().startswith(("- ", "* "))]
    acceptance = [a for a in acceptance if a]
    if not acceptance:
        raise SpecError("## Acceptance criteria has no checklist items")
    objective = first_sentence(section(body, "Desired behavior")) or first_sentence(section(body, "Problem"))
    if not objective:
        raise SpecError("no text for Objective in ## Desired behavior or ## Problem")
    scope = split_top(str(fm.get("scope") or ""))
    if not scope:
        raise SpecError("scope is missing")
    h1 = next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), "")
    title = re.sub(rf"^Spec\s+[—-]\s+(?:{re.escape(key)}:\s*)?", "", h1).strip() or key
    root = Path(repo) if repo else path.parent.parent.parent
    plan = root / "docs" / "plans" / f"{key}.md"
    rel = lambda p: p.resolve().relative_to(root.resolve()).as_posix() if p.resolve().is_relative_to(root.resolve()) else str(p)
    return {"key": key, "assignee": assignee.strip(), "blocked_by": list(blocked), "issue": issue,
            "scope": scope, "title": f"{key} — {title}", "objective": objective, "acceptance": acceptance,
            "spec_path": path, "plan_path": plan, "spec_rel": rel(path), "plan_rel": rel(plan)}


def links(spec: dict) -> list[str]:
    out = [spec["spec_rel"], spec["plan_rel"]]
    if spec["issue"]:
        owner, repo, n = spec["issue"]
        out.append(f"https://github.com/{owner}/{repo}/issues/{n}")
    return out


def body_text(spec: dict) -> str:
    return "\n".join([f"Objective: {spec['objective']}", "Scope:", *(f"- {x}" for x in spec["scope"]),
                      "Acceptance:", *(f"- {x}" for x in spec["acceptance"]),
                      "Links:", *(f"- {x}" for x in links(spec))])


def idempotency_key(spec: dict, board: str) -> str:
    if spec["issue"]:
        owner, repo, n = spec["issue"]
        return f"gh:{owner}/{repo}#{n}:{spec['key']}"
    return f"card:{board}:{spec['key']}"


def order(specs: list[dict], existing_keys=()) -> list[dict]:
    """Specs in dependency order. SpecError on an unknown key or a cycle."""
    by_key = {s["key"]: s for s in specs}
    for s in specs:
        for b in s["blocked_by"]:
            if b not in by_key and b not in existing_keys:
                raise SpecError(f"{s['key']}: blocked_by {b} is not a given spec or an existing card")
    done, result, pending = set(), [], list(specs)
    while pending:
        ready = [s for s in pending if all(b in done or b not in by_key for b in s["blocked_by"])]
        if not ready:
            raise SpecError("dependency cycle among " + ", ".join(s["key"] for s in pending))
        for s in ready:
            result.append(s)
            done.add(s["key"])
            pending.remove(s)
    return result
