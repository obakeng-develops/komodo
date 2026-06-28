"""Thin async wrappers over the `docker` CLI.

ponytail: shell out to the docker CLI the host already has — no docker-py dependency.
Upgrade path: switch to docker-py / the socket API only if CLI parsing proves flaky.
"""

import asyncio
import json
import logging

logger = logging.getLogger("executor.docker")


def _bin():
    return "docker"


async def _run(*args: str) -> tuple[int, str, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            _bin(), *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        return proc.returncode or 0, out.decode().strip(), err.decode().strip()
    except FileNotFoundError:
        logger.warning("docker binary not found in PATH")
        return 127, "", "docker not found"


def _classify(state: str, health: str) -> str:
    if state != "running":
        return "down"
    if health == "unhealthy":
        return "degraded"
    return "healthy"


async def list_containers() -> list[dict]:
    code, out, err = await _run("ps", "-a", "--format", "{{json .}}")
    if code != 0:
        if err:
            logger.warning("docker ps failed: %s", err)
        return []
    containers = []
    for line in out.splitlines():
        if not line.strip():
            continue
        try:
            c = json.loads(line)
        except json.JSONDecodeError:
            continue
        state = c.get("State", "")
        health = c.get("HealthStatus", "")
        containers.append(
            {
                "name": c.get("Names", ""),
                "id": c.get("ID", ""),
                "image": c.get("Image", ""),
                "state": state,
                "health": health,
                "status": _classify(state, health),
            }
        )
    return containers


async def restart(name: str) -> bool:
    code, _, err = await _run("restart", name)
    if code != 0:
        logger.warning("docker restart %s failed: %s", name, err)
    return code == 0


async def stop(name: str) -> bool:
    code, _, err = await _run("stop", name)
    if code != 0:
        logger.warning("docker stop %s failed: %s", name, err)
    return code == 0


async def start(name: str) -> bool:
    code, _, err = await _run("start", name)
    if code != 0:
        logger.warning("docker start %s failed: %s", name, err)
    return code == 0


async def logs(name: str, tail: int = 50) -> str | None:
    code, out, err = await _run("logs", "--tail", str(tail), name)
    if code != 0:
        logger.warning("docker logs %s failed: %s", name, err)
        return None
    return out
