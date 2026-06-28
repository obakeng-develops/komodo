import httpx

from app.config import get_settings


def _client():
    return httpx.AsyncClient(timeout=60)


async def diagnose(
    context: dict,
    api_key_encrypted: str | None,
    provider: str,
    model: str,
) -> dict | None:
    settings = get_settings()
    url = settings.llm_service_url
    if not url:
        return None
    async with _client() as client:
        resp = await client.post(
            f"{url.rstrip('/')}/diagnose",
            json={
                "context": context,
                "api_key_encrypted": api_key_encrypted,
                "provider": provider,
                "model": model,
            },
            headers={"X-Internal-API-Key": settings.internal_api_key or ""},
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("diagnosis"):
            return None
        return {
            "diagnosis": data.get("diagnosis"),
            "suggested_fix": data.get("suggested_fix"),
            "confidence": data.get("confidence"),
            "action": data.get("action"),
        }
