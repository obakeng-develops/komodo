#!/usr/bin/env python3
"""Komodo agent — runs on a user's server and reports container status.

Stdlib only. Talks to the Komodo backend via the /api/v1/agent/beat endpoint.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("komodo-agent")

# Bumped whenever the agent script changes. Reported on every beat so Komodo can
# flag hosts running an out-of-date agent. The server compares it against the
# version of the script it currently serves.
AGENT_VERSION = "2026-06-28"


def run_docker_ps():
    try:
        proc = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{json .}}"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError:
        logger.error("docker not found in PATH")
        return []
    if proc.returncode != 0:
        logger.error("docker ps failed: %s", proc.stderr.strip())
        return []
    containers = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            c = json.loads(line)
        except json.JSONDecodeError:
            continue
        state = c.get("State", "")
        health = c.get("HealthStatus", "")
        if state != "running":
            status = "down"
        elif health == "unhealthy":
            status = "degraded"
        else:
            status = "healthy"
        containers.append(
            {
                "name": c.get("Names", ""),
                "id": c.get("ID", ""),
                "image": c.get("Image", ""),
                "state": state,
                "health": health,
                "status": status,
            }
        )
    return containers


def docker_restart(name):
    try:
        proc = subprocess.run(
            ["docker", "restart", name],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return proc.returncode == 0
    except Exception as exc:
        logger.error("docker restart %s failed: %s", name, exc)
        return False


def run_docker_logs(name, tail=50):
    try:
        # Merge stderr into stdout: many images (nginx, postgres, most apps)
        # log to stderr, so capturing stdout alone returns nothing.
        proc = subprocess.run(
            ["docker", "logs", "--tail", str(tail), name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
            check=False,
        )
    except Exception as exc:
        logger.error("docker logs %s failed: %s", name, exc)
        return None
    if proc.returncode != 0:
        logger.warning("docker logs %s: %s", name, (proc.stdout or "").strip())
        return None
    return proc.stdout


def send_beat(server, token, containers):
    url = f"{server.rstrip('/')}/api/v1/agent/beat"
    data = json.dumps({"containers": containers, "agent_version": AGENT_VERSION}).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        logger.error("beat failed %s: %s", exc.code, body)
        return None
    except Exception as exc:
        logger.error("beat failed: %s", exc)
        return None


def send_logs(server, token, lines):
    url = f"{server.rstrip('/')}/api/v1/agent/logs"
    data = json.dumps({"lines": lines}).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        logger.error("log send failed: %s", exc)
        return None


def main():
    parser = argparse.ArgumentParser(description="Komodo agent")
    parser.add_argument("--server", required=True, help="Komodo backend URL")
    parser.add_argument("--token", required=True, help="Agent token")
    parser.add_argument("--interval", type=int, default=10, help="Heartbeat interval in seconds")
    parser.add_argument("--once", action="store_true", help="Send one beat and exit")
    args = parser.parse_args()

    logger.info("komodo agent starting: server=%s interval=%ss", args.server, args.interval)

    pending_logs: set[str] = set()
    tail_proc = None
    tail_thread = None
    tail_stop = threading.Event()
    tail_lines = []
    tail_lock = threading.Lock()
    tail_container: str | None = None

    def tail_loop(container_name):
        nonlocal tail_lines
        logger.info("start tailing logs for %s", container_name)
        proc = subprocess.Popen(
            ["docker", "logs", "-f", "--since", "0s", container_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        nonlocal tail_proc
        tail_proc = proc
        try:
            for line in proc.stdout:
                if tail_stop.is_set():
                    break
                with tail_lock:
                    tail_lines.append(line.rstrip("\n"))
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
            logger.info("stopped tailing logs for %s", container_name)

    def flush_lines():
        nonlocal tail_lines
        with tail_lock:
            batch = tail_lines
            tail_lines = []
        if batch:
            send_logs(args.server, args.token, batch)

    try:
        while True:
            containers = run_docker_ps()
            # If backend asked for logs last beat, fetch them now.
            if containers and pending_logs:
                for c in containers:
                    if c["name"] in pending_logs:
                        c["logs"] = run_docker_logs(c["name"])
                pending_logs.clear()

            if containers:
                response = send_beat(args.server, args.token, containers)
                if response:
                    for action in response.get("restart", []):
                        # The backend sends action dicts ({"action": ..., "container": ...});
                        # tolerate a bare name string too.
                        name = action.get("container") if isinstance(action, dict) else action
                        if not name:
                            continue
                        logger.info("restarting %s", name)
                        if docker_restart(name):
                            logger.info("restarted %s", name)
                        else:
                            logger.error("failed to restart %s", name)
                    pending_logs.update(response.get("fetch_logs", []))

                    want_tail = response.get("tail_logs", False)
                    if tail_thread and tail_container and not want_tail:
                        tail_stop.set()
                        tail_thread.join(timeout=3)
                        tail_thread = None
                        tail_container = None
                        flush_lines()
                    elif want_tail and containers:
                        target = None
                        for c in containers:
                            if c["status"] in ("down", "degraded"):
                                target = c["name"]
                                break
                        if target and target != tail_container:
                            if tail_thread:
                                tail_stop.set()
                                tail_thread.join(timeout=3)
                                tail_thread = None
                            tail_stop.clear()
                            tail_container = target
                            tail_lines = []
                            tail_thread = threading.Thread(target=tail_loop, args=(target,), daemon=True)
                            tail_thread.start()
                        elif target == tail_container:
                            flush_lines()
            if args.once:
                break
            time.sleep(args.interval)
    finally:
        tail_stop.set()
        if tail_thread:
            tail_thread.join(timeout=3)
        flush_lines()


if __name__ == "__main__":
    main()
