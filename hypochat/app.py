import asyncio
import json
import os
import socket
from getpass import getpass
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from hypochat.chat.session import ChatSession
from hypochat.core.identity import create_identity, import_identity, load_identity
from hypochat.core.keys import generate_keys, npub_to_hex
from hypochat.nostr.client import NostrClient
from hypochat.nostr.relays import add_relay, get_relays, remove_relay
from hypochat.core.tor import TorManager
from hypochat.storage.config_store import load_config, save_config
from hypochat.storage import get_config_path, get_contacts_path, get_data_dir, get_history_dir, get_key_path, get_peer_state_dir
from hypochat.storage.key_store import load_key
from hypochat.storage.peer_state_store import get_last_seen
from hypochat.storage.transcript_store import get_last_transcript_timestamp, rewrite_sorted_transcript
from hypochat.storage.contact_store import (
    add_contact,
    find_contact,
    load_contacts,
    remove_contact,
)
from hypochat.ui.banner import print_banner
from hypochat.ui.console import err, info, ok, warn

console = Console()


def _doctor_add(rows: list[tuple[str, str, str]], component: str, status: str, detail: str):
    rows.append((component, status, detail))


def _doctor_status_style(status: str) -> str:
    return {
        "OK": "bright_green",
        "WARN": "yellow",
        "FAIL": "bright_red",
        "INFO": "bright_cyan",
    }.get(status, "white")


