from rich.console import Console

_console = Console()

def pinfo(msg: str):
    _console.print(f"[bold white]INFO:[/bold white] {msg}")

def pwarn(msg: str):
    _console.print(f"[bold yellow]WARN:[/bold yellow] {msg}")

def perr(msg: str):
    _console.print(f"[bold red]ERROR:[/bold red] {msg}")
