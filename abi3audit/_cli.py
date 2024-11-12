"""
The `abi3audit` CLI.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from typing import Any

from abi3info.models import PyVersion
from rich import traceback
from rich.logging import RichHandler

from abi3audit._audit import AuditError, AuditResult, audit
from abi3audit._extract import (
    Extractor,
    ExtractorError,
    InvalidSpec,
    PyPISpec,
    SharedObjectSpec,
    WheelSpec,
    make_specs,
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

traceback.install(show_locals=True)


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


class _PyVersionAction(argparse.Action):
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: Any = None,
    ) -> None:
        try:
            pyversion = self._ensure_pyversion(values)
        except ValueError as exc:
            raise argparse.ArgumentError(self, str(exc))
        setattr(namespace, self.dest, pyversion)

    @classmethod
    def _ensure_pyversion(cls, version: str) -> PyVersion:
        error_msg = f"must have syntax '3.x', with x>=2; you gave '{version}'"
        try:
            pyversion = PyVersion.parse_dotted(version)
        except Exception:
            raise ValueError(error_msg)
        if pyversion.major != 3 or pyversion.minor < 2:
            raise ValueError(error_msg)
        return pyversion


class SpecResults:
    def __init__(self) -> None:
        # Map of extractor -> shared object -> audit result
        self._results: defaultdict[Extractor, list[AuditResult]] = defaultdict(list)
        self._bad_abi3_version_counts: defaultdict[SharedObject, int] = defaultdict(int)
        self._abi3_violation_counts: defaultdict[SharedObject, int] = defaultdict(int)

    def add(self, extractor: Extractor, so: SharedObject, result: AuditResult) -> None:
        self._results[extractor].append(result)

        if result.computed > result.baseline:
            self._bad_abi3_version_counts[so] += 1

        self._abi3_violation_counts[so] += len(result.non_abi3_symbols)

    def summarize_extraction(self, extractor: Extractor, summary: bool) -> str | None:
        spec_results = self._results[extractor]

        if not spec_results:
            return _yellow(f":person_shrugging: nothing auditable found in {extractor.spec}")

        abi3_version_counts = sum(self._bad_abi3_version_counts[res.so] for res in spec_results)
        abi3_violations = sum(self._abi3_violation_counts[res.so] for res in spec_results)
        if summary or abi3_violations > 0 or abi3_version_counts > 0:
            return (
                f":information_desk_person: {extractor}: {len(spec_results)} extensions scanned; "
                f"{_colornum(abi3_version_counts)} ABI version mismatches and "
                f"{_colornum(abi3_violations)} ABI violations found"
            )
        else:
            return None

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
            if isinstance(extractor.spec, WheelSpec):
                body = {"kind": "wheel", "wheel": _one_wheel(results)}
            elif isinstance(extractor.spec, SharedObjectSpec):
                body = {"kind": "object", "object": _one_object(results)}
            elif isinstance(extractor.spec, PyPISpec):
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
        "-s",
        "--summary",
        action="store_true",
        help="always output a summary even if there are no violations/ABI version mismatches",
    )
    parser.add_argument(
        "-S",
        "--strict",
        action="store_true",
        help="fail the entire audit if an individual audit step fails",
    )
    parser.add_argument(
        "--assume-minimum-abi3",
        action=_PyVersionAction,
        help="assumed abi3 version (3.x, with x>=2) if it cannot be detected",
    )
    args = parser.parse_args()

    if args.debug:
        logging.root.setLevel("DEBUG")

    specs = []
    for spec in args.specs:
        try:
            specs.extend(make_specs(spec, assume_minimum_abi3=args.assume_minimum_abi3))
        except InvalidSpec as e:
            console.log(f"[red]:thumbs_down: processing error: {e}")
            sys.exit(1)

    logger.debug(f"parsed arguments: {args}")

    results = SpecResults()
    all_passed = True
    with status:
        for spec in specs:
            status.update(f"auditing {spec}")
            try:
                extractor = spec._extractor()
            except ExtractorError as e:
                console.log(f"[red]:thumbs_down: processing error: {e}")
                sys.exit(1)

            for so in extractor:
                status.update(f"{spec}: auditing {so}")

                try:
                    result = audit(so, assume_minimum_abi3=args.assume_minimum_abi3)
                    all_passed = all_passed and bool(result)
                except AuditError as exc:
                    # TODO(ww): Refine exceptions and error states here.
                    console.log(f"[red]:skull: {so}: auditing error: {exc}")
                    if args.strict:
                        sys.exit(1)
                    continue

                results.add(extractor, so, result)
                if not result and args.verbose:
                    console.log(result)

            log_message = results.summarize_extraction(extractor, args.summary)
            if log_message:
                console.log(log_message)

    if args.report:
        print(json.dumps(results.json()), file=args.output)

    if not all_passed:
        sys.exit(1)
