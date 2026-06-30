"""Fly.io Machines API client.

A Fly executor type: a service whose `method` is "fly" lives as a Fly Machine,
and Mino talks to the Machines API instead of the agent or `docker`. This is
the read path — list an app's machines and map their state to a status.
Remediation (restart/stop/start) lands in a later PR.
"""

import logging

logger = logging.getLogger("oncall.fly")

API_BASE = "https://api.machines.dev/v1"

# Mino action name -> Machines API operation.
OPS = {"restart_container": "restart", "stop_container": "stop", "start_container": "start"}


async def list_machines(app: str, token: str) -> list[dict] | None:
    """Machines for a Fly app. None if the call failed (bad token, missing app)."""
    import httpx

    url = f"{API_BASE}/apps/{app}/machines"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.warning("fly list machines for %s failed: %s", app, exc)
        return None


async def machine_action(app: str, machine_id: str, op: str, token: str) -> bool:
    """Run a Machines API op (restart/stop/start) on a machine. True on success."""
    import httpx

    url = f"{API_BASE}/apps/{app}/machines/{machine_id}/{op}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers={"Authorization": f"Bearer {token}"})
            resp.raise_for_status()
            return True
    except Exception as exc:
        logger.warning("fly %s machine %s failed: %s", op, machine_id, exc)
        return False


def machine_status(state: str | None) -> str:
    """Fly machine.state -> Mino status. `started` is healthy; a stopped or
    failed machine is down; transitional states are degraded.

    ponytail: state-based. Fly also exposes per-machine health checks; fold them
    in if state alone proves too coarse.
    """
    if state == "started":
        return "healthy"
    if state in ("stopped", "destroyed", "destroying", "failed"):
        return "down"
    return "degraded"


if __name__ == "__main__":
    assert machine_status("started") == "healthy"
    assert machine_status("stopped") == "down"
    assert machine_status("failed") == "down"
    assert machine_status("starting") == "degraded"
    assert machine_status(None) == "degraded"
    assert OPS["restart_container"] == "restart"
    assert OPS["stop_container"] == "stop"
    assert OPS["start_container"] == "start"
    print("fly self-check ok")
