#!/usr/bin/env python3
"""`ginflow gh token`: JWT signing, caching, repo->installation mapping, credential helper."""
import base64
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "skills/ginflow/scripts/ginflow.py"
TMP = Path(tempfile.mkdtemp(prefix="ginflow-gh-")).resolve()
KEY, PUB = TMP / "app.pem", TMP / "app.pub"
subprocess.run(["openssl", "genrsa", "-out", str(KEY), "2048"], check=True, capture_output=True)
subprocess.run(["openssl", "rsa", "-in", str(KEY), "-pubout", "-out", str(PUB)], check=True, capture_output=True)

APP_ID = "4242"
REPOS = {"o/a": 7, "o/b": 7, "o/r": 7, "p/c": 9}
STATE = {"hits": [], "mint": 0, "token_status": None, "expires_in": 3600, "jwt_errors": []}


def unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def check_jwt(header):
    try:
        h, c, s = header.split(" ", 1)[1].split(".")
        sig = TMP / "sig.bin"
        sig.write_bytes(unb64(s))
        ok = subprocess.run(["openssl", "dgst", "-sha256", "-verify", str(PUB), "-signature", str(sig)],
                            input=f"{h}.{c}".encode(), capture_output=True).returncode == 0
        claims = json.loads(unb64(c))
        now = time.time()
        ok = ok and json.loads(unb64(h)) == {"alg": "RS256", "typ": "JWT"} and claims["iss"] == APP_ID
        ok = ok and claims["exp"] - now <= 600 and claims["exp"] > now and claims["iat"] < now
        return ok
    except Exception:
        return False


class Stub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, code, body=None):
        data = json.dumps(body or {}).encode()
        self.send_response(code)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_any(self):
        STATE["hits"].append(f"{self.command} {self.path}")
        if not check_jwt(self.headers.get("Authorization", "Bearer x.y.z")):
            STATE["jwt_errors"].append(self.path)
            return self.reply(401)
        parts = self.path.strip("/").split("/")
        if self.command == "GET" and parts[0] == "repos" and parts[-1] == "installation":
            inst = REPOS.get("/".join(parts[1:3]))
            return self.reply(200, {"id": inst}) if inst else self.reply(404)
        if self.command == "POST" and parts[:2] == ["app", "installations"] and parts[-1] == "access_tokens":
            if STATE["token_status"]:
                return self.reply(STATE["token_status"])
            if int(parts[2]) not in set(REPOS.values()):
                return self.reply(404)
            STATE["mint"] += 1
            exp = datetime.now(timezone.utc) + timedelta(seconds=STATE["expires_in"])
            return self.reply(201, {"token": f"tok-{parts[2]}-{STATE['mint']}",
                                    "expires_at": exp.strftime("%Y-%m-%dT%H:%M:%SZ")})
        self.reply(404)

    do_GET = do_POST = handle_any


server = HTTPServer(("127.0.0.1", 0), Stub)
threading.Thread(target=server.serve_forever, daemon=True).start()

CACHE = TMP / "cache"
ENV = {k: v for k, v in os.environ.items() if not k.startswith("GINFLOW_GH_")}
ENV.update(GINFLOW_GH_APP_ID=APP_ID, GINFLOW_GH_APP_KEY=str(KEY), GINFLOW_GH_CACHE=str(CACHE),
           GINFLOW_GH_API=f"http://127.0.0.1:{server.server_port}")


def cli(*args, stdin=None, **env):
    e = {**ENV, **env}
    e = {k: v for k, v in e.items() if v is not None}
    r = subprocess.run([sys.executable, str(CLI), "gh", "token", *args], input=stdin, env=e, text=True, capture_output=True)
    return r.returncode, r.stdout, r.stderr


def reset(clear_cache=True):
    STATE.update(hits=[], mint=0, token_status=None, expires_in=3600, jwt_errors=[])
    if clear_cache:
        subprocess.run(["rm", "-rf", str(CACHE)])


def count(kind):
    return sum(1 for h in STATE["hits"] if kind in h)


failures = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + ("" if cond else f" {detail}"))
    if not cond:
        failures.append(name)


