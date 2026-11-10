"""Provider command builders for publishing a reviewed branch as an MR/PR.

Pure: builds argv lists only, never executes. Callers run them without a shell.
"""
from __future__ import annotations

import json
import re

PROVIDERS = ("github", "gitlab")
_HEX = re.compile(r"[0-9a-f]{7,40}")
_URL = re.compile(r"https?://\S+")


def _ref(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip() or value.startswith("-") or any(c.isspace() for c in value):
        raise ValueError(f"invalid {name}: {value!r}")
    return value


def _provider(provider: object) -> str:
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider: {provider!r}")
    return provider  # type: ignore[return-value]


def build_push_argv(workspace: str, remote: str, commit: str, branch: str) -> list[str]:
    """Push the exact reviewed commit to the branch. Never force."""
    if not isinstance(commit, str) or not _HEX.fullmatch(commit):
        raise ValueError(f"invalid commit: {commit!r}")
    return ["git", "-C", _ref("workspace", workspace), "push", _ref("remote", remote),
            f"{commit}:refs/heads/{_ref('branch', branch)}"]


def build_create_argv(provider: str, branch: str, target: str, title: str, body: str, draft: bool = False) -> list[str]:
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title is required")
    branch, target = _ref("branch", branch), _ref("target", target)
    if _provider(provider) == "github":
        argv = ["gh", "pr", "create", "-H", branch, "-B", target, "-t", title.strip(), "-b", body or ""]
    else:
        argv = ["glab", "mr", "create", "-s", branch, "-b", target, "-t", title.strip(), "-d", body or "",
                "--push=false", "--yes"]
    return argv + (["--draft"] if draft else [])


def build_existing_argv(provider: str, branch: str) -> list[str]:
    branch = _ref("branch", branch)
    if _provider(provider) == "github":
        return ["gh", "pr", "list", "-H", branch, "--json", "url"]
    return ["glab", "mr", "list", "-s", branch, "-F", "json"]


def build_auth_argv(provider: str) -> list[str]:
    return ["gh" if _provider(provider) == "github" else "glab", "auth", "status"]


def parse_existing_url(provider: str, stdout: str) -> str | None:
    """First open MR/PR URL from list JSON, else None."""
    _provider(provider)
    try:
        items = json.loads(stdout or "[]")
    except json.JSONDecodeError:
        return None
    for item in items if isinstance(items, list) else []:
        url = item.get("url") or item.get("web_url") if isinstance(item, dict) else None
        if isinstance(url, str) and _URL.fullmatch(url):
            return url
    return None


def parse_created_url(stdout: str) -> str | None:
    """Last URL printed by `gh pr create` / `glab mr create`."""
    found = _URL.findall(stdout or "")
    return found[-1] if found else None


__all__ = ["PROVIDERS", "build_push_argv", "build_create_argv", "build_existing_argv", "build_auth_argv",
           "parse_existing_url", "parse_created_url"]
