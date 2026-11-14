#!/usr/bin/env python3
"""ginflow command. `ginflow init` sets up a project; each step prints `ok|set|fail <step>: <detail>`."""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "lib"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"ginflow_cli_{name}", LIB / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pc = _load("project_config")
publish = _load("publish")
spec_cards = _load("spec_cards")
core = _load("harness_core")


def run(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(argv, 127, "", str(exc))


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return run(["git", "-C", str(repo), *args])


def behind_error(repo: Path) -> str | None:
    """None when the local publish target is not behind its remote; else a one-line problem."""
    settings = pc.configured_publish(repo) or {}
    target, remote = settings.get("target", "main"), settings.get("remote", "origin")
    ref = f"{remote}/{target}"
    if git(repo, "fetch", remote).returncode != 0 or git(repo, "rev-parse", "--verify", "-q", f"refs/remotes/{ref}").returncode != 0:
        return f"no {ref}"
    behind = git(repo, "rev-list", "--count", f"{target}..{ref}")
    if behind.returncode != 0:
        return f"no local {target}"
    count = int(behind.stdout.strip() or 0)
    return f"behind {ref} by {count}" if count else None


class Init:
    def __init__(self) -> None:
        self.failed = False

    def say(self, status: str, step: str, detail: str) -> None:
        print(f"{status} {step}: {detail}")
        self.failed |= status == "fail"

    def boards(self) -> dict[str, dict]:
        out = run(["hermes", "kanban", "boards", "list", "--json"])
        try:
            return {b["slug"]: b for b in json.loads(out.stdout)} if out.returncode == 0 else {}
        except (ValueError, KeyError, TypeError):
            return {}

    def workdir_state(self, board: str, repo: Path) -> str:
        """'ok' | 'unset' | 'missing' | other path."""
        info = self.boards().get(board)
        if info is None:
            return "missing"
        current = info.get("default_workdir")
        if not current:
            return "unset"
        return "ok" if Path(current).resolve() == repo else str(current)

    def create_board(self, name: str, repo: Path) -> bool:
        if name in self.boards():
            return False
        return run(["hermes", "kanban", "boards", "create", name, "--default-workdir", str(repo)]).returncode == 0

    def context(self, repo: Path, args) -> str | None:
        """Resolve board; return its name, or None after a `fail` line."""
        if pc.config_exists(repo):
            error = pc.context_error(repo)
            if error:
                self.say("fail", "context", error)
                return None
            board = pc.configured_context(repo)["board"]
            self.say("ok", "context", f".ginflow.yaml names {board}")
            return board
        if bool(args.board) == bool(args.new_board):
            self.say("fail", "context", "no .ginflow.yaml; pass exactly one of --board NAME or --new-board NAME")
            return None
        name = args.board or args.new_board
        if args.board:
            state = self.workdir_state(name, repo)
            if state == "missing":
                self.say("fail", "context", f"board {name} does not exist")
                return None
            if state not in ("ok", "unset"):
                self.say("fail", "workdir", f"board {name} default_workdir is {state}, not {repo}")
                return None
        try:
            pc.initialize_context(
                repo, choice="current" if args.board else "new", current_board=args.board,
                board_name=args.new_board, create_board=lambda n: self.create_board(n, repo) or None,
            )
        except pc.ContextInitializationError as exc:
            self.say("fail", "context", str(exc))
            return None
        self.say("set", "context", f"wrote .ginflow.yaml with board {name}")
        return name

    def workdir(self, board: str, repo: Path) -> None:
        state = self.workdir_state(board, repo)
        if state == "ok":
            self.say("ok", "workdir", str(repo))
        elif state == "unset":
            done = run(["hermes", "kanban", "boards", "set-default-workdir", board, str(repo)]).returncode == 0
            self.say("set" if done else "fail", "workdir", str(repo))
        elif state == "missing":
            self.say("fail", "workdir", f"board {board} does not exist")
        else:
            self.say("fail", "workdir", f"board {board} default_workdir is {state}, not {repo}")

    def reviewer(self, repo: Path, profile: str | None) -> None:
        try:
            if profile and pc.configured_reviewer(repo) != profile:
                if profile not in pc.installed_profiles():
                    return self.say("fail", "reviewer", f"{profile!r} is not an installed Hermes profile")
                if not pc.persist_reviewer(repo, profile):
                    return self.say("fail", "reviewer", "unable to persist reviewer")
            reviewer, written = pc.seed_default_reviewer(
                repo, installed_profiles=pc.installed_profiles(), current=pc.hermes_default_reviewer())
        except (pc.ReviewerConfigError, OSError, subprocess.SubprocessError) as exc:
            return self.say("fail", "reviewer", str(exc))
        if reviewer is None:
            self.say("ok", "reviewer", "not configured")
        else:
            self.say("set" if written else "ok", "reviewer", reviewer)

    def worker(self, repo: Path, spec: str | None) -> None:
        if not spec:
            return
        parts = spec.split(":")
        if len(parts) != 3 or not all(p.strip() for p in parts):
            return self.say("fail", "worker", "--worker needs PROFILE:PROVIDER:MODEL")
        wanted = dict(zip(pc.WORKER_FIELDS, (p.strip() for p in parts)))
        if pc.configured_worker(repo) == wanted:
            changed = False
        elif pc.persist_worker_defaults(repo, **wanted) is None:
            return self.say("fail", "worker", "unable to persist worker defaults")
        else:
            changed = True
        try:
            resolved = pc.resolve_worker_dispatch(repo)
        except pc.WorkerDefaultsError as exc:
            return self.say("fail", "worker", str(exc))
        self.say("set" if changed else "ok", "worker", " ".join(f"{k}={v}" for k, v in resolved.items()))

    def notify(self, repo: Path) -> None:
        context = pc.load_config(repo).get("ginflow", {})
        error = pc.notify_error(context) if isinstance(context, dict) else None
        self.say("fail" if error else "ok", "notify", error or "valid")

    def auth(self, repo: Path) -> None:
        error = pc.publish_error(repo)
        if error:
            return self.say("fail", "auth", error)
        settings = pc.configured_publish(repo)
        if not settings:
            return self.say("ok", "auth", "publish not configured")
        result = run(publish.build_auth_argv(settings["provider"]))
        self.say("ok" if result.returncode == 0 else "fail", "auth", f"{settings['provider']} auth status")

    def main_branch(self, repo: Path) -> None:
        error = behind_error(repo)
        settings = pc.configured_publish(repo) or {}
        ref = f"{settings.get('remote', 'origin')}/{settings.get('target', 'main')}"
        self.say("fail" if error else "ok", "main", error or f"{settings.get('target', 'main')} up to date with {ref}")

    def dispatcher(self) -> None:
        out = run(["hermes", "gateway", "status"])
        running = out.returncode == 0 and "running" in out.stdout.lower() and "not running" not in out.stdout.lower()
        self.say("ok" if running else "fail", "dispatcher", "gateway running" if running else "gateway not running")

    def run(self, args) -> int:
        top = git(Path(args.project).expanduser().resolve(), "rev-parse", "--show-toplevel")
        if top.returncode != 0:
            self.say("fail", "context", f"{args.project} is not a git repository")
            return 1
        repo = Path(top.stdout.strip()).resolve()
        board = self.context(repo, args)
        if board is not None and not self.failed:
            self.workdir(board, repo)
        if not self.failed:  # nothing is rewritten after a failed context/workdir
            self.reviewer(repo, args.reviewer)
            self.worker(repo, args.worker)
        self.notify(repo) if pc.config_exists(repo) else None
        self.auth(repo) if pc.config_exists(repo) else None
        self.main_branch(repo)
        self.dispatcher()
        return 1 if self.failed else 0


HARNESS = Path(__file__).with_name("validate-harness.py")


def kanban(board: str, *args: str) -> subprocess.CompletedProcess:
    return run(["hermes", "kanban", "--board", board, *args])


def kanban_json(board: str, *args: str):
    out = kanban(board, *args, "--json")
    if out.returncode != 0:
        raise RuntimeError((out.stderr or out.stdout).strip() or f"exit {out.returncode}")
    return json.loads(out.stdout)


def cards_create(args) -> int:
    top = git(Path(args.project).expanduser().resolve(), "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        print(f"fail: {args.project} is not a git repository")
        return 1
    repo = Path(top.stdout.strip()).resolve()
    errors: list[str] = []
    board = pc.resolve_board(repo, args.board)
    info = Init().boards().get(board or "")
    if not info:
        errors.append(f"board {board} does not exist" if board else "no board: pass --board or run `ginflow init`")
    elif not info.get("default_workdir"):
        errors.append(f"board {board} has no default_workdir; run `ginflow init`")
    behind = behind_error(repo)
    if behind:
        errors.append(f"main: {behind}")
    specs: dict[str, dict] = {}
    for path in args.specs:
        spec, problems = spec_cards.load_spec(Path(path).resolve(), repo)
        errors += problems
        if spec and spec["key"] in specs:
            errors.append(f"{path}: duplicate card key {spec['key']}")
        elif spec:
            specs[spec["key"]] = spec
            if spec["assignee"] not in pc.installed_profiles():
                errors.append(f"{path}: assignee {spec['assignee']!r} is not an installed Hermes profile")
    existing: dict[str, dict] = {}
    if board and info and not errors:
        try:
            for card in kanban_json(board, "list"):
                key = card["title"].split(spec_cards.SEP)[0]
                if card["title"].startswith(key + spec_cards.SEP):
                    existing.setdefault(key, card)
        except (RuntimeError, ValueError, KeyError) as exc:
            errors.append(f"cannot list board {board}: {exc}")
    for key, spec in specs.items():
        for dep in spec["blocked_by"]:
            if dep not in specs and dep not in existing and not errors:
                errors.append(f"{key}: blocked_by {dep} is neither a given spec nor a card on the board")
    sequence, cycle = spec_cards.order(specs)
    if cycle:
        errors.append("dependency cycle among: " + ", ".join(cycle))
    if errors:
        print("\n".join(f"fail: {e}" for e in errors))
        return 1

    assert board
    ids = {k: c["id"] for k, c in existing.items()}
    result: dict[str, dict] = {}
    new: list[str] = []
    code = 0

    def emit() -> None:
        print(json.dumps([{"key": k, **result[k]} for k in sequence if k in result], indent=2))

    for key in sequence:
        spec = specs[key]
        if key in existing:
            result[key] = {"id": ids[key], "created": False}
            continue
        made = kanban(board, "create", spec["title"], "--body", spec["body"], "--assignee", spec["assignee"],
                      "--workspace", "worktree", "--initial-status", "blocked", "--json")
        if made.returncode != 0:
            print(f"fail: create {key}: {(made.stderr or made.stdout).strip()}", file=sys.stderr)
            emit()
            return 1
        ids[key] = json.loads(made.stdout)["id"]
        result[key] = {"id": ids[key], "created": True}
        new.append(key)
    for key in sequence:
        if key not in new:
            continue
        have = set(kanban_json(board, "show", ids[key]).get("parents", []))
        for dep in specs[key]["blocked_by"]:
            if ids[dep] not in have and kanban(board, "link", ids[dep], ids[key]).returncode != 0:
                print(f"fail: link {dep} -> {key}", file=sys.stderr)
                code = 1
    commit = git(repo, "rev-parse", "HEAD").stdout.strip()
    for key in new:
        check = run([sys.executable, str(HARNESS), "--target", str(repo), "--board", board, "--kanban-task-id", ids[key],
                     "--baseline-commit", commit, *[a for p in specs[key]["links"] for a in ("--baseline-path", p)], "--json"])
        try:
            report = json.loads(check.stdout)
            failed = [r["message"] for s in report["subsystems"].values() for r in s["checks"]
                      if not r["pass"] and r.get("severity") == "blocker"]
        except (ValueError, KeyError, TypeError):
            failed = ["harness unavailable"]
        if failed:
            kanban(board, "comment", ids[key], "ginflow cards create: kept blocked; failed check: " + "; ".join(failed))
            code = 1
        elif kanban(board, "unblock", ids[key]).returncode != 0:
            code = 1
    cards = {c["id"]: c for c in kanban_json(board, "list")}
    for key in sequence:
        card = cards.get(ids[key], {})
        result[key]["status"] = card.get("status")
        result[key]["parents"] = specs[key]["blocked_by"]
    emit()
    return code


PUBLISHED = re.compile(r"^ginflow-publish: (https?://\S+?)(?: \(updated\))?$")
PR_URL = re.compile(r"^https?://[^/]+/([^/]+/[^/]+)/pull/(\d+)")
FB_TITLE = re.compile(r"^(\S+)-fb(\d+) — PR #(\d+) feedback$")
SYNCED = re.compile(r"^\[ginflow-pr\] synced=(\S+)")


def _ts(text: str) -> float:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


class PrSync:
    """`ginflow pr sync`: PR feedback becomes a follow-up card on the PR head branch (PRFB-1)."""

    def __init__(self, board: str | None, repo: Path) -> None:
        self.board, self.repo, self.failed = board, repo, False

    def kb(self, *args: str):
        return core.kanban_json(self.board, *args)

    def kb_run(self, *args: str) -> str:
        out = core.kanban_run(self.board, *args)
        if out.returncode:
            raise RuntimeError(f"kanban {args[0]}: {(out.stderr or out.stdout).strip()}")
        return out.stdout

    def gh(self, *args: str) -> str:
        out = run(["gh", *args], self.repo)
        if out.returncode:
            raise RuntimeError(f"gh {' '.join(args[:2])}: {(out.stderr or out.stdout).strip()}")
        return out.stdout

    def feedback(self, url: str, since: float) -> tuple[dict, list[str]]:
        pr = json.loads(self.gh("pr", "view", url, "--json", "state,headRefName,reviews,comments"))
        slug, number = PR_URL.match(url).groups()
        raw = []  # (when, who, where, text)
        for r in pr.get("reviews") or []:
            text = (r.get("body") or "").strip() or ("changes requested" if r.get("state") == "CHANGES_REQUESTED" else "")
            raw.append((r.get("submittedAt"), (r.get("author") or {}).get("login", "?"), "review", text))
        for c in pr.get("comments") or []:
            raw.append((c.get("createdAt"), (c.get("author") or {}).get("login", "?"), "comment", (c.get("body") or "").strip()))
        for c in json.loads(self.gh("api", f"repos/{slug}/pulls/{number}/comments") or "[]"):
            raw.append((c.get("created_at"), (c.get("user") or {}).get("login", "?"),
                        f"{c.get('path')}:{c.get('line') or c.get('original_line') or '?'}", (c.get("body") or "").strip()))
        lines = [f"{who} {where}: {text[:300]}".replace("\n", " ")
                 for when, who, where, text in sorted(r for r in raw if r[0])
                 if text and not text.startswith("[ginflow]") and _ts(when) > since]
        return pr, lines

    def open_fb(self, data: dict, number: str) -> tuple[str | None, int]:
        """(open fb card id for this PR, count of fb cards)."""
        open_id, count = None, 0
        for cid in data.get("children") or []:
            task = self.kb("show", cid, "--json")["task"]
            if m := FB_TITLE.match(task["title"]):
                count += 1
                if m.group(3) == number and task["status"] not in ("done", "archived"):
                    open_id = cid
        return open_id, count

    def free_branch(self, head: str) -> str | None:
        """Remove a clean worktree holding `head`; return a reason when it is dirty."""
        for block in git(self.repo, "worktree", "list", "--porcelain").stdout.split("\n\n")[1:]:  # [0] is main
            info = dict(line.split(" ", 1) for line in block.splitlines() if " " in line)
            if info.get("branch") == f"refs/heads/{head}":
                if git(info["worktree"], "status", "--porcelain").stdout.strip():
                    return f"worktree {info['worktree']} on {head} is dirty"
                git(self.repo, "worktree", "remove", info["worktree"])
        return None

    def sync_card(self, tid: str) -> None:
        data = self.kb("show", tid, "--json")
        task, url, since, finished = data["task"], None, float(data["task"].get("completed_at") or 0), False
        for c in data.get("comments") or []:
            body = str(c.get("body") or "")
            if m := PUBLISHED.match(body):
                url = m.group(1)
            elif m := SYNCED.match(body):
                since = max(since, _ts(m.group(1)))
            elif body.startswith(("[ginflow-pr] merged", "[ginflow-pr] closed")):
                finished = True
        if not url or finished or FB_TITLE.match(task["title"]):
            return
        if not PR_URL.match(url):
            return print(f"skip {url}: provider gitlab not supported yet")
        pr, lines = self.feedback(url, since)
        if pr.get("state") in ("MERGED", "CLOSED"):
            self.kb_run("comment", tid, f"[ginflow-pr] {pr['state'].lower()}")
            return
        if not lines:
            return print(f"ok {tid}: no new feedback")
        number = PR_URL.match(url).group(2)
        open_id, count = self.open_fb(data, number)
        if open_id:
            self.kb_run("comment", open_id, "[ginflow-pr] new feedback:\n" + "\n".join(f"- {x}" for x in lines))
            print(f"set {tid}: appended {len(lines)} to {open_id}")
        else:
            self.create_fb(task, pr["headRefName"], number, count + 1, lines)
        self.kb_run("comment", tid, f"[ginflow-pr] synced={datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ} items={len(lines)}")

    def create_fb(self, task: dict, head: str, number: str, n: int, lines: list[str]) -> None:
        fields = core.parse_card_body(task.get("body"))
        body = "\n".join(["Objective: address PR review feedback", "Scope:", *(f"- {x}" for x in fields["scope"]),
                          "Acceptance:", *(f"- {x}" for x in lines), "- `make lint test` passes",
                          "Links:", *(f"- {x}" for x in fields["links"])])
        dirty = self.free_branch(head)
        title = f"{task['title'].split(' — ')[0].strip()}-fb{n} — PR #{number} feedback"
        args = ["create", title, "--body", body, "--workspace", "worktree", "--branch", head,
                "--initial-status", "blocked", "--json"]
        if task.get("assignee"):
            args += ["--assignee", task["assignee"]]
        fid = json.loads(self.kb_run(*args))["id"]
        self.kb_run("link", task["id"], fid)
        if dirty:
            self.kb_run("comment", fid, f"[ginflow-pr] needs_input: {dirty}")
            self.kb_run("block", fid, "--kind", "needs_input", f"required_action: clean {dirty}")
        else:
            self.kb_run("unblock", fid)
        print(f"set {task['id']}: created {fid} {title}")

    def run(self) -> int:
        for task in self.kb("list", "--status", "done", "--json"):
            try:
                self.sync_card(task["id"])
            except Exception as exc:  # one PR failing must not stop the rest
                self.failed = True
                print(f"fail {task['id']}: {exc}")
        return 1 if self.failed else 0


def pr_sync(args) -> int:
    top = git(Path(args.project).expanduser().resolve(), "rev-parse", "--show-toplevel")
    if top.returncode:
        print(f"fail context: {args.project} is not a git repository")
        return 1
    repo = Path(top.stdout.strip()).resolve()
    ok = pc.config_exists(repo) and not pc.context_error(repo)
    return PrSync(args.board or (pc.configured_context(repo)["board"] if ok else None), repo).run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ginflow")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="set up a project: context, board workdir, reviewer, checks")
    init.add_argument("--project", default=".")
    init.add_argument("--board", help="use existing Kanban board")
    init.add_argument("--new-board", help="create Kanban board with default workdir")
    init.add_argument("--worker", help="PROFILE:PROVIDER:MODEL")
    init.add_argument("--reviewer", help="reviewer profile to record in .ginflow.yaml")
    cards = sub.add_parser("cards", help="build Kanban cards from spec front matter").add_subparsers(dest="cards_command", required=True)
    create = cards.add_parser("create", help="create linked, blocked-until-ready cards from specs")
    create.add_argument("--project", default=".")
    create.add_argument("--board", help="Kanban board (default: .ginflow.yaml)")
    create.add_argument("specs", nargs="+", metavar="SPEC")
    pr = sub.add_parser("pr", help="pull request commands").add_subparsers(dest="pr_command", required=True)
    sync = pr.add_parser("sync", help="turn new PR review comments into follow-up cards")
    sync.add_argument("--project", default=".")
    sync.add_argument("--board")
    args = parser.parse_args(argv)
    if args.command == "cards":
        return cards_create(args)
    return pr_sync(args) if args.command == "pr" else Init().run(args)


if __name__ == "__main__":
    sys.exit(main())