# installation token + cache reuse
reset()
rc, out, err = cli("--installation", "7")
check("token printed exactly", rc == 0 and out == "tok-7-1\n", (rc, out, err))
rc, out, _ = cli("--installation", "7")
check("second call reuses cache", out == "tok-7-1\n" and count("access_tokens") == 1, STATE["hits"])
check("JWTs verified", not STATE["jwt_errors"], STATE["jwt_errors"])
check("cache dir 0700", stat.S_IMODE(CACHE.stat().st_mode) == 0o700)
check("cache files 0600", all(stat.S_IMODE(f.stat().st_mode) == 0o600 for f in CACHE.iterdir()) and any(CACHE.iterdir()))

# near-expiry token re-minted
reset()
CACHE.mkdir(mode=0o700)
soon = (datetime.now(timezone.utc) + timedelta(seconds=200)).strftime("%Y-%m-%dT%H:%M:%SZ")
(CACHE / "7.json").write_text(json.dumps({"token": "old", "expires_at": soon}))
rc, out, _ = cli("--installation", "7")
check("200 s token re-minted", out == "tok-7-1\n" and count("access_tokens") == 1, out)

# corrupt cache ignored
(CACHE / "7.json").write_text("{not json")
reset(clear_cache=False)
rc, out, _ = cli("--installation", "7")
check("corrupt cache overwritten", rc == 0 and out == "tok-7-1\n", out)

# repo lookup cached
reset()
rc, out, _ = cli("--repo", "o/r")
rc2, out2, _ = cli("--repo", "o/r")
check("repo resolves once", rc == rc2 == 0 and out == out2 and count("/repos/o/r/installation") == 1, STATE["hits"])

# multiple repos
reset()
a, b, c = cli("--repo", "o/a")[1], cli("--repo", "o/b")[1], cli("--repo", "p/c")[1]
check("o/a and o/b share a token", a == b and a.startswith("tok-7-") and STATE["mint"] == 2, (a, b, STATE["mint"]))
check("p/c differs", c != a and c.startswith("tok-9-"), c)
rc, out, _ = cli("credential", "get", stdin="protocol=https\nhost=github.com\npath=p/c.git\n\n")
check("credential get p/c uses installation 9", out == f"username=x-access-token\npassword={c.strip()}\n", out)

# not granted
reset()
rc, out, err = cli("--repo", "o/none")
check("ungranted repo", rc == 1 and out == "" and err.strip() == "fail token: App not installed on o/none", (rc, out, err))

# stale mapping: cached installation gone, repo moved
reset()
CACHE.mkdir(mode=0o700)
(CACHE / "repos.json").write_text(json.dumps({"o/r": "99"}))
rc, out, err = cli("--repo", "o/r")
check("stale mapping re-resolved", rc == 0 and out == "tok-7-1\n"
      and json.loads((CACHE / "repos.json").read_text())["o/r"] == "7", (rc, out, err))

# credential helper
reset()
rc, out, _ = cli("credential", "get", stdin="protocol=https\nhost=github.com\npath=o/r.git\n\n")
expected_token = "tok-7-1"
check("credential get", rc == 0 and out == f"username=x-access-token\npassword={expected_token}\n", out)
hits = len(STATE["hits"])
rc, out, _ = cli("credential", "get", stdin="protocol=https\nhost=example.com\npath=o/r.git\n\n")
check("other host prints nothing", rc == 0 and out == "" and len(STATE["hits"]) == hits)
check("store/erase exit 0", cli("credential", "store", stdin="host=github.com\n")[0] == 0
      and cli("credential", "erase", stdin="host=github.com\n")[0] == 0)

# no installation
reset()
rc, out, err = cli()
check("no installation", rc == 1 and out == "" and "no installation" in err, err)
rc, out, _ = cli(GINFLOW_GH_INSTALLATION_ID="9")
check("env installation fallback", rc == 0 and out == "tok-9-1\n", out)

# missing key
reset()
missing = str(TMP / "nokey.pem")
rc, out, err = cli("--installation", "7", GINFLOW_GH_APP_KEY=missing)
check("missing key", rc == 1 and out == "" and missing in err, (rc, out, err))

# 401
reset()
STATE["token_status"] = 401
rc, out, err = cli("--installation", "7")
check("401 prints no token", rc == 1 and out == "" and err.startswith("fail token:"), (rc, out, err))

server.shutdown()
if failures:
    print(f"FAILED: {len(failures)}")
    sys.exit(1)
print("OK: ginflow gh token")
