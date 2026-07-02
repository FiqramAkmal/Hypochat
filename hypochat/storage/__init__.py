from pathlib import Path
from platformdirs import user_data_dir

def get_data_dir() -> Path:
    p = Path(user_data_dir("hypochat", "hypochat"))
    p.mkdir(parents=True, exist_ok=True)
    return p

def get_key_path() -> Path:
    return get_data_dir() / "key.json"

def get_contacts_path() -> Path:
    return get_data_dir() / "contacts.json"

def get_config_path() -> Path:
    return get_data_dir() / "config.json"

def get_history_dir() -> Path:
    p = get_data_dir() / "history"
    p.mkdir(exist_ok=True)
    return p

def get_peer_state_dir() -> Path:
    p = get_data_dir() / "peer_state"
    p.mkdir(exist_ok=True)
    return p


def get_session_state_dir() -> Path:
    p = get_data_dir() / "sessions"
    p.mkdir(exist_ok=True)
    return p
