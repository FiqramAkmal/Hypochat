import typer
from hypochat import __version__

app = typer.Typer(
    name="hypochat",
    help="[Hypochat] Secure terminal chat over Nostr relay network.",
    add_completion=False,
    rich_markup_mode="rich",
)

relay_app = typer.Typer(help="Manage Nostr relay list.")
privacy_app = typer.Typer(help="Manage privacy defaults.")
app.add_typer(relay_app, name="relay")
app.add_typer(privacy_app, name="privacy")

# ── IDENTITY ──────────────────────────────────────────────

@app.command()
def init(
    password: str | None = typer.Option(None, "--password", help="Key-store password; omit to be prompted"),
):
    """Generate new identity and save locally."""
    from hypochat.app import cmd_init
    cmd_init(password)

@app.command()
def id(
    password: str | None = typer.Option(None, "--password", help="Key-store password; omit to be prompted"),
):
    """Show your Public ID (npub)."""
    from hypochat.app import cmd_id
    cmd_id(password)

@app.command()
def export(
    password: str | None = typer.Option(None, "--password", help="Key-store password; omit to be prompted"),
):
    """Show your private recovery key. Keep this secret!"""
    from hypochat.app import cmd_export
    cmd_export(password)

@app.command("import")
def import_key(
    nsec: str = typer.Argument(..., help="Your nsec private key"),
    password: str | None = typer.Option(None, "--password", help="Key-store password; omit to be prompted"),
):
    """Import identity from private key (nsec)."""
    from hypochat.app import cmd_import
    cmd_import(nsec, password)

# ── CONTACTS ──────────────────────────────────────────────

@app.command()
def add(
    public_id: str = typer.Argument(..., help="Contact's npub or hex public key"),
    name: str = typer.Option(..., "--name", "-n", help="Nickname for this contact"),
):
    """Add a contact by their Public ID."""
    from hypochat.app import cmd_add
    cmd_add(public_id, name)

@app.command()
def contacts():
    """List all contacts."""
    from hypochat.app import cmd_contacts
    cmd_contacts()

@app.command()
def doctor(
    password: str | None = typer.Option(None, "--password", help="Key-store password; optional, used to verify identity unlock"),
):
    """Run local diagnostics for Tor, storage, config, and dependencies."""
    from hypochat.app import cmd_doctor
    cmd_doctor(password)

@app.command()
def remove(nickname: str = typer.Argument(..., help="Nickname to remove")):
    """Remove a contact by nickname."""
    from hypochat.app import cmd_remove
    cmd_remove(nickname)

# ── CHAT ──────────────────────────────────────────────────

@app.command()
def chat(
    target: str = typer.Argument(..., help="Nickname or npub to chat with"),
    password: str | None = typer.Option(None, "--password", help="Key-store password; omit to be prompted"),
    tor: bool | None = typer.Option(None, "--tor/--no-tor", help="Best-effort Tor proxy mode"),
    store_history: bool | None = typer.Option(None, "--store-history/--no-store-history", help="Persist local chat history"),
):
    """Start a chat session."""
    from hypochat.app import cmd_chat
    cmd_chat(target, password=password, tor=tor, store_history=store_history)

@app.command()
def ghost(
    target: str | None = typer.Argument(None, help="Nickname or npub to chat with from an ephemeral identity"),
    tor: bool | None = typer.Option(None, "--tor/--no-tor", help="Best-effort Tor proxy mode"),
):
    """Start a one-time ghost session with temporary identity."""
    from hypochat.app import cmd_ghost
    cmd_ghost(target=target, tor=tor)

# ── RELAYS ────────────────────────────────────────────────

@relay_app.command("list")
def relay_list():
    """Show all active relays."""
    from hypochat.app import cmd_relay_list
    cmd_relay_list()

@relay_app.command("add")
def relay_add(url: str = typer.Argument(..., help="Relay URL (wss://...)")):
    """Add a relay."""
    from hypochat.app import cmd_relay_add
    cmd_relay_add(url)

@relay_app.command("remove")
def relay_remove(url: str = typer.Argument(..., help="Relay URL to remove")):
    """Remove a relay."""
    from hypochat.app import cmd_relay_remove
    cmd_relay_remove(url)


@privacy_app.command("set")
def privacy_set(
    tor: bool | None = typer.Option(None, "--tor/--no-tor", help="Persist best-effort Tor mode"),
    store_history: bool | None = typer.Option(None, "--store-history/--no-store-history", help="Persist local chat history default"),
    tor_proxy: str | None = typer.Option(None, "--tor-proxy", help="SOCKS proxy URL, default socks5://127.0.0.1:9050"),
    privacy_mode: str | None = typer.Option(None, "--privacy-mode", help="usable-sync or strict-no-trace"),
):
    """Update privacy defaults."""
    from hypochat.app import cmd_set_privacy
    cmd_set_privacy(use_tor=tor, store_history=store_history, tor_proxy=tor_proxy, privacy_mode=privacy_mode)

# ── VERSION ───────────────────────────────────────────────

@app.command()
def version():
    """Show version."""
    from rich.console import Console
    Console().print(f"[bright_cyan]Hypochat CLI[/] v{__version__}")