def _probe_tcp(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        try:
            sock.close()
        except Exception:
            pass


def _safe_json_load(path: Path) -> tuple[bool, object | None, str | None]:
    if not path.exists():
        return False, None, "missing"
    try:
        return True, json.loads(path.read_text()), None
    except Exception as exc:
        return True, None, str(exc)


def cmd_doctor(password: str | None = None):
    print_banner()
    console.print()
    rows: list[tuple[str, str, str]] = []

    data_dir = get_data_dir()
    _doctor_add(rows, "Data dir", "OK", str(data_dir))

    config_path = get_config_path()
    config_exists, config_payload, config_error = _safe_json_load(config_path)
    if not config_exists:
        _doctor_add(rows, "Config file", "WARN", f"Missing, defaults will be used at {config_path}")
        config = load_config()
    elif config_error:
        _doctor_add(rows, "Config file", "FAIL", f"Invalid JSON at {config_path}: {config_error}")
        config = None
    else:
        _doctor_add(rows, "Config file", "OK", str(config_path))
        try:
            config = _apply_privacy_mode(load_config())
            _doctor_add(rows, "Privacy config", "OK", f"mode={config['privacy_mode']} tor={config['use_tor']} history={config['store_history']}")
        except Exception as exc:
            _doctor_add(rows, "Privacy config", "FAIL", str(exc))
            config = None

    contacts_path = get_contacts_path()
    contacts_exists, contacts_payload, contacts_error = _safe_json_load(contacts_path)
    if not contacts_exists:
        _doctor_add(rows, "Contacts", "WARN", f"No contacts file yet at {contacts_path}")
    elif contacts_error:
        _doctor_add(rows, "Contacts", "FAIL", f"Invalid JSON at {contacts_path}: {contacts_error}")
    elif not isinstance(contacts_payload, list):
        _doctor_add(rows, "Contacts", "FAIL", "contacts.json must contain a list")
    else:
        _doctor_add(rows, "Contacts", "OK", f"{len(contacts_payload)} contact(s) loaded")

    key_path = get_key_path()
    if not key_path.exists():
        _doctor_add(rows, "Identity store", "WARN", f"Missing key store at {key_path}")
    else:
        try:
            payload = json.loads(key_path.read_text())
            version = payload.get("version")
            if version != 2:
                _doctor_add(rows, "Identity store", "FAIL", f"Unsupported key store version: {version}")
            else:
                _doctor_add(rows, "Identity store", "OK", f"Encrypted key store found at {key_path}")
                if password:
                    try:
                        key_data = load_key(password)
                        npub = key_data.get("npub", "unknown") if key_data else "unknown"
                        _doctor_add(rows, "Identity unlock", "OK", f"Password valid for {npub}")
                    except Exception as exc:
                        _doctor_add(rows, "Identity unlock", "FAIL", str(exc))
                else:
                    _doctor_add(rows, "Identity unlock", "INFO", "Skipped; pass --password to verify unlock")
        except Exception as exc:
            _doctor_add(rows, "Identity store", "FAIL", f"Unreadable key store: {exc}")

    history_dir = get_history_dir()
    peer_state_dir = get_peer_state_dir()
    _doctor_add(rows, "History dir", "OK", str(history_dir))
    _doctor_add(rows, "Peer state dir", "OK", str(peer_state_dir))

    try:
        history_count = len(list(history_dir.glob("*.json")))
        _doctor_add(rows, "Transcript cache", "INFO", f"{history_count} cached room file(s)")
    except Exception as exc:
        _doctor_add(rows, "Transcript cache", "FAIL", str(exc))

    try:
        peer_state_count = len(list(peer_state_dir.glob("*.json")))
        _doctor_add(rows, "Peer sync state", "INFO", f"{peer_state_count} peer-state file(s)")
    except Exception as exc:
        _doctor_add(rows, "Peer sync state", "FAIL", str(exc))

    relays = []
    if config is None:
        _doctor_add(rows, "Relays", "FAIL", "Skipped because config is invalid")
    else:
        relays = config.get("relays", [])
        if not isinstance(relays, list):
            _doctor_add(rows, "Relays", "FAIL", "Config relays must be a list")
        elif not relays:
            _doctor_add(rows, "Relays", "FAIL", "Relay list is empty")
        else:
            invalid_relays = [relay for relay in relays if not isinstance(relay, str) or not relay.startswith("wss://")]
            if invalid_relays:
                _doctor_add(rows, "Relays", "FAIL", f"Invalid relay entries: {', '.join(map(str, invalid_relays[:3]))}")
            else:
                _doctor_add(rows, "Relays", "OK", f"{len(relays)} relay(s) configured")

    try:
        import nostr_sdk  # noqa: F401
        _doctor_add(rows, "Dependency nostr_sdk", "OK", "Installed")
    except Exception as exc:
        _doctor_add(rows, "Dependency nostr_sdk", "FAIL", str(exc))

    try:
        import cryptography  # noqa: F401
        _doctor_add(rows, "Dependency cryptography", "OK", "Installed")
    except Exception as exc:
        _doctor_add(rows, "Dependency cryptography", "FAIL", str(exc))

    tor_manager = TorManager((config or load_config()).get("tor_proxy", "socks5://127.0.0.1:9050"))
    current_platform_key = tor_manager._platform_key()
    _doctor_add(rows, "Tor platform", "INFO", current_platform_key)

    bundle_ok, bundle_missing, bundle_root = tor_manager.validate_bundle_layout()
    bundle_binary = tor_manager.bundled_binary()
    if not bundle_ok or bundle_binary is None:
        detail = f"Missing current-platform bundle files: {', '.join(bundle_missing)}" if bundle_missing else "Bundled Tor files missing for this platform"
        _doctor_add(rows, "Tor bundle", "FAIL", detail)
    else:
        _doctor_add(rows, "Tor bundle", "OK", str(bundle_binary))

    bundle_report = tor_manager.validate_all_bundles()
    ready_count = sum(1 for item in bundle_report.values() if item['ok'])
    total_count = len(bundle_report)
    status = "OK" if ready_count == total_count else "WARN"
    _doctor_add(rows, "Tor packaging", status, f"{ready_count}/{total_count} bundled platform layouts complete")
    for platform_key, report in bundle_report.items():
        if report['ok']:
            continue
        missing = ', '.join(report['missing'][:4])
        _doctor_add(rows, f"Tor pkg {platform_key}", "WARN", f"Missing: {missing}")

    socks_open = _probe_tcp("127.0.0.1", 9050)
    if socks_open:
        _doctor_add(rows, "Tor SOCKS 9050", "OK", "Existing local SOCKS listener detected")
    else:
        _doctor_add(rows, "Tor SOCKS 9050", "WARN", "No listener on 127.0.0.1:9050 before launch")

    if config is not None and config.get("use_tor", True):
        runtime = tor_manager.start(wait_seconds=8.0)
        if runtime.proxy:
            source = "bundle started" if runtime.started else "existing SOCKS"
            _doctor_add(rows, "Tor startup", "OK", f"Using {source} via {runtime.proxy}")
        else:
            _doctor_add(rows, "Tor startup", "WARN", runtime.warning or "Tor did not become ready")
        tor_manager.stop()
    else:
        _doctor_add(rows, "Tor startup", "INFO", "Skipped because use_tor is disabled in config")

    table = Table(show_header=True, header_style="bold bright_cyan", border_style="grey50", title="[bright_green]Hypochat Doctor[/]")
    table.add_column("Component", style="white")
    table.add_column("Status", style="white", width=8)
    table.add_column("Detail", style="white")
    for component, status, detail in rows:
        table.add_row(component, f"[{_doctor_status_style(status)}]{status}[/]", detail)
    console.print(table)

    has_fail = any(status == "FAIL" for _component, status, _detail in rows)
    has_warn = any(status == "WARN" for _component, status, _detail in rows)
    console.print()
    if has_fail:
        err("Doctor found blocking issues.")
        raise SystemExit(1)
    if has_warn:
        warn("Doctor finished with warnings.")
    else:
        ok("Doctor finished cleanly.")


def _resolve_password(provided: str | None, confirm: bool = False) -> str:
    password = provided or os.environ.get("HYPOCHAT_PASSWORD")
    if password:
        return password

    first = getpass("Key-store password: ")
    if not first:
        raise SystemExit("Password cannot be empty.")

    if confirm:
        second = getpass("Confirm password: ")
        if first != second:
            raise SystemExit("Password confirmation mismatch.")

    return first


def _load_identity_or_exit(password: str | None) -> tuple[dict, str]:
    try:
        resolved_password = _resolve_password(password)
        identity = load_identity(resolved_password)
    except FileNotFoundError:
        err("No identity found. Run: [yellow]python -m hypochat init[/]")
        raise SystemExit(1)
    except ValueError as exc:
        err(str(exc))
        raise SystemExit(1)
    except Exception as exc:
        err(f"Failed to unlock identity: {exc}")
        raise SystemExit(1)

    if not identity:
        err("No identity found. Run: [yellow]python -m hypochat init[/]")
        raise SystemExit(1)

    return identity, resolved_password


def _resolve_target(target: str) -> tuple[str, str]:
    contact = find_contact(target)
    if contact:
        return contact["public_id"], contact["nickname"]

    try:
        npub_to_hex(target)
        return target, target[:12] + "..."
    except Exception:
        err(f"Unknown contact or invalid public ID: {target}")
        raise SystemExit(1)


def _resolve_runtime_config(tor: bool | None, store_history: bool | None) -> dict:
    config = load_config()
    if tor is not None:
        config["use_tor"] = tor
    if store_history is not None:
        config["store_history"] = store_history
    return config


def _start_tor_if_enabled(config: dict) -> tuple[TorManager | None, dict]:
    if not config.get("use_tor", False):
        return None, {"enabled": False, "warning": None, "proxy": None, "started": False, "using_bundle": False}

    manager = TorManager(config.get("tor_proxy"))
    status = manager.start()
    if status.proxy:
        config["tor_proxy"] = status.proxy
    else:
        config["use_tor"] = False
    return manager, {
        "enabled": status.enabled,
        "warning": status.warning,
        "proxy": status.proxy,
        "started": status.started,
        "using_bundle": status.using_bundle,
    }


def _apply_privacy_mode(config: dict) -> dict:
    mode = config.get("privacy_mode", "usable-sync")
    if mode not in {"usable-sync", "strict-no-trace"}:
        raise ValueError(f"Invalid privacy_mode: {mode}")
    if mode == "strict-no-trace":
        config["store_history"] = False
        config["persist_transcript"] = False
        config["persist_peer_state"] = False
    else:
        config.setdefault("persist_transcript", True)
        config.setdefault("persist_peer_state", True)
    return config


# ── IDENTITY ──────────────────────────────────────────────

def cmd_init(password: str | None):
    print_banner()
    if get_key_path().exists():
        warn("Identity already exists.")
        identity, _ = _load_identity_or_exit(password)
        ok(f"Your Public ID: [bright_cyan]{identity['npub']}[/]")
        return

    resolved_password = _resolve_password(password, confirm=True)
    identity = create_identity(resolved_password)
    ok("Identity created")
    ok(f"Your Public ID: [bright_cyan]{identity['npub']}[/]")
    console.print()
    warn("Backup your recovery key with: [yellow]python -m hypochat export[/]")
    warn("Private key is stored encrypted at rest.")


def cmd_id(password: str | None):
    identity, _ = _load_identity_or_exit(password)
    ok(f"Your Public ID: [bright_cyan]{identity['npub']}[/]")


def cmd_export(password: str | None):
    identity, _ = _load_identity_or_exit(password)
    console.print()
    warn("══════════════════════════════════════")
    warn("  SECURITY WARNING — PRIVATE KEY")
    warn("══════════════════════════════════════")
    warn("  Never share this with anyone.")
    warn("  Anyone with this key can impersonate you.")
    warn("══════════════════════════════════════")
    console.print()
    console.print(f"[bright_red]Recovery Key:[/] [yellow]{identity['nsec']}[/]")
    console.print()


def cmd_import(nsec: str, password: str | None):
    resolved_password = _resolve_password(password, confirm=True)
    identity = import_identity(nsec, resolved_password)
    ok("Identity imported")
    ok(f"Your Public ID: [bright_cyan]{identity['npub']}[/]")


# ── CONTACTS ──────────────────────────────────────────────

def cmd_add(public_id: str, name: str):
    try:
        npub_to_hex(public_id)
    except Exception:
        err(f"Invalid public ID: {public_id}")
        raise SystemExit(1)
    contacts = load_contacts()
    existing = next((c for c in contacts if c["nickname"] == name), None)
    if existing:
        err(f"Nickname '{name}' already exists. Remove it first with: python -m hypochat remove {name}")
        raise SystemExit(1)
    add_contact(name, public_id)
    ok(f"Contact added: [bright_cyan]{name}[/] → {public_id}")


def cmd_contacts():
    contacts = load_contacts()
    if not contacts:
        info("No contacts yet. Add one with: python -m hypochat add <public_id> --name <nickname>")
        return
    table = Table(
        show_header=True,
        header_style="bold bright_cyan",
        border_style="grey50",
        title="[bright_green]Contacts[/]",
    )
    table.add_column("Nickname", style="bright_green")
    table.add_column("Public ID", style="cyan")
    table.add_column("Added At", style="grey50")
    for contact in contacts:
        table.add_row(contact["nickname"], contact["public_id"], contact.get("created_at", "-"))
    console.print(table)


def cmd_remove(nickname: str):
    if remove_contact(nickname):
        ok(f"Contact '{nickname}' removed.")
    else:
        err(f"Contact '{nickname}' not found.")


# ── RELAYS ────────────────────────────────────────────────

def cmd_relay_list():
    relays = get_relays()
    table = Table(
        show_header=True,
        header_style="bold bright_cyan",
        border_style="grey50",
        title="[bright_green]Active Relays[/]",
    )
    table.add_column("Relay URL", style="cyan")
    for relay in relays:
        table.add_row(relay)
    console.print(table)


def cmd_relay_add(url: str):
    if not url.startswith("wss://"):
        err("Relay URL must start with wss://")
        raise SystemExit(1)
    add_relay(url)
    ok(f"Relay added: {url}")


def cmd_relay_remove(url: str):
    if remove_relay(url):
        ok(f"Relay removed: {url}")
    else:
        err(f"Relay not found: {url}")


# ── CHAT ──────────────────────────────────────────────────

def _print_session_header(peer_name: str, peer_npub: str, config: dict, my_npub: str, ephemeral: bool = False, tor_runtime: dict | None = None):
    print_banner()
    console.print()
    info("Connected relays:")
    for relay in get_relays():
        ok(f"  {relay}")
    console.print()
    mode = "ephemeral" if ephemeral else "persistent"
    info(f"Identity mode: [bright_cyan]{mode}[/]")
    info(f"Your Public ID: [bright_cyan]{my_npub}[/]")
    info(f"Chatting with: [bright_cyan]{peer_name}[/]")
    info(f"History storage: [bright_cyan]{'enabled' if config['store_history'] else 'disabled'}[/]")
    last_seen = get_last_seen(peer_npub)
    if last_seen > 0:
        last_seen_text = datetime.fromtimestamp(last_seen).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
        info(f"Last synced peer msg: [bright_cyan]{last_seen_text}[/]")
    else:
        info("Last synced peer msg: [bright_cyan]no synced messages yet[/]")
    last_activity = get_last_transcript_timestamp(peer_npub)
    if last_activity > 0:
        last_activity_text = datetime.fromtimestamp(last_activity).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
        info(f"Room last activity: [bright_cyan]{last_activity_text}[/]")
    else:
        info("Room last activity: [bright_cyan]empty room[/]")
    if tor_runtime and tor_runtime.get("enabled"):
        if tor_runtime.get("proxy"):
            ok(f"Tor active via {'bundled binary' if tor_runtime.get('using_bundle') else 'existing SOCKS proxy'}: {tor_runtime['proxy']}")
        if tor_runtime.get("warning"):
            warn(tor_runtime["warning"])
    elif config["use_tor"]:
        warn("Tor requested but unavailable; falling back to direct connection.")
    console.print("[grey50]─────────────────────────────────────[/]")
    info("Type /help for commands. /exit to quit.")


def _build_chat_header_status(peer_npub: str, config: dict | None = None) -> list[str]:
    lines = []
    if config and not config.get("persist_peer_state", True):
        lines.append("Last synced peer msg: disabled by strict-no-trace")
    else:
        last_seen = get_last_seen(peer_npub)
        if last_seen > 0:
            last_seen_text = datetime.fromtimestamp(last_seen).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
            lines.append(f"Last synced peer msg: {last_seen_text}")
        else:
            lines.append("Last synced peer msg: no synced messages yet")

    if config and not config.get("persist_transcript", True):
        lines.append("Room last activity: disabled by strict-no-trace")
    else:
        last_activity = get_last_transcript_timestamp(peer_npub)
        if last_activity > 0:
            last_activity_text = datetime.fromtimestamp(last_activity).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
            lines.append(f"Room last activity: {last_activity_text}")
        else:
            lines.append("Room last activity: empty room")
    return lines


def cmd_chat(target: str, password: str | None, tor: bool | None, store_history: bool | None):
    identity, resolved_password = _load_identity_or_exit(password)
    os.environ["HYPOCHAT_SESSION_PASSWORD"] = resolved_password
    peer_npub, peer_name = _resolve_target(target)
    config = _apply_privacy_mode(_resolve_runtime_config(tor, store_history))
    if config.get("persist_transcript", True):
        rewrite_sorted_transcript(peer_npub)
    tor_manager, tor_runtime = _start_tor_if_enabled(config)

    async def run():
        client = NostrClient(
            identity["nsec"],
            use_tor=config["use_tor"],
            tor_proxy=config["tor_proxy"],
            persist_peer_state=config.get("persist_peer_state", True),
        )
        await client.connect()
        await client.reset_session_context(peer_npub)
        session = ChatSession(
            client,
            peer_name,
            peer_npub,
            identity["npub"],
            store_history=config["store_history"],
            persist_transcript=config.get("persist_transcript", True),
            header_status_provider=lambda: _build_chat_header_status(peer_npub, config),
        )
        try:
            await session.run()
        finally:
            await client.disconnect()
            if tor_manager is not None:
                tor_manager.stop()

    _print_session_header(peer_name, peer_npub, config, identity["npub"], tor_runtime=tor_runtime)
    asyncio.run(run())
    info("Session ended.")


# ── GHOST MODE ────────────────────────────────────────────

def cmd_ghost(target: str | None = None, tor: bool | None = None):
    temp = generate_keys()
    config = _apply_privacy_mode(_resolve_runtime_config(tor, store_history=False))
    tor_manager, tor_runtime = _start_tor_if_enabled(config)
    peer_npub = None
    peer_name = None

    if target:
        peer_npub, peer_name = _resolve_target(target)
        if config.get("persist_transcript", True):
            rewrite_sorted_transcript(peer_npub)

    async def run():
        client = NostrClient(
            temp["nsec"],
            use_tor=config["use_tor"],
            tor_proxy=config["tor_proxy"],
            persist_peer_state=config.get("persist_peer_state", True),
        )
        await client.connect()
        try:
            if peer_npub:
                await client.reset_session_context(peer_npub)
                session = ChatSession(
                    client,
                    peer_name,
                    peer_npub,
                    temp["npub"],
                    store_history=False,
                    persist_transcript=config.get("persist_transcript", True),
                    header_status_provider=lambda: _build_chat_header_status(peer_npub, config),
                )
                await session.run()
            else:
                info("Ghost Mode — temporary identity (not saved)")
                ok(f"Temp Public ID: [bright_cyan]{temp['npub']}[/]")
                warn("Share this Temp Public ID to receive replies in this session.")
                warn("No local key or chat history will be stored.")
                if tor_runtime.get("enabled") and tor_runtime.get("proxy"):
                    ok(f"Tor active via {'bundled binary' if tor_runtime.get('using_bundle') else 'existing SOCKS proxy'}: {tor_runtime['proxy']}")
                if tor_runtime.get("warning"):
                    warn(tor_runtime['warning'])
                console.print("[grey50]─────────────────────────────────────[/]")
                info("Use `python -m hypochat ghost <npub>` on another terminal to start chatting.")
                while True:
                    await asyncio.sleep(1)
        finally:
            await client.disconnect()
            if tor_manager is not None:
                tor_manager.stop()

    if peer_npub:
        _print_session_header(peer_name, peer_npub, config, temp["npub"], ephemeral=True, tor_runtime=tor_runtime)
    else:
        print_banner()
        console.print()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        console.print()
        warn("Ghost identity destroyed. Goodbye.")


def cmd_set_privacy(use_tor: bool | None = None, store_history: bool | None = None, tor_proxy: str | None = None, privacy_mode: str | None = None):
    config = load_config()
    if use_tor is not None:
        config["use_tor"] = use_tor
    if store_history is not None:
        config["store_history"] = store_history
    if tor_proxy is not None:
        config["tor_proxy"] = tor_proxy
    if privacy_mode is not None:
        config["privacy_mode"] = privacy_mode
    try:
        config = _apply_privacy_mode(config)
    except ValueError as exc:
        err(str(exc))
        raise SystemExit(1)
    save_config(config)
    ok("Privacy config updated")
    ok(f"privacy_mode={config['privacy_mode']}")
    ok(f"use_tor={config['use_tor']}")
    ok(f"store_history={config['store_history']}")
    ok(f"persist_transcript={config['persist_transcript']}")
    ok(f"persist_peer_state={config['persist_peer_state']}")
    ok(f"tor_proxy={config['tor_proxy']}")
