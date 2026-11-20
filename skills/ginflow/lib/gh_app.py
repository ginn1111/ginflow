"""GitHub App installation tokens: JWT signing, repo->installation lookup, per-installation cache."""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

MARGIN = 300
DEFAULT_KEY = "/run/secrets/gh-app.pem"
DEFAULT_API = "https://api.github.com"


class TokenError(Exception):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def api_base(env=None) -> str:
    return (env or os.environ).get("GINFLOW_GH_API", DEFAULT_API).rstrip("/")


def cache_dir(env=None) -> Path:
    env = env or os.environ
    if env.get("GINFLOW_GH_CACHE"):
        return Path(env["GINFLOW_GH_CACHE"])
    return Path(env.get("HERMES_HOME") or Path.home() / ".hermes") / "cache" / "ginflow-gh"


def app_jwt(app_id: str, key_path: str, now: float | None = None) -> str:
    now = int(now if now is not None else time.time())
    head = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = _b64(json.dumps({"iat": now - 60, "exp": now + 540, "iss": app_id}, separators=(",", ":")).encode())
    signing_input = f"{head}.{claims}".encode()
    if not shutil.which("openssl"):
        raise TokenError("openssl not found")
    if not Path(key_path).is_file() or not os.access(key_path, os.R_OK):
        raise TokenError(f"cannot read App key {key_path}")
    proc = subprocess.run(["openssl", "dgst", "-sha256", "-sign", key_path], input=signing_input, capture_output=True)
    if proc.returncode or not proc.stdout:
        raise TokenError(f"signing with {key_path} failed")
    return f"{head}.{claims}.{_b64(proc.stdout)}"


def _request(method: str, url: str, jwt: str) -> tuple[int, dict]:
    req = urllib.request.Request(url, method=method, data=b"" if method == "POST" else None, headers={
        "Authorization": f"Bearer {jwt}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "ginflow"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise TokenError(f"GitHub API unreachable: {getattr(exc, 'reason', exc)}")


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _expiry(value: str) -> float:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp()
    except (ValueError, AttributeError):
        return 0.0


def installation_for_repo(repo: str, jwt: str, env=None, refresh: bool = False) -> str:
    cache = cache_dir(env) / "repos.json"
    mapping = _read_json(cache)
    if not refresh and mapping.get(repo):
        return str(mapping[repo])
    status, body = _request("GET", f"{api_base(env)}/repos/{repo}/installation", jwt)
    if status == 404:
        if repo in mapping:
            mapping.pop(repo)
            _write_json(cache, mapping)
        raise TokenError(f"App not installed on {repo}")
    if status // 100 != 2 or "id" not in body:
        raise TokenError(f"GitHub API returned {status} resolving installation for {repo}")
    mapping[repo] = str(body["id"])
    _write_json(cache, mapping)
    return mapping[repo]


def installation_token(inst: str, jwt: str, env=None) -> str | None:
    """Cached or minted token; None when GitHub says the installation does not exist (404)."""
    path = cache_dir(env) / f"{inst}.json"
    cached = _read_json(path)
    if cached.get("token") and _expiry(cached.get("expires_at", "")) - time.time() > MARGIN:
        return cached["token"]
    status, body = _request("POST", f"{api_base(env)}/app/installations/{inst}/access_tokens", jwt)
    if status == 404:
        return None
    if status // 100 != 2 or not body.get("token"):
        raise TokenError(f"GitHub API returned {status} minting token for installation {inst}")
    _write_json(path, {"token": body["token"], "expires_at": body.get("expires_at", "")})
    return body["token"]


def resolve_token(repo: str | None = None, installation: str | None = None, env=None) -> str:
    env = env if env is not None else os.environ
    app_id = env.get("GINFLOW_GH_APP_ID")
    if not app_id:
        raise TokenError("GINFLOW_GH_APP_ID is not set")
    inst = installation or (None if repo else env.get("GINFLOW_GH_INSTALLATION_ID"))
    if not inst and not repo:
        raise TokenError("no installation (pass --repo or --installation)")
    jwt = app_jwt(app_id, env.get("GINFLOW_GH_APP_KEY", DEFAULT_KEY))
    if inst:
        token = installation_token(str(inst), jwt, env)
        if token is None:
            raise TokenError(f"installation {inst} not found")
        return token
    assert repo
    cached = bool(_read_json(cache_dir(env) / "repos.json").get(repo))
    inst = installation_for_repo(repo, jwt, env)
    token = installation_token(inst, jwt, env)
    if token is None and cached:  # stale mapping: resolve once more
        inst = installation_for_repo(repo, jwt, env, refresh=True)
        token = installation_token(inst, jwt, env)
    if token is None:
        raise TokenError(f"App not installed on {repo}")
    return token


def credential(op: str, stdin, stdout, env=None) -> int:
    env = env if env is not None else os.environ
    fields = dict(line.rstrip("\n").split("=", 1) for line in stdin if "=" in line)
    if op != "get":
        return 0
    hosts = {"github.com"}
    netloc = urlparse(api_base(env)).netloc
    hosts.add(netloc[4:] if netloc.startswith("api.") else netloc)
    if fields.get("host") not in hosts:
        return 0
    path = fields.get("path", "").strip("/")
    path = path[:-4] if path.endswith(".git") else path
    repo = "/".join(path.split("/")[:2]) if path.count("/") >= 1 else None
    try:
        token = resolve_token(repo=repo, env=env)
    except TokenError as exc:
        print(f"fail token: {exc}", file=sys.stderr)
        return 1
    stdout.write(f"username=x-access-token\npassword={token}\n")
    return 0


def main(repo, installation, action, env=None) -> int:
    """CLI entry: `action` is [] for a plain token or ['credential', op]."""
    if action:
        if len(action) != 2 or action[0] != "credential" or action[1] not in ("get", "store", "erase"):
            print("fail token: usage: ginflow gh token [credential get|store|erase]", file=sys.stderr)
            return 1
        return credential(action[1], sys.stdin, sys.stdout, env)
    try:
        token = resolve_token(repo, installation, env)
    except TokenError as exc:
        print(f"fail token: {exc}", file=sys.stderr)
        return 1
    print(token)
    return 0
