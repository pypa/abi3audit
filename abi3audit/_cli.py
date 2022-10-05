"""
The `abi3audit` CLI.
"""

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from typing import Any, DefaultDict

from rich.logging import RichHandler

from abi3audit._audit import AuditError, AuditResult, audit
from abi3audit._extract import (
    Extractor,
    InvalidSpec,
    PyPISpec,
    SharedObjectSpec,
    WheelSpec,
    make_spec,
)
from abi3audit._object import SharedObject
from abi3audit._state import console, status

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("ABI3AUDIT_LOGLEVEL", "INFO").upper(),
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console)],
)


# TODO: Put these helpers somewhere else.
def _green(s: str) -> str:
    return f"[green]{s}[/green]"


def _yellow(s: str) -> str:
    return f"[yellow]{s}[/yellow]"


def _red(s: str) -> str:
    return f"[red]{s}[/red]"


def _colornum(n: int) -> str:
    if n == 0:
        return _green(str(n))
    return _red(str(n))


class SpecResults:
    def __init__(self) -> None:
        # Map of extractor -> shared object -> audit result
        self._results: DefaultDict[Extractor, list[AuditResult]] = defaultdict(list)
        self._bad_abi3_version_counts: DefaultDict[SharedObject, int] = defaultdict(int)
        self._abi3_violation_counts: DefaultDict[SharedObject, int] = defaultdict(int)

    def add(self, extractor: Extractor, so: SharedObject, result: AuditResult) -> None:
        self._results[extractor].append(result)

        if result.computed > result.baseline:
            self._bad_abi3_version_counts[so] += 1

        self._abi3_violation_counts[so] += len(result.non_abi3_symbols)

    def summarize_all(self) -> str:
        pass

    def summarize_extraction(self, extractor: Extractor) -> str:
        spec_results = self._results[extractor]

        if not spec_results:
            return _yellow(f":person_shrugging: nothing auditable found in {extractor.spec}")

        abi3_version_counts = sum(self._bad_abi3_version_counts[res.so] for res in spec_results)
        abi3_violations = sum(self._abi3_violation_counts[res.so] for res in spec_results)
        return (
            f":information_desk_person: {extractor}: {len(spec_results)} extensions scanned; "
            f"{_colornum(abi3_version_counts)} ABI version mismatches and "
            f"{_colornum(abi3_violations)} ABI violations found"
        )

    def json(self) -> dict[str, Any]:
        """
        Returns a JSON-serializable dictionary representation of this `SpecResults`.
        """

        # TODO(ww): These inner helpers could definitely be consolidated.
        def _one_object(results: list[AuditResult]) -> dict[str, Any]:
            # NOTE: Anything else indicates a logic error.
            assert len(results) == 1
            return {"name": results[0].so.path.name, "result": results[0].json()}

        def _one_wheel(results: list[AuditResult]) -> list[dict[str, Any]]:
            sos = []
            for result in results:
                sos.append(
                    {
                        "name": result.so.path.name,
                        "result": result.json(),
                    }
                )
            return sos

        def _one_package(results: list[AuditResult]) -> dict[str, Any]:
            sos_by_wheel = defaultdict(list)
            for result in results:
                # NOTE: mypy can't see that this is never None in this context.
                wheel_name = result.so._extractor.parent.path.name  # type: ignore[union-attr]
                sos_by_wheel[wheel_name].append(
                    {
                        "name": result.so.path.name,
                        "result": result.json(),
                    }
                )
            return sos_by_wheel

        def _one_extractor(extractor: Extractor, results: list[AuditResult]) -> dict[str, Any]:
            body: dict[str, Any]
            match extractor.spec:
                case WheelSpec(_):
                    body = {"kind": "wheel", "wheel": _one_wheel(results)}
                case SharedObjectSpec(_):
                    body = {"kind": "object", "object": _one_object(results)}
                case PyPISpec(_):
                    body = {"kind": "package", "package": _one_package(results)}
            return body

        summary: dict[str, Any] = {}
        specs = summary["specs"] = {}
        for extractor, results in self._results.items():
            specs[extractor.spec] = _one_extractor(extractor, results)

        return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="abi3audit",
        description="Scans Python extensions for abi3 violations and inconsistencies",
    )
    parser.add_argument(
        "specs",
        type=make_spec,
        metavar="SPEC",
        nargs="+",
        help="the files or other dependency specs to scan",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help=(
            "emit debug statements; this setting also overrides `ABI3AUDIT_LOGLEVEL` and "
            "is equivalent to setting it to `debug`"
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help=("give more output, including pretty-printed results for each audit step"),
    )
    parser.add_argument(
        "-R", "--report", action="store_true", help="generate a JSON report; uses --output"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="the path to write the JSON report to (default: stdout)",
    )
    parser.add_argument(
        "-S",
        "--strict",
        action="store_true",
        help="fail the entire audit if an individual audit step fails",
    )
    args = parser.parse_args()

    if args.debug:
        logging.root.setLevel("DEBUG")

    logger.debug(f"parsed arguments: {args}")

    results = SpecResults()
    with status:
        for spec in set(args.specs):
            status.update(f"auditing {spec}")
            try:
                extractor = spec._extractor()
            except InvalidSpec as e:
                console.log(f"[red]:thumbs_down: processing error: {e}")
                sys.exit(1)

            for so in extractor:
                status.update(f"{spec}: auditing {so}")

                try:
                    result = audit(so)
                except AuditError as exc:
                    # TODO(ww): Refine exceptions and error states here.
                    console.log(f"[red]:skull: {so}: auditing error: {exc}")
                    if args.strict:
                        sys.exit(1)
                    continue

                results.add(extractor, so, result)
                if not result and args.verbose:
                    console.log(result)

            console.log(results.summarize_extraction(extractor))

    if args.report:
        print(json.dumps(results.json()), file=args.output)
