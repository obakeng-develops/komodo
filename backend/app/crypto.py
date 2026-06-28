import base64
import logging

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from app.config import get_settings

logger = logging.getLogger("oncall.crypto")


def _derive_key(raw: str | None) -> bytes:
    if not raw:
        if _derive_key._ephemeral is None:
            logger.warning("ENCRYPTION_KEY not set; generating an ephemeral key. LLM API keys will be lost on restart.")
            _derive_key._ephemeral = Fernet.generate_key()
        return _derive_key._ephemeral
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"komodo-v1-llm-key",
        info=b"komodo-fernet-key",
    )
    key = hkdf.derive(raw.encode())
    return base64.urlsafe_b64encode(key)


_derive_key._ephemeral: bytes | None = None


def _fernet() -> Fernet:
    return Fernet(_derive_key(get_settings().encryption_key))


def encrypt(text: str | None) -> str | None:
    if not text:
        return None
    return _fernet().encrypt(text.encode()).decode()


def decrypt(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except Exception:
        logger.warning("failed to decrypt token")
        return None


def mask_key(key: str | None) -> str | None:
    if not key:
        return None
    if len(key) <= 8:
        return "•" * len(key)
    return f"{key[:3]}...{key[-4:]}"


if __name__ == "__main__":
    original = "sk-test-secret-key-1234"
    enc = encrypt(original)
    dec = decrypt(enc)
    assert dec == original
    assert mask_key(original) == "sk-...1234"
    print("crypto self-check ok")
