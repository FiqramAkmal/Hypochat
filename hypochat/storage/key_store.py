import json
import base64
import os

from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from hypochat.storage import get_key_path


def _derive_fernet_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def save_key(key_data: dict, password: str):
    salt = os.urandom(16)
    fernet_key = _derive_fernet_key(password, salt)
    ciphertext = Fernet(fernet_key).encrypt(
        json.dumps(key_data).encode("utf-8")
    )
    payload = {
        "version": 2,
        "kdf": "pbkdf2-sha256",
        "iterations": 600000,
        "salt": base64.b64encode(salt).decode("ascii"),
        "cipher": "fernet",
        "ciphertext": ciphertext.decode("ascii"),
    }
    get_key_path().write_text(json.dumps(payload, indent=2))
    get_key_path().chmod(0o600)


def load_key(password: str | None = None) -> dict | None:
    p = get_key_path()
    if not p.exists():
        return None
    payload = json.loads(p.read_text())

    if payload.get("version") != 2:
        raise ValueError(
            "Legacy plaintext key store detected. Re-import your nsec with the upgraded client."
        )

    if not password:
        raise ValueError("Password required to unlock key store.")

    salt = base64.b64decode(payload["salt"])
    fernet_key = _derive_fernet_key(password, salt)
    try:
        plaintext = Fernet(fernet_key).decrypt(payload["ciphertext"].encode("ascii"))
    except InvalidToken as exc:
        raise ValueError("Wrong password or corrupted key store.") from exc
    return json.loads(plaintext.decode("utf-8"))
