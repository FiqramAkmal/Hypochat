# Abstraction layer for message content encryption and payload shaping.

import base64
import json
import secrets
import uuid

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.asymmetric import x25519

from nostr_sdk import Keys, Nip44Version, PublicKey, nip44_encrypt, nip44_decrypt

from hypochat.core.constants import PAD_BLOCK_SIZE

INNER_ENVELOPE_VERSION = 2
INNER_ENVELOPE_ALG = "hypochat-inner-nip44-v1"
SESSION_CONTROL_VERSION = 4
SESSION_CONTROL_ALG = "hypochat-session-control-v1"
SESSION_MESSAGE_VERSION = 5
SESSION_MESSAGE_ALG = "hypochat-session-msg-v1"
PREKEY_BUNDLE_VERSION = 6
PREKEY_BUNDLE_ALG = "hypochat-prekey-bundle-v1"
HANDSHAKE_INIT_VERSION = 7
HANDSHAKE_INIT_ALG = "hypochat-handshake-init-v1"


def encrypt_message(sender_nsec: str, recipient_npub: str, plaintext: str) -> str:
    keys = Keys.parse(sender_nsec)
    recipient_pk = PublicKey.parse(recipient_npub)
    return nip44_encrypt(keys.secret_key(), recipient_pk, plaintext, Nip44Version.V2)


def decrypt_message(receiver_nsec: str, sender_npub: str, ciphertext: str) -> str:
    keys = Keys.parse(receiver_nsec)
    sender_pk = PublicKey.parse(sender_npub)
    return nip44_decrypt(keys.secret_key(), sender_pk, ciphertext)


def pad_plaintext(plaintext: str, block_size: int = PAD_BLOCK_SIZE) -> str:
    envelope = {
        "v": 1,
        "body": plaintext,
        "pad": "",
    }
    serialized = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False)
    remainder = len(serialized) % block_size
    if remainder != 0:
        target = block_size - remainder
        envelope["pad"] = secrets.token_hex((target // 2) + 8)
        serialized = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False)
        while len(serialized) % block_size != 0:
            envelope["pad"] += secrets.choice("abcdef0123456789")
            serialized = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False)
    return serialized


def unpad_plaintext(payload: str) -> str:
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return payload

    if not isinstance(decoded, dict):
        return payload
    if decoded.get("v") != 1:
        return payload
    body = decoded.get("body")
    return body if isinstance(body, str) else payload


def _serialize_padded_envelope(envelope: dict, block_size: int = PAD_BLOCK_SIZE) -> str:
    serialized = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False)
    remainder = len(serialized) % block_size
    if remainder != 0:
        target = block_size - remainder
        envelope["pad"] = secrets.token_hex((target // 2) + 8)
        serialized = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False)
        while len(serialized) % block_size != 0:
            envelope["pad"] += secrets.choice("abcdef0123456789")
            serialized = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False)
    return serialized


def seal_hypochat_payload(sender_nsec: str, recipient_npub: str, plaintext: str) -> str:
    inner_ciphertext = encrypt_message(sender_nsec, recipient_npub, plaintext)
    envelope = {
        "v": INNER_ENVELOPE_VERSION,
        "alg": INNER_ENVELOPE_ALG,
        "ct": inner_ciphertext,
        "pad": "",
    }
    return _serialize_padded_envelope(envelope)


def open_hypochat_payload(receiver_nsec: str, sender_npub: str, payload: str) -> str:
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return unpad_plaintext(payload)

    if not isinstance(decoded, dict):
        return unpad_plaintext(payload)

    if decoded.get("v") == INNER_ENVELOPE_VERSION and decoded.get("alg") == INNER_ENVELOPE_ALG:
        ciphertext = decoded.get("ct")
        if not isinstance(ciphertext, str):
            raise ValueError("Invalid Hypochat-only payload")
        return decrypt_message(receiver_nsec, sender_npub, ciphertext)

    return unpad_plaintext(payload)


def generate_session_key() -> str:
    return Fernet.generate_key().decode("ascii")


def _serialize_json(data: dict) -> str:
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def build_session_announce_plaintext(session_id: str, session_key: str) -> str:
    return _serialize_json({
        "v": SESSION_CONTROL_VERSION,
        "alg": SESSION_CONTROL_ALG,
        "type": "announce",
        "sid": session_id,
        "key": session_key,
    })


def parse_session_control_plaintext(payload: str) -> dict | None:
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(decoded, dict):
        return None
    if decoded.get("v") != SESSION_CONTROL_VERSION or decoded.get("alg") != SESSION_CONTROL_ALG:
        return None
    if decoded.get("type") != "announce":
        return None
    if not isinstance(decoded.get("sid"), str) or not isinstance(decoded.get("key"), str):
        return None
    return decoded


