"""
`abi3audit` CLI state, broken out to avoid circular imports.
"""

from rich.console import Console

console = Console(log_path=False)
status = console.status("[bold green]Processing inputs", spinner="clock")
