from rich.console import Console
from rich.panel import Panel
from rich import box

console = Console()

def print_banner():
    banner_text = (
        "[bright_cyan]╔══════════════════════════════════════╗[/]\n"
        "[bright_cyan]║[/]  [bright_green]    H Y P O C H A T   C L I    [/]  [bright_cyan]   ║[/]\n"
        "[bright_cyan]║[/]  [grey50]secure chat without own server[/]  [bright_cyan]    ║[/]\n"
        "[bright_cyan]╚══════════════════════════════════════╝[/]"
    )
    console.print(banner_text)
