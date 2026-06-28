import logging
import re

import jwt

from app.config import get_settings

logger = logging.getLogger("executor.auth")

_CONTAINER_NAME_RE = re.compile(r"^[a-zA-Z0-9_.-]+$")
_ALLOWED_ACTIONS = {
    "restart_container",
    "stop_container",
    "fetch_logs",
    "list_containers",
}


def validate_action_token(token: str | None) -> dict | None:
    if not token:
        return None
    key = get_settings().public_key
    if not key:
        logger.error("PUBLIC_KEY not configured")
        return None
    try:
        payload = jwt.decode(token, key, algorithms=["RS256"])
    except Exception as exc:
        logger.warning("invalid action token: %s", exc)
        return None
    action = payload.get("action")
    container = payload.get("container")
    if action not in _ALLOWED_ACTIONS:
        logger.warning("disallowed action: %s", action)
        return None
    if container is not None and not _CONTAINER_NAME_RE.fullmatch(container):
        logger.warning("invalid container name: %s", container)
        return None
    return payload


async def verify_internal_state(internal_state: str) -> bool:
    # Future: fetch nonce revocation list from control plane.
    return True
