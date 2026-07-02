from hypochat.storage.config_store import load_config, save_config

def get_relays() -> list[str]:
    return load_config().get("relays", [])

def add_relay(url: str):
    cfg = load_config()
    relays = cfg.get("relays", [])
    if url not in relays:
        relays.append(url)
    cfg["relays"] = relays
    save_config(cfg)

def remove_relay(url: str) -> bool:
    cfg = load_config()
    relays = cfg.get("relays", [])
    if url not in relays:
        return False
    cfg["relays"] = [r for r in relays if r != url]
    save_config(cfg)
    return True