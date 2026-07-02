APP_NAME = "hypochat"
DEFAULT_RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.primal.net",
]
GIFT_WRAP_KIND = 1059
PRIVATE_MSG_KIND = 14
DEFAULT_TOR_PROXY = "socks5://127.0.0.1:9050"
DEFAULT_PRIVACY_MODE = "usable-sync"
PAD_BLOCK_SIZE = 128
DEFAULT_CONFIG = {
    "relays": DEFAULT_RELAYS,
    "store_history": False,
    "persist_transcript": True,
    "persist_peer_state": True,
    "privacy_mode": DEFAULT_PRIVACY_MODE,
    "use_tor": True,
    "tor_proxy": DEFAULT_TOR_PROXY,
}
