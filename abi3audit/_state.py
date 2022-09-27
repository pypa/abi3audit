"""
`abi3audit` CLI state, broken out to avoid circular imports.
"""

import sys

from rich.console import Console

console = Console(log_path=False, file=sys.stderr)
status = console.status("[green]Processing inputs", spinner="clock")
