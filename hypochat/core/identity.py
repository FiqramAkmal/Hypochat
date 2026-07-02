from hypochat.storage.key_store import load_key, save_key
from hypochat.core.keys import generate_keys, keys_from_nsec

def create_identity(password: str) -> dict:
    key_data = generate_keys()
    save_key(key_data, password)
    return key_data

def load_identity(password: str) -> dict | None:
    return load_key(password)

def import_identity(nsec: str, password: str) -> dict:
    key_data = keys_from_nsec(nsec)
    save_key(key_data, password)
    return key_data
