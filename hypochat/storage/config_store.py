import json
from hypochat.storage import get_config_path
from hypochat.core.constants import DEFAULT_CONFIG

def load_config() -> dict:
    path = get_config_path()
    if not path.exists():
        return DEFAULT_CONFIG.copy()
    config = json.loads(path.read_text())
    merged = DEFAULT_CONFIG.copy()
    merged.update(config)
    return merged

def save_config(cfg: dict):
    get_config_path().write_text(json.dumps(cfg, indent=2))
