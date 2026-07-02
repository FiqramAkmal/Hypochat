import json
from datetime import datetime, timezone
from hypochat.storage import get_contacts_path

def load_contacts() -> list:
    p = get_contacts_path()
    if not p.exists():
        return []
    return json.loads(p.read_text())

def save_contacts(contacts: list):
    get_contacts_path().write_text(json.dumps(contacts, indent=2))

def add_contact(nickname: str, public_id: str):
    contacts = load_contacts()
    contacts.append({
        "nickname": nickname,
        "public_id": public_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    save_contacts(contacts)

def remove_contact(nickname: str) -> bool:
    contacts = load_contacts()
    new = [c for c in contacts if c["nickname"] != nickname]
    if len(new) == len(contacts):
        return False
    save_contacts(new)
    return True

def find_contact(target: str) -> dict | None:
    for c in load_contacts():
        if c["nickname"] == target or c["public_id"] == target:
            return c
    return None