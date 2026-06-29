"""Action whitelist and container-name validation.

ponytail: only these actions may be issued by the control plane. New executors
(Kubernetes, systemd, etc.) add new actions here and implement them locally.
"""
import logging
import re

logger = logging.getLogger("oncall.actions")

_ALLOWED_ACTIONS = {
    "restart_container",
    "stop_container",
    "start_container",
    "fetch_logs",
    "list_containers",
}

_CONTAINER_NAME_RE = re.compile(r"^[a-zA-Z0-9_.-]+$")


def is_allowed_action(action: dict) -> bool:
    if not isinstance(action, dict):
        return False
    name = action.get("action")
    if name not in _ALLOWED_ACTIONS:
        return False
    container = action.get("container")
    if container is not None and not _is_valid_container_name(container):
        logger.warning("disallowed container name in action: %r", action)
        return False
    return True


def _is_valid_container_name(name: str) -> bool:
    return isinstance(name, str) and bool(_CONTAINER_NAME_RE.fullmatch(name))
