from rich.console import Console
from rich.panel import Panel
from hypochat.ui.theme import COLORS

console = Console()

def ok(msg: str):
    console.print(f"[{COLORS['success']}][+][/] {msg}")

def err(msg: str):
    console.print(f"[{COLORS['error']}][!][/] {msg}")

def warn(msg: str):
    console.print(f"[{COLORS['warn']}][!][/] {msg}")

def info(msg: str):
    console.print(f"[{COLORS['info']}][*][/] {msg}")

def dim(msg: str):
    console.print(f"[{COLORS['dim']}]{msg}[/]")