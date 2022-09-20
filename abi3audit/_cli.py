"""
The `abi3audit` CLI.
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console


def main():
    parser = argparse.ArgumentParser(
        description="Scans Python wheels for abi3 violations and inconsistencies"
    )
    parser.add_argument("files", type=Path, metavar="FILE", nargs="+", help="the file(s) to scan")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help=(
            "give more output; this setting overrides `ABI3AUDIT_LOGLEVEL` and "
            "is equivalent to setting it to `debug`"
        ),
    )

    args = parser.parse_args()
    console = Console(log_path=False)

    with console.status(f"[bold green]Processing {len(args.files)} inputs") as status:
        for filename in args.files:
            status.update(f"[bold green]Processing {filename.name}")

            import time
            time.sleep(1)

            match filename.suffix:
                case ".whl":
                    pass
                case ".so" | ".pyd" | ".dylib":
                    pass
                case _:
                    console.log(f"[bold red]unrecognized file suffix: '{filename}'")
                    sys.exit(1)
