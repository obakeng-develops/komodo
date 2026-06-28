import json
from datetime import datetime, timedelta

from fastapi import Request, Response

# ponytail: in-memory idempotency is enough for a local prototype.
# Replace with persistent storage if this becomes a real service.
_idempotency_store: dict[str, tuple[int, str]] = {}
_idempotency_created: dict[str, datetime] = {}
IDEMPOTENCY_TTL_SECONDS = 3600


def _cleanup_old():
    cutoff = datetime.utcnow() - timedelta(seconds=IDEMPOTENCY_TTL_SECONDS)
    stale = [k for k, created in _idempotency_created.items() if created < cutoff]
    for k in stale:
        _idempotency_store.pop(k, None)
        _idempotency_created.pop(k, None)


def _store_key(method: str, path: str, key: str) -> str:
    return f"{method}:{path}:{key}"


async def idempotency_middleware(request: Request, call_next):
    if request.method not in ("POST", "PATCH", "DELETE"):
        return await call_next(request)

    key = request.headers.get("Idempotency-Key")
    if not key:
        return await call_next(request)

    store_key = _store_key(request.method, request.url.path, key)
    existing = _idempotency_store.get(store_key)
    if existing:
        status_code, body = existing
        return Response(content=body, status_code=status_code, media_type="application/json")

    response = await call_next(request)
    body = b""
    async for chunk in response.body_iterator:
        body += chunk

    _cleanup_old()
    _idempotency_store[store_key] = (response.status_code, body.decode("utf-8"))
    _idempotency_created[store_key] = datetime.utcnow()

    return Response(
        content=body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
    )
