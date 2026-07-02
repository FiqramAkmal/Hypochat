import json
import os
import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from hypochat.storage import get_peer_state_dir

MAX_SEEN_EVENT_IDS = 256


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


def _state_path(peer_id: str):
    safe_peer_id = peer_id.replace('/', '_')
    return get_peer_state_dir() / f'{safe_peer_id}.json'


def load_peer_state(peer_id: str) -> dict:
    path = _state_path(peer_id)
    if not path.exists():
        return {'last_seen': 0, 'seen_event_ids': []}

    raw = json.loads(path.read_text())
    if raw.get('version') == 1:
        password = _state_password()
        if not password:
            return {'last_seen': 0, 'seen_event_ids': []}
        salt = base64.b64decode(raw['salt'])
        fernet_key = _derive_fernet_key(password, salt)
        try:
            plaintext = Fernet(fernet_key).decrypt(raw['ciphertext'].encode('ascii'))
        except InvalidToken:
            return {'last_seen': 0, 'seen_event_ids': []}
        state = json.loads(plaintext.decode('utf-8'))
    else:
        state = raw
    state.setdefault('last_seen', 0)
    state.setdefault('seen_event_ids', [])
    return state


def save_peer_state(peer_id: str, state: dict):
    sanitized = {
        'last_seen': int(state.get('last_seen', 0)),
        'seen_event_ids': list(state.get('seen_event_ids', []))[-MAX_SEEN_EVENT_IDS:],
    }
    password = _state_password()
    if not password:
        _state_path(peer_id).write_text(json.dumps(sanitized, indent=2))
        return
    salt = os.urandom(16)
    fernet_key = _derive_fernet_key(password, salt)
    ciphertext = Fernet(fernet_key).encrypt(json.dumps(sanitized).encode('utf-8'))
    payload = {
        'version': 1,
        'salt': base64.b64encode(salt).decode('ascii'),
        'ciphertext': ciphertext.decode('ascii'),
    }
    _state_path(peer_id).write_text(json.dumps(payload, indent=2))


def mark_peer_event(peer_id: str, event_id: str, created_at: int, persist: bool = True):
    if not persist:
        return
    state = load_peer_state(peer_id)
    seen = state.get('seen_event_ids', [])
    if event_id not in seen:
        seen.append(event_id)
    state['seen_event_ids'] = seen[-MAX_SEEN_EVENT_IDS:]
    state['last_seen'] = max(int(created_at), int(state.get('last_seen', 0)))
    save_peer_state(peer_id, state)


def has_seen_event(peer_id: str, event_id: str) -> bool:
    return event_id in load_peer_state(peer_id).get('seen_event_ids', [])


def get_last_seen(peer_id: str) -> int:
    return int(load_peer_state(peer_id).get('last_seen', 0))


def get_seen_event_ids(peer_id: str) -> list[str]:
    return list(load_peer_state(peer_id).get('seen_event_ids', []))