def seal_session_message_payload(session_id: str, session_key: str, plaintext: str) -> str:
    ciphertext = Fernet(session_key.encode("ascii")).encrypt(plaintext.encode("utf-8")).decode("ascii")
    envelope = {
        "v": SESSION_MESSAGE_VERSION,
        "alg": SESSION_MESSAGE_ALG,
        "sid": session_id,
        "ct": ciphertext,
        "pad": "",
    }
    return _serialize_padded_envelope(envelope)


def parse_session_message_payload(payload: str) -> dict | None:
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(decoded, dict):
        return None
    if decoded.get("v") != SESSION_MESSAGE_VERSION or decoded.get("alg") != SESSION_MESSAGE_ALG:
        return None
    if not isinstance(decoded.get("sid"), str) or not isinstance(decoded.get("ct"), str):
        return None
    return decoded


def open_session_message_payload(session_key: str, payload: str) -> str:
    decoded = parse_session_message_payload(payload)
    if decoded is None:
        raise ValueError("Invalid session payload")
    plaintext = Fernet(session_key.encode("ascii")).decrypt(decoded["ct"].encode("ascii"))
    return plaintext.decode("utf-8")


def generate_prekey_bundle() -> dict:
    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key()
    return {
        "prekey_id": uuid.uuid4().hex,
        "private_key": base64.b64encode(private_key.private_bytes_raw()).decode("ascii"),
        "public_key": base64.b64encode(public_key.public_bytes_raw()).decode("ascii"),
    }


def build_prekey_bundle_plaintext(bundle: dict, request_reply: bool = False) -> str:
    return _serialize_json({
        "v": PREKEY_BUNDLE_VERSION,
        "alg": PREKEY_BUNDLE_ALG,
        "prekey_id": bundle["prekey_id"],
        "public_key": bundle["public_key"],
        "request_reply": bool(request_reply),
    })


def parse_prekey_bundle_plaintext(payload: str) -> dict | None:
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(decoded, dict):
        return None
    if decoded.get("v") != PREKEY_BUNDLE_VERSION or decoded.get("alg") != PREKEY_BUNDLE_ALG:
        return None
    if not isinstance(decoded.get("prekey_id"), str) or not isinstance(decoded.get("public_key"), str):
        return None
    if "request_reply" in decoded and not isinstance(decoded.get("request_reply"), bool):
        return None
    decoded.setdefault("request_reply", False)
    return decoded


def _derive_handshake_key(shared_secret: bytes, salt: bytes) -> bytes:
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=b"hypochat-phase4b")
    return base64.urlsafe_b64encode(hkdf.derive(shared_secret))


def build_handshake_init_plaintext(prekey_bundle: dict, session_id: str, session_key: str) -> str:
    eph_private = x25519.X25519PrivateKey.generate()
    eph_public = eph_private.public_key()
    receiver_public = x25519.X25519PublicKey.from_public_bytes(base64.b64decode(prekey_bundle["public_key"]))
    shared_secret = eph_private.exchange(receiver_public)
    handshake_id = uuid.uuid4().hex
    salt = secrets.token_bytes(16)
    fernet_key = _derive_handshake_key(shared_secret, salt)
    wrapped_session_key = Fernet(fernet_key).encrypt(session_key.encode("utf-8")).decode("ascii")
    return _serialize_json({
        "v": HANDSHAKE_INIT_VERSION,
        "alg": HANDSHAKE_INIT_ALG,
        "hid": handshake_id,
        "sid": session_id,
        "prekey_id": prekey_bundle["prekey_id"],
        "eph_pub": base64.b64encode(eph_public.public_bytes_raw()).decode("ascii"),
        "salt": base64.b64encode(salt).decode("ascii"),
        "wkey": wrapped_session_key,
    })


def parse_handshake_init_plaintext(payload: str) -> dict | None:
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(decoded, dict):
        return None
    if decoded.get("v") != HANDSHAKE_INIT_VERSION or decoded.get("alg") != HANDSHAKE_INIT_ALG:
        return None
    required = ("hid", "sid", "prekey_id", "eph_pub", "salt", "wkey")
    if not all(isinstance(decoded.get(key), str) for key in required):
        return None
    return decoded


def open_handshake_init_plaintext(prekey_bundle: dict, payload: str) -> dict:
    decoded = parse_handshake_init_plaintext(payload)
    if decoded is None:
        raise ValueError("Invalid handshake init payload")
    if decoded["prekey_id"] != prekey_bundle["prekey_id"]:
        raise ValueError("Handshake prekey mismatch")
    private_key = x25519.X25519PrivateKey.from_private_bytes(base64.b64decode(prekey_bundle["private_key"]))
    eph_public = x25519.X25519PublicKey.from_public_bytes(base64.b64decode(decoded["eph_pub"]))
    shared_secret = private_key.exchange(eph_public)
    salt = base64.b64decode(decoded["salt"])
    fernet_key = _derive_handshake_key(shared_secret, salt)
    session_key = Fernet(fernet_key).decrypt(decoded["wkey"].encode("ascii")).decode("utf-8")
    return {
        "handshake_id": decoded["hid"],
        "session_id": decoded["sid"],
        "session_key": session_key,
    }
