from hypochat.core.keys import generate_keys, keys_from_nsec, npub_to_hex

def test_generate_keys():
    k = generate_keys()
    assert k["npub"].startswith("npub1")
    assert k["nsec"].startswith("nsec1")

def test_roundtrip():
    k = generate_keys()
    k2 = keys_from_nsec(k["nsec"])
    assert k["npub"] == k2["npub"]

def test_npub_to_hex():
    k = generate_keys()
    h = npub_to_hex(k["npub"])
    assert len(h) == 64