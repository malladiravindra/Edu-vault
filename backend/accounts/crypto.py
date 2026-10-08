"""Symmetric encryption and keyed hashing for secrets stored in the database (TOTP seeds, backup codes)."""
import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _key_material():
    """FIELD_ENCRYPTION_KEY when configured (mandatory in production); SECRET_KEY only as a development fallback."""
    return (settings.FIELD_ENCRYPTION_KEY or settings.SECRET_KEY).encode()


def _fernet():
    if settings.FIELD_ENCRYPTION_KEY:
        return Fernet(settings.FIELD_ENCRYPTION_KEY)
    digest = hashlib.sha256(b"eduvault.field-encryption:" + _key_material()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plaintext):
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token):
    """Returns the plaintext, or raises ValueError if the token is invalid or the key is wrong."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt value.") from exc


def keyed_hash(purpose, value):
    """Deterministic HMAC-SHA256 of `value`, namespaced by `purpose`, keyed from the encryption key."""
    key = hashlib.sha256(b"eduvault.hmac:" + purpose.encode() + b":" + _key_material()).digest()
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()
