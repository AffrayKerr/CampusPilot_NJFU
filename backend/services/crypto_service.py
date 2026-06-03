import base64
import hashlib

from cryptography.fernet import Fernet
from flask import current_app


def _derive_key(raw_key):
    digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet():
    raw_key = current_app.config.get("ENCRYPTION_KEY") or current_app.config.get("SECRET_KEY")
    return Fernet(_derive_key(raw_key))


def encrypt_text(plain_text):
    if plain_text is None:
        return ""
    return get_fernet().encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_text(cipher_text):
    if not cipher_text:
        return ""
    return get_fernet().decrypt(cipher_text.encode("utf-8")).decode("utf-8")
