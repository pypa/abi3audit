"""
The `abi3audit` CLI.
"""

import argparse
import logging
import os
import sys

from rich.console import Console

from abi3audit._audit import audit
from abi3audit._extract import InvalidSpec, Spec, extractor

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get("ABI3AUDIT_LOGLEVEL", "INFO").upper())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scans Python wheels for abi3 violations and inconsistencies"
    )
    parser.add_argument(
        "specs",
        type=Spec,
        metavar="SPEC",
        nargs="+",
        help="the files or other dependency specs to scan",
    )
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

    with console.status(
        f"[bold green]Processing {len(args.specs)} inputs", spinner="clock"
    ) as status:
        for spec in args.specs:
            status.update(f"[bold green]Auditing {spec}")
            try:
                ex = extractor(spec)
            except InvalidSpec as e:
                console.log(f"[bold red]Processing error: {e}")
                sys.exit(1)

            for so in ex:
                status.update(f"[bold green]{spec}: auditing {so}")

                try:
                    result = audit(so)
                except Exception as exc:
                    # TODO(ww): Refine exceptions and error states here.
                    console.log(f"[bold red]:thumbs_down: {exc}")
                    continue

                if result.computed > result.baseline:
                    console.log(
                        f"[bold red]:thumbs_down: {so} is {result.computed}, which is later than "
                        f"{result.baseline} due to {result.future_abi3_symbols}"
                    )
                elif result.non_abi3_symbols:
                    console.log(
                        f"[bold red]:thumbs_down: {so} has non-abi3 symbols: "
                        f"{result.non_abi3_symbols}"
                    )
                else:
                    console.log(f"[bold green]:thumbs_up: {so} looks good!")
