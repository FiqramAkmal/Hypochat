import time
from nostr_sdk import EventBuilder, Kind, PublicKey

def build_dm_event(keys, recipient_npub: str, ciphertext: str):
    recipient_pk = PublicKey.parse(recipient_npub)
    # NIP-04 DM: Kind 4
    builder = EventBuilder.encrypted_direct_msg(keys, recipient_pk, ciphertext, None)
    return builder.sign_with_keys(keys)