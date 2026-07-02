import base64
import json
import os
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from hypochat.storage import get_history_dir

MAX_TRANSCRIPT_MESSAGES = 200


def _state_password() -> str | None:
    return os.environ.get("HYPOCHAT_SESSION_PASSWORD") or os.environ.get("HYPOCHAT_PASSWORD")


def _derive_fernet_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=300_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def _transcript_path(peer_id: str):
    safe_peer_id = peer_id.replace('/', '_')
    return get_history_dir() / f'{safe_peer_id}.json'


def _sort_transcript(transcript: list) -> list:
    return sorted(
        transcript,
        key=lambda item: (
            int(item.get('timestamp', 0) or 0),
            item.get('sender', ''),
            item.get('text', ''),
        ),
    )


def load_transcript(peer_id: str) -> list:
    path = _transcript_path(peer_id)
    if not path.exists():
        return []

    raw = json.loads(path.read_text())
    if isinstance(raw, dict) and raw.get('version') == 1:
        password = _state_password()
        if not password:
            return []
        salt = base64.b64decode(raw['salt'])
        fernet_key = _derive_fernet_key(password, salt)
        try:
            plaintext = Fernet(fernet_key).decrypt(raw['ciphertext'].encode('ascii'))
        except InvalidToken:
            return []
        transcript = json.loads(plaintext.decode('utf-8'))
    else:
        transcript = raw
    return _sort_transcript(transcript)


def get_last_transcript_timestamp(peer_id: str) -> int:
    transcript = load_transcript(peer_id)
    if not transcript:
        return 0
    return max(int(item.get('timestamp', 0) or 0) for item in transcript)


def _save_transcript(peer_id: str, transcript: list):
    transcript = _sort_transcript(transcript)[-MAX_TRANSCRIPT_MESSAGES:]
    password = _state_password()
    if not password:
        _transcript_path(peer_id).write_text(json.dumps(transcript, indent=2))
        return
    salt = os.urandom(16)
    fernet_key = _derive_fernet_key(password, salt)
    ciphertext = Fernet(fernet_key).encrypt(json.dumps(transcript).encode('utf-8'))
    payload = {
        'version': 1,
        'salt': base64.b64encode(salt).decode('ascii'),
        'ciphertext': ciphertext.decode('ascii'),
    }
    _transcript_path(peer_id).write_text(json.dumps(payload, indent=2))


def append_transcript_message(peer_id: str, sender: str, text: str, timestamp: int | None = None):
    transcript = load_transcript(peer_id)
    ts = int(timestamp) if timestamp is not None else int(datetime.now(timezone.utc).timestamp())
    transcript.append(
        {
            'sender': sender,
            'text': text,
            'timestamp': ts,
        }
    )
    _save_transcript(peer_id, transcript)


def rewrite_sorted_transcript(peer_id: str):
    transcript = load_transcript(peer_id)
    _save_transcript(peer_id, transcript)
