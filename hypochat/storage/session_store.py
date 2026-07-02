import base64
import json
import os
import uuid
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from hypochat.storage import get_session_state_dir


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
    return get_session_state_dir() / f'{safe_peer_id}.json'


def _default_state() -> dict:
    return {
        'version': 1,
        'current_outgoing': None,
        'current_incoming': None,
        'prekey_bundle': None,
        'seen_handshake_ids': [],
        'pending_outgoing': [],
    }


def load_session_state(peer_id: str) -> dict:
    path = _state_path(peer_id)
    if not path.exists():
        return _default_state()

    raw = json.loads(path.read_text())
    if raw.get('version') == 1 and 'ciphertext' in raw and 'salt' in raw:
        password = _state_password()
        if not password:
            return _default_state()
        salt = base64.b64decode(raw['salt'])
        fernet_key = _derive_fernet_key(password, salt)
        try:
            plaintext = Fernet(fernet_key).decrypt(raw['ciphertext'].encode('ascii'))
        except InvalidToken:
            return _default_state()
        state = json.loads(plaintext.decode('utf-8'))
    else:
        state = raw
    state.setdefault('version', 1)
    state.setdefault('current_outgoing', None)
    state.setdefault('current_incoming', None)
    state.setdefault('prekey_bundle', None)
    state.setdefault('seen_handshake_ids', [])
    state.setdefault('pending_outgoing', [])
    return state


def save_session_state(peer_id: str, state: dict):
    sanitized = {
        'version': 1,
        'current_outgoing': state.get('current_outgoing'),
        'current_incoming': state.get('current_incoming'),
        'prekey_bundle': state.get('prekey_bundle'),
        'seen_handshake_ids': list(state.get('seen_handshake_ids', []))[-256:],
        'pending_outgoing': [item for item in state.get('pending_outgoing', []) if isinstance(item, str)][-64:],
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


def _new_session_record(key: str) -> dict:
    now = int(datetime.now(timezone.utc).timestamp())
    return {
        'session_id': uuid.uuid4().hex,
        'key': key,
        'created_at': now,
        'last_used': now,
    }


def get_outgoing_session(peer_id: str) -> dict | None:
    return load_session_state(peer_id).get('current_outgoing')


def set_outgoing_session(peer_id: str, session: dict | None):
    state = load_session_state(peer_id)
    state['current_outgoing'] = session
    save_session_state(peer_id, state)


def rotate_outgoing_session(peer_id: str, key: str) -> dict:
    state = load_session_state(peer_id)
    session = _new_session_record(key)
    state['current_outgoing'] = session
    save_session_state(peer_id, state)
    return session


def get_incoming_session(peer_id: str) -> dict | None:
    return load_session_state(peer_id).get('current_incoming')


def get_incoming_session_by_id(peer_id: str, session_id: str) -> dict | None:
    session = get_incoming_session(peer_id)
    if session and session.get('session_id') == session_id:
        return session
    return None


def set_incoming_session(peer_id: str, session_id: str, key: str):
    state = load_session_state(peer_id)
    now = int(datetime.now(timezone.utc).timestamp())
    state['current_incoming'] = {
        'session_id': session_id,
        'key': key,
        'created_at': now,
        'last_used': now,
    }
    save_session_state(peer_id, state)


def touch_incoming_session(peer_id: str, session_id: str):
    state = load_session_state(peer_id)
    session = state.get('current_incoming')
    if session and session.get('session_id') == session_id:
        session['last_used'] = int(datetime.now(timezone.utc).timestamp())
        save_session_state(peer_id, state)


def clear_outgoing_session(peer_id: str):
    state = load_session_state(peer_id)
    state['current_outgoing'] = None
    save_session_state(peer_id, state)


def get_prekey_bundle(peer_id: str) -> dict | None:
    return load_session_state(peer_id).get('prekey_bundle')


def set_prekey_bundle(peer_id: str, bundle: dict | None):
    state = load_session_state(peer_id)
    state['prekey_bundle'] = bundle
    save_session_state(peer_id, state)


def has_seen_handshake(peer_id: str, handshake_id: str) -> bool:
    return handshake_id in load_session_state(peer_id).get('seen_handshake_ids', [])


def mark_seen_handshake(peer_id: str, handshake_id: str):
    state = load_session_state(peer_id)
    seen = list(state.get('seen_handshake_ids', []))
    if handshake_id not in seen:
        seen.append(handshake_id)
    state['seen_handshake_ids'] = seen[-256:]
    save_session_state(peer_id, state)


def get_pending_outgoing(peer_id: str) -> list[str]:
    return [item for item in load_session_state(peer_id).get("pending_outgoing", []) if isinstance(item, str)]


def enqueue_pending_outgoing(peer_id: str, plaintext: str):
    state = load_session_state(peer_id)
    pending = [item for item in state.get("pending_outgoing", []) if isinstance(item, str)]
    pending.append(plaintext)
    state["pending_outgoing"] = pending[-64:]
    save_session_state(peer_id, state)


def pop_pending_outgoing(peer_id: str) -> list[str]:
    state = load_session_state(peer_id)
    pending = [item for item in state.get("pending_outgoing", []) if isinstance(item, str)]
    state["pending_outgoing"] = []
    save_session_state(peer_id, state)
    return pending
