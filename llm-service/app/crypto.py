import base64
import logging

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from app.config import get_settings

logger = logging.getLogger("llm.crypto")


def _derive_key(raw: str | None) -> bytes:
    if not raw:
        raise ValueError("ENCRYPTION_KEY is required for the LLM service")
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"komodo-v1-llm-key",
        info=b"komodo-fernet-key",
    )
    key = hkdf.derive(raw.encode())
    return base64.urlsafe_b64encode(key)


def _fernet() -> Fernet:
    return Fernet(_derive_key(get_settings().encryption_key))


def decrypt(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except Exception:
        logger.warning("failed to decrypt token")
        return None
