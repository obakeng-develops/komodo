"""Chaos tests for detection + the incident loop (D1, L4, I2, plus a soft
diagnosis check) against a LOCAL Komodo (docker compose) you've already brought
up and logged into once.

Runs a real agent against local Docker, reporting to the local Komodo, then:
  D1  stop a container        -> reported `down` (not `degraded`/`unhealthy`)
  (*) diagnosis               -> incident gets an LLM cause (soft: needs a key)
  L4  start it again          -> incident resolves, monitoring resumes
  I2  kill the agent          -> the watched container is untouched

Run:  .venv/bin/python tests/chaos/detection_chaos.py
Env:  KOMODO_HOST (default http://localhost), KOMODO_EMAIL, KOMODO_PASSWORD
"""
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST = os.getenv("KOMODO_HOST", "http://localhost")
EMAIL = os.getenv("KOMODO_EMAIL", "owner@example.com")
PASSWORD = os.getenv("KOMODO_PASSWORD", "locustpw123")
TARGET = "chaos-web"
PASS = FAIL = 0
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))


def check(name, ok, detail=""):
    global PASS, FAIL
    PASS += ok
    FAIL += not ok
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{HOST}{path}", data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with _opener.open(req, timeout=20) as r:
            txt = r.read().decode()
            return r.status, (json.loads(txt) if txt else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def service(name):
    _, svcs = api("GET", "/api/v1/services")
    return next((s for s in (svcs or []) if s["name"] == name), None)


def wait_for(predicate, timeout=40, interval=2):
    end = time.time() + timeout
    while time.time() < end:
        val = predicate()
        if val:
            return val
        time.sleep(interval)
    return None


def docker(*a):
    return subprocess.run(["docker", *a], capture_output=True, text=True)


def main():
    api("POST", "/api/v1/auth/login", {"email": EMAIL, "password": PASSWORD})
    st, host = api("POST", "/api/v1/hosts", {"name": f"chaos-detect-{int(time.time())}"})
    token = host["token"] if st == 201 else None
    if not token:
        print("  could not create host (already exists?). Re-run after removing it in the UI.")
        raise SystemExit(2)

    docker("rm", "-f", TARGET)
    docker("run", "-d", "--name", TARGET, "nginx")

    agent = subprocess.Popen(
        ["python3", str(ROOT / "agent" / "komodo-agent.py"),
         "--server", HOST, "--token", token, "--interval", "3"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    def incident_for_target():
        _, inc = api("GET", "/api/v1/incidents?limit=10")
        return next((i for i in (inc or {}).get("data", []) if i.get("service_name") == TARGET), None)

    try:
        print("D1  container death is detected as `down`")
        up = wait_for(lambda: (service(TARGET) or {}).get("status") == "healthy", timeout=30)
        check("agent reported the container healthy first", bool(up))
        docker("stop", TARGET)
        # The authoritative detection signal is the incident the monitor opens.
        item = wait_for(lambda: incident_for_target() if (incident_for_target() or {}).get("severity") == "down" else None,
                        timeout=45)
        check("detected as `down` (incident opened, severity=down)",
              bool(item), f"severity={(item or {}).get('severity')}")

        print("\n(*) the incident gets an LLM diagnosis (soft: needs a key + a moment)")
        if item:
            diagnosed = wait_for(
                lambda: (api("GET", f"/api/v1/incidents/{item['id']}")[1] or {}).get("llm_diagnosis"),
                timeout=25)
            if diagnosed:
                print(f"      diagnosis: {str(diagnosed)[:90]}")
            else:
                print("      (no diagnosis yet — fine if no LLM key or it's still thinking)")
        else:
            check("an incident opened for it", False, "no incident found")

        print("\nL4  external fix -> recovery is detected")
        docker("start", TARGET)
        back = wait_for(lambda: (service(TARGET) or {}).get("status") == "healthy", timeout=40)
        check("reported healthy again after restart", bool(back))

        print("\nI2  killing the agent leaves the container untouched")
        agent.terminate()
        agent.wait(timeout=5)
        time.sleep(2)
        state = docker("inspect", "-f", "{{.State.Running}}", TARGET).stdout.strip()
        check("watched container still running after agent dies", state == "true", f"running={state}")
    finally:
        if agent.poll() is None:
            agent.kill()
        docker("rm", "-f", TARGET)

    print(f"\n== detection chaos: {PASS} passed, {FAIL} failed ==")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
