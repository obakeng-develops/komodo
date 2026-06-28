"""Sign and send action tokens to executors.

ponytail: keep the signing key in the control plane only. Each executor gets the
matching public key via env var. Tokens are short-lived and single-purpose.
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone

import httpx
import jwt

from app.config import get_settings

logger = logging.getLogger("oncall.executor")


def sign_action(action: str, container: str | None = None, ttl_seconds: int = 60) -> str:
    private_key = get_settings().executor_signing_key
    if not private_key:
        raise RuntimeError("EXECUTOR_SIGNING_KEY not configured")
    now = datetime.now(timezone.utc)
    payload = {
        "action": action,
        "container": container,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


async def send_action(host_url: str, action_token: str) -> tuple[bool, str | None]:
    if not host_url:
        return False, "no executor url"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{host_url.rstrip('/')}/execute",
                json={"action_token": action_token},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("ok", False), data.get("output")
    except Exception as exc:
        logger.warning("executor request failed: %s", exc)
        return False, str(exc)
