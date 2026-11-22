#!/usr/bin/env python3
"""ginflow command. `ginflow init` sets up a project; each step prints `ok|set|fail <step>: <detail>`."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shlex
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
core = _load("harness_core")
gh_app = _load("gh_app")
sc = _load("spec_cards")


def run(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(argv, 127, "", str(exc))


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return run(["git", "-C", str(repo), *args])


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

    def exclude(self, repo: Path) -> None:
        """Keep `.ginflow.yaml` and `.hermes.md` out of git via info/exclude; never touch `.gitignore`."""
        names = (".ginflow.yaml", ".hermes.md")
        if git(repo, "ls-files", "--error-unmatch", ".ginflow.yaml").returncode == 0:
            return self.say("fail", "exclude", ".ginflow.yaml is tracked; run git rm --cached .ginflow.yaml")
        common = git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
        if common.returncode != 0:
            return self.say("fail", "exclude", "cannot resolve git common dir")
        path = Path(common.stdout.strip()) / "info" / "exclude"
        try:
            text = path.read_text(encoding="utf-8") if path.exists() else ""
            present = {line.strip().lstrip("/") for line in text.splitlines()}
            missing = [n for n in names if n not in present]
            if missing:
                path.parent.mkdir(parents=True, exist_ok=True)
                prefix = "" if not text or text.endswith("\n") else "\n"
                path.write_text(text + prefix + "".join(f"{n}\n" for n in missing), encoding="utf-8")
        except OSError as exc:
            return self.say("fail", "exclude", str(exc))
        self.say("set" if missing else "ok", "exclude", f"added {' '.join(missing)}" if missing else "present")

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
        settings = pc.configured_publish(repo) or {}
        target, remote = settings.get("target", "main"), settings.get("remote", "origin")
        ref = f"{remote}/{target}"
        if git(repo, "fetch", remote).returncode != 0 or git(repo, "rev-parse", "--verify", "-q", f"refs/remotes/{ref}").returncode != 0:
            return self.say("fail", "main", f"no {ref}")
        behind = git(repo, "rev-list", "--count", f"{target}..{ref}")
        if behind.returncode != 0:
            return self.say("fail", "main", f"no local {target}")
        count = int(behind.stdout.strip() or 0)
        if count:
            return self.say("fail", "main", f"behind {ref} by {count}")
        self.say("ok", "main", f"{target} up to date with {ref}")

    def sync(self, repo: Path, board: str | None) -> None:
        if not board:
            return
        name, home = f"ginflow-pr-sync:{board}", Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
        script = home / "scripts" / f"ginflow-pr-sync-{board}.sh"
        want = (f"#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(Path(__file__).resolve()))} "
                f"pr sync --board {shlex.quote(board)} --project {shlex.quote(str(repo))}\n")
        try:
            jobs = json.loads((home / "cron/jobs.json").read_text())["jobs"]
        except (OSError, ValueError, KeyError):
            jobs = []
        if any(j.get("name") == name for j in jobs):
            same = script.exists() and script.read_text() == want
            return self.say("ok" if same else "fail", "sync", name if same else f"{name} exists with a different command")
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(want)
        script.chmod(0o755)
        target = pc.configured_notify_target(repo) or "origin"
        made = run(["hermes", "cron", "create", "every 10m", "--name", name, "--script", script.name, "--no-agent", "--deliver", target])
        self.say("set" if made.returncode == 0 else "fail", "sync", name if made.returncode == 0 else (made.stderr or made.stdout).strip())

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
            self.exclude(repo)
        if board is not None and not self.failed:
            self.workdir(board, repo)
        if not self.failed:  # nothing is rewritten after a failed context/workdir
            self.reviewer(repo, args.reviewer)
            self.worker(repo, args.worker)
        self.notify(repo) if pc.config_exists(repo) else None
        self.auth(repo) if pc.config_exists(repo) else None
        self.main_branch(repo)
        self.sync(repo, board) if not self.failed else None
        self.dispatcher()
        return 1 if self.failed else 0


PUBLISHED = re.compile(r"^ginflow-publish: (https?://\S+?)(?: \(updated\))?$")
PR_URL = re.compile(r"^https?://[^/]+/([^/]+/[^/]+)/pull/(\d+)")
FB_TITLE = re.compile(r"^(\S+)-fb(\d+) — PR #(\d+) feedback$")
SYNCED = re.compile(r"^\[ginflow-pr\] synced=(\S+)")


def _ts(text: str) -> float:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


class PrSync:
    """`ginflow pr sync`: PR feedback becomes a follow-up card on the PR head branch (PRFB-1)."""

    def __init__(self, board: str | None, repo: Path) -> None:
        self.board, self.repo, self.failed, self.merged = board, repo, False, False

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
        pr = json.loads(self.gh("pr", "view", url, "--json", "state,headRefName,mergeCommit,reviews,comments"))
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
        if pr.get("state") == "MERGED":
            sha = (pr.get("mergeCommit") or {}).get("oid", "")
            self.retarget(data, pr["headRefName"])
            self.kb_run("comment", tid, f"[ginflow-pr] merged {sha}".strip())
            self.merged = True
            return print(f"set {tid}: merged {sha[:7]}".strip())
        if pr.get("state") == "CLOSED":
            self.kb_run("comment", tid, "[ginflow-pr] closed")
            return
        if not lines:
            return
        number = PR_URL.match(url).group(2)
        open_id, count = self.open_fb(data, number)
        if open_id:
            self.kb_run("comment", open_id, "[ginflow-pr] new feedback:\n" + "\n".join(f"- {x}" for x in lines))
            print(f"set {tid}: appended {len(lines)} to {open_id}")
        else:
            self.create_fb(task, pr["headRefName"], number, count + 1, lines)
        self.kb_run("comment", tid, f"[ginflow-pr] synced={datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ} items={len(lines)}")

    def retarget(self, data: dict, head: str) -> None:
        """Child PRs still based on the merged branch: GitHub only retargets when the branch is deleted."""
        target = (pc.configured_publish(self.repo) or {}).get("target", "main")
        for cid in data.get("children") or []:
            urls = [m.group(1) for c in self.kb("show", cid, "--json").get("comments") or []
                    if (m := PUBLISHED.match(str(c.get("body") or "")))]
            if not urls or not PR_URL.match(urls[-1]):
                continue
            child = json.loads(self.gh("pr", "view", urls[-1], "--json", "state,baseRefName"))
            if child.get("state") == "OPEN" and child.get("baseRefName") == head:
                self.gh("pr", "edit", urls[-1], "--base", target)
                print(f"set {cid}: base {head} -> {target}")

    def fast_forward(self) -> None:
        # ponytail: uses the --project checkout; same repo as board default_workdir after `ginflow init`.
        settings = pc.configured_publish(self.repo) or {}
        target, remote = settings.get("target", "main"), settings.get("remote", "origin")
        if git(self.repo, "fetch", remote).returncode:
            return print(f"warn {target}: fetch {remote} failed")
        branch = git(self.repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        if branch != target:
            return print(f"warn {target}: on {branch}")
        if git(self.repo, "status", "--porcelain").stdout.strip():
            return print(f"warn {target}: dirty checkout")
        if git(self.repo, "rev-list", "--count", f"{target}..{remote}/{target}").stdout.strip() in ("", "0"):
            return
        done = git(self.repo, "merge", "--ff-only", f"{remote}/{target}")
        print(f"set {target}: fast-forwarded to {remote}/{target}" if done.returncode == 0 else f"warn {target}: not fast-forwardable")

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
        if self.merged:
            self.fast_forward()
        return 1 if self.failed else 0


def pr_sync(args) -> int:
    top = git(Path(args.project).expanduser().resolve(), "rev-parse", "--show-toplevel")
    if top.returncode:
        print(f"fail context: {args.project} is not a git repository")
        return 1
    repo = Path(top.stdout.strip()).resolve()
    ok = pc.config_exists(repo) and not pc.context_error(repo)
    return PrSync(args.board or (pc.configured_context(repo)["board"] if ok else None), repo).run()


class CardsCreate:
    """`ginflow cards create`: committed spec/plan pairs become linked, idempotent cards (CLOUD-1.4)."""

    def __init__(self, board: str | None, repo: Path) -> None:
        self.board, self.repo, self.problems = board, repo, []

    def fail(self, where, reason: str) -> None:
        self.problems.append(f"fail {where}: {reason}")

    def kb(self, *args: str):
        return core.kanban_json(self.board, *args)

    def kb_run(self, *args: str) -> str:
        out = core.kanban_run(self.board, *args)
        if out.returncode:
            raise RuntimeError(f"kanban {args[0]}: {(out.stderr or out.stdout).strip()}")
        return out.stdout

    def committed(self, path: Path) -> bool:
        rel = str(path)
        tracked = git(self.repo, "ls-files", "--error-unmatch", "--", rel).returncode == 0
        return tracked and not git(self.repo, "status", "--porcelain", "--", rel).stdout.strip()

    def existing(self) -> dict[str, dict]:
        """Non-archived board cards by Card key (title prefix `<KEY> — `)."""
        cards = {}
        for task in self.kb("list", "--json"):
            title = str(task.get("title", ""))
            key = title.split(" — ", 1)[0]
            if " — " in title and sc.KEY.match(key):
                cards.setdefault(key, task)
        return cards

    def preflight(self, files: list[str]) -> tuple[list[dict], dict[str, dict]]:
        if not self.board:
            self.fail("board", "no board: pass --board, set HERMES_KANBAN_BOARD, or run `ginflow init`")
            return [], {}
        out = run(["hermes", "kanban", "boards", "list", "--json"])
        try:
            info = {b["slug"]: b for b in json.loads(out.stdout)}.get(self.board)
        except (ValueError, KeyError, TypeError):
            info = None
        if info is None:
            self.fail("board", f"board {self.board} does not exist")
            return [], {}
        if not info.get("default_workdir"):
            self.fail("board", f"board {self.board} has no default_workdir; run `ginflow init`")
            return [], {}
        specs, seen = [], {}
        profiles = pc.installed_profiles()
        for name in files:
            path = Path(name).expanduser().resolve()
            try:
                spec = sc.load_spec(path, self.repo)
            except sc.SpecError as exc:
                self.fail(name, str(exc))
                continue
            if spec["key"] in seen:
                self.fail(name, f"duplicate card {spec['key']} (also {seen[spec['key']]})")
                continue
            seen[spec["key"]] = name
            if spec["assignee"] not in profiles:
                self.fail(name, f"assignee {spec['assignee']!r} is not an installed Hermes profile")
            if not spec["plan_path"].is_file():
                self.fail(name, f"missing plan {spec['plan_rel']}")
            for p in (path, spec["plan_path"]):
                if p.is_file() and not self.committed(p):
                    self.fail(name, f"{p.name} is not committed (or has uncommitted changes)")
            specs.append(spec)
        existing = {}
        try:
            existing = self.existing()
        except (RuntimeError, ValueError) as exc:
            self.fail("board", str(exc))
        try:
            ordered = sc.order(specs, set(existing))
        except sc.SpecError as exc:
            self.fail("specs", str(exc))
            ordered = specs
        return ordered, existing

    def create(self, spec: dict) -> str:
        body = sc.body_text(spec)
        fields = core.parse_card_body(body)
        if not (fields["objective"] and fields["scope"] and fields["acceptance"] and fields["links"]):
            raise RuntimeError(f"{spec['key']}: body does not round-trip through parse_card_body")
        args = ["create", spec["title"], "--body", body, "--assignee", spec["assignee"], "--workspace", "worktree",
                "--initial-status", "blocked", "--idempotency-key", sc.idempotency_key(spec, self.board), "--json"]
        return json.loads(self.kb_run(*args))["id"]

    def harness(self, tid: str) -> str | None:
        """None when the candidate check passes, else the failed check."""
        script = Path(__file__).resolve().parent / "validate-harness.py"
        out = run([sys.executable, str(script), "--target", str(self.repo), "--board", self.board,
                   "--kanban-task-id", tid, "--json"])
        try:
            data = json.loads(out.stdout)
        except ValueError:
            return "harness unavailable"
        if data.get("status") != "blocker":
            return None
        for name, sub in data["subsystems"].items():
            for row in sub.get("checks", []):
                if not row.get("pass") and row.get("severity") == "blocker":
                    return f"{name}: {row.get('message')}"
        return "harness blocker"

    def run(self, files: list[str]) -> int:
        ordered, existing = self.preflight(files)
        if self.problems:
            print("\n".join(self.problems))
            return 1
        ids = {k: t["id"] for k, t in existing.items()}
        result, new = [], []
        try:
            for spec in ordered:
                key, is_new = spec["key"], spec["key"] not in existing
                if is_new:
                    ids[key] = self.create(spec)
                    new.append(spec)
                result.append({"key": key, "id": ids[key], "status": None, "parents": [], "created": is_new})
            for spec, row in zip(ordered, result):
                have = set(self.kb("show", row["id"], "--json").get("parents") or [])
                for b in spec["blocked_by"]:
                    if ids[b] not in have:
                        self.kb_run("link", ids[b], row["id"])
            for spec in new:
                tid = ids[spec["key"]]
                failed = self.harness(tid)
                if failed:
                    self.kb_run("comment", tid, f"[ginflow] cards create: left blocked, {failed}")
                else:
                    self.kb_run("unblock", tid)
            for row in result:
                data = self.kb("show", row["id"], "--json")
                row["status"], row["parents"] = data["task"]["status"], list(data.get("parents") or [])
        except (RuntimeError, ValueError, KeyError) as exc:
            print(f"fail cards: {exc}")
            print(json.dumps(result, indent=2))
            return 1
        print(json.dumps(result, indent=2))
        return 0


def cards_create(args) -> int:
    top = git(Path(args.project).expanduser().resolve(), "rev-parse", "--show-toplevel")
    if top.returncode:
        print(f"fail context: {args.project} is not a git repository")
        return 1
    repo = Path(top.stdout.strip()).resolve()
    if pc.config_exists(repo) and pc.context_error(repo):
        print(f"fail context: {pc.context_error(repo)}")
        return 1
    return CardsCreate(pc.resolve_board(repo, args.board), repo).run(args.specs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ginflow")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="set up a project: context, board workdir, reviewer, checks")
    init.add_argument("--project", default=".")
    init.add_argument("--board", help="use existing Kanban board")
    init.add_argument("--new-board", help="create Kanban board with default workdir")
    init.add_argument("--worker", help="PROFILE:PROVIDER:MODEL")
    init.add_argument("--reviewer", help="reviewer profile to record in .ginflow.yaml")
    pr = sub.add_parser("pr", help="pull request commands").add_subparsers(dest="pr_command", required=True)
    sync = pr.add_parser("sync", help="turn new PR review comments into follow-up cards")
    sync.add_argument("--project", default=".")
    sync.add_argument("--board")
    gh = sub.add_parser("gh", help="GitHub App commands").add_subparsers(dest="gh_command", required=True)
    tok = gh.add_parser("token", help="print a GitHub App installation token; `credential <op>` is a git credential helper")
    tok.add_argument("--repo", help="OWNER/REPO")
    tok.add_argument("--installation")
    tok.add_argument("action", nargs="*")
    cards = sub.add_parser("cards", help="card commands").add_subparsers(dest="cards_command", required=True)
    create = cards.add_parser("create", help="create linked cards from committed spec/plan pairs")
    create.add_argument("--project", default=".")
    create.add_argument("--board")
    create.add_argument("specs", nargs="+", metavar="SPEC")
    args = parser.parse_args(argv)
    if args.command == "gh":
        return gh_app.main(args.repo, args.installation, args.action)
    if args.command == "cards":
        return cards_create(args)
    return pr_sync(args) if args.command == "pr" else Init().run(args)


if __name__ == "__main__":
    sys.exit(main())
