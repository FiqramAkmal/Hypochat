from nostr_sdk import Keys, PublicKey, SecretKey

def generate_keys() -> dict:
    keys = Keys.generate()
    return {
        "nsec": keys.secret_key().to_bech32(),
        "npub": keys.public_key().to_bech32(),
        "hex_private": keys.secret_key().to_hex(),
        "hex_public": keys.public_key().to_hex(),
    }

def keys_from_nsec(nsec: str) -> dict:
    keys = Keys.parse(nsec)
    return {
        "nsec": keys.secret_key().to_bech32(),
        "npub": keys.public_key().to_bech32(),
        "hex_private": keys.secret_key().to_hex(),
        "hex_public": keys.public_key().to_hex(),
    }

def npub_to_hex(npub: str) -> str:
    return PublicKey.parse(npub).to_hex()