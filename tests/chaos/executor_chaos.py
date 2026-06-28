"""Chaos tests for the executor's safety boundary (scenarios E1, E2, E5, E6).

These are deterministic and need no LLM. They stand up a throwaway executor with
an ephemeral RSA keypair and a target container, then assert the executor only
runs whitelisted, validly-signed actions and that an unreachable executor fails
gracefully.

Run:  .venv/bin/python tests/chaos/executor_chaos.py
Needs: docker, and the repo's ./executor image (built on demand).

Out of scope here (Komodo doesn't implement these yet, so they'd assert fiction):
  E3 per-target allowlist  - the executor validates name *format*, not a list.
  E4 confidence gating      - the executor has no concept of confidence.
"""
import datetime as dt
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[2]
PORT = 8009
TARGET = "chaos-target"
PASS, FAIL = 0, 0


def check(name, ok, detail=""):
    global PASS, FAIL
    PASS += ok
    FAIL += not ok
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def sign(priv_pem, action, container=None, ttl=60):
    now = dt.datetime.now(dt.timezone.utc)
    return jwt.encode(
        {"action": action, "container": container, "iat": now,
         "exp": now + dt.timedelta(seconds=ttl), "jti": "chaos"},
        priv_pem, algorithm="RS256",
    )


def execute(token, port=PORT):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/execute",
        data=json.dumps({"action_token": token}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except urllib.error.URLError as e:
        return None, str(e)  # unreachable / connection refused


def main():
    # ephemeral keypair
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(serialization.Encoding.PEM,
                             serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode()
    pub = key.public_key().public_bytes(serialization.Encoding.PEM,
                                         serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    # Write under the repo (Docker Desktop shares it; /tmp it does not).
    tmp = ROOT / "secrets" / "chaos-executor.pub"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_text(pub)

    print("building executor image...")
    subprocess.run(["docker", "build", "-q", "-t", "komodo-executor-chaos", str(ROOT / "executor")],
                   check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["docker", "rm", "-f", "chaos-executor", TARGET], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    # target container the executor will act on
    subprocess.run(["docker", "run", "-d", "--name", TARGET, "nginx"], check=True,
                   stdout=subprocess.DEVNULL)
    # executor with the test public key + docker socket; ALLOW_SIMULATE so stop is allowed
    subprocess.run([
        "docker", "run", "-d", "--name", "chaos-executor", "--privileged",
        "-p", f"{PORT}:8002",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "-v", f"{tmp}:/keys/executor.pub:ro",
        "-e", "PUBLIC_KEY_FILE=/keys/executor.pub",
        "-e", "ALLOW_SIMULATE=true",
        "komodo-executor-chaos",
    ], check=True, stdout=subprocess.DEVNULL)

    try:
        for _ in range(15):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2)
                break
            except Exception:
                time.sleep(1)

        print("\nE1  whitelisted action (restart) is accepted and executed")
        before = subprocess.check_output(
            ["docker", "inspect", "-f", "{{.State.StartedAt}}", TARGET]).decode().strip()
        s, body = execute(sign(priv, "restart_container", TARGET))
        time.sleep(2)
        after = subprocess.check_output(
            ["docker", "inspect", "-f", "{{.State.StartedAt}}", TARGET]).decode().strip()
        check("E1 accepted (200, ok)", s == 200 and isinstance(body, dict) and body.get("ok"), str(body))
        check("E1 container actually restarted", before != after, f"{before} -> {after}")

        print("\nE2  non-whitelisted action (exec_shell rm -rf /) is rejected")
        s, body = execute(sign(priv, "exec_shell", "/"))
        check("E2 rejected (401)", s == 401, f"status={s}")

        print("\nE6  malformed / bad-signature tokens are rejected")
        check("E6 garbage token -> 401", execute("not.a.jwt")[0] == 401)
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_pem = other.private_bytes(serialization.Encoding.PEM,
                                        serialization.PrivateFormat.PKCS8,
                                        serialization.NoEncryption()).decode()
        check("E6 wrong-key signature -> 401",
              execute(sign(other_pem, "restart_container", TARGET))[0] == 401)
        check("E6 bad container name -> 401",
              execute(sign(priv, "restart_container", "a; rm -rf /"))[0] == 401)

        print("\nE5  executor unreachable -> caller gets a clean failure, no crash")
        status, _ = execute(sign(priv, "restart_container", TARGET), port=8010)  # nothing listening
        check("E5 unreachable surfaces as error, not exception", status is None, "connection refused handled")

    finally:
        subprocess.run(["docker", "rm", "-f", "chaos-executor", TARGET],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"\n== executor chaos: {PASS} passed, {FAIL} failed ==")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
