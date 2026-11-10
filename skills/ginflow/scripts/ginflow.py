#!/usr/bin/env python3
"""ginflow command. `ginflow init` sets up a project; each step prints `ok|set|fail <step>: <detail>`."""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "lib"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"ginflow_cli_{name}", LIB / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pc = _load("project_config")
publish = _load("publish")


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ginflow")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="set up a project: context, board workdir, reviewer, checks")
    init.add_argument("--project", default=".")
    init.add_argument("--board", help="use existing Kanban board")
    init.add_argument("--new-board", help="create Kanban board with default workdir")
    init.add_argument("--worker", help="PROFILE:PROVIDER:MODEL")
    init.add_argument("--reviewer", help="reviewer profile to record in .ginflow.yaml")
    args = parser.parse_args(argv)
    return Init().run(args)


if __name__ == "__main__":
    sys.exit(main())
