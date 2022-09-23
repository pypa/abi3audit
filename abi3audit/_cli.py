"""
The `abi3audit` CLI.
"""

import argparse
import logging
import os
import sys
from collections import defaultdict

from abi3audit._audit import audit
from abi3audit._extract import InvalidSpec, Spec, extractor
from abi3audit._state import console, status

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

    if args.verbose:
        logging.root.setLevel("DEBUG")

    logger.debug(f"parsed arguments: {args}")

    results_by_spec = defaultdict(list)
    with status:
        for spec in args.specs:
            status.update(f"auditing {spec}")
            try:
                extractor_ = extractor(spec)
            except InvalidSpec as e:
                console.log(f"[red]:thumbs_down: processing error: {e}")
                sys.exit(1)

            results = defaultdict(list)
            bad_abi3_version_count = 0
            abi3_violation_count = 0
            for so in extractor_:
                status.update(f"{spec}: auditing {so}")

                try:
                    result = audit(so)
                except Exception as exc:
                    # TODO(ww): Refine exceptions and error states here.
                    console.log(f"[red]:thumbs_down: {exc}")
                    continue

                if result.computed > result.baseline:
                    console.log(
                        f"[red]:thumbs_down: {so} is {result.computed}, which is later than "
                        f"{result.baseline} due to {result.future_abi3_symbols}"
                    )
                    bad_abi3_version_count += 1
                elif result.non_abi3_symbols:
                    console.log(
                        f"[red]:thumbs_down: {so} has non-abi3 symbols: "
                        f"{result.non_abi3_symbols}"
                    )
                    abi3_violation_count += 1
                results[so].append(result)

            if not results:
                console.log(f"[yellow]:person_shrugging: nothing auditable found in {spec}")
            else:
                # TODO: Ugly. There has to be a better way to do this.
                if bad_abi3_version_count:
                    bad_abi3_version_count = f"[red]{bad_abi3_version_count}[/red]"
                else:
                    bad_abi3_version_count = f"[green]{bad_abi3_version_count}[/green]"

                if abi3_violation_count:
                    abi3_violation_count = f"[red]{abi3_violation_count}[/red]"
                else:
                    abi3_violation_count = f"[green]{abi3_violation_count}[/green]"

                console.log(
                    f":information_desk_person: {spec}: {len(results)} extensions scanned, "
                    f"{bad_abi3_version_count} abi3 version errors, "
                    f"{abi3_violation_count} abi3 violations"
                )
                results_by_spec[spec] = results
