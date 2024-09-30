"""
Core auditing logic for shared objects.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from abi3info import DATAS, FUNCTIONS
from abi3info.models import Data, Function, PyVersion, Symbol
from rich.console import Console, ConsoleOptions, RenderResult
from rich.table import Table

from abi3audit._object import SharedObject
from abi3audit._state import status

logger = logging.getLogger(__name__)

# A handpicked exclusion list of symbols that are not strictly in the limited API
# or stable ABI, but in practice always appear in ABI3-compatible code.
# Since they are not listed in CPython's `stable_abi.toml`, we maintain them here separately.
# For more information, see https://github.com/pypa/abi3audit/issues/85
# and https://github.com/wjakob/nanobind/discussions/500 .
_ALLOWED_SYMBOLS: set[str] = {"Py_XDECREF"}


class AuditError(Exception):
    pass


@dataclass(frozen=True, eq=True)
class AuditResult:
    so: SharedObject
    baseline: PyVersion
    computed: PyVersion
    non_abi3_symbols: set[Symbol]
    future_abi3_objects: set[Function | Data]

    def is_abi3(self) -> bool:
        return len(self.non_abi3_symbols) == 0

    def is_abi3_baseline_compatible(self) -> bool:
        # TODO(ww): Why does PyVersion.__le__ not typecheck as bool?
        return bool(self.baseline >= self.computed)

    def json(self) -> dict[str, Any]:
        return {
            "is_abi3": self.is_abi3(),
            "is_abi3_baseline_compatible": self.is_abi3_baseline_compatible(),
            "baseline": str(self.baseline),
            "computed": str(self.computed),
            "non_abi3_symbols": [sym.name for sym in self.non_abi3_symbols],
            "future_abi3_objects": {
                obj.symbol.name: str(obj.added) for obj in self.future_abi3_objects
            },
        }

    def __bool__(self) -> bool:
        return self.is_abi3() and self.is_abi3_baseline_compatible()

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        # Violating abi3 entirely is more "serious" than having the wrong abi3
        # version, so we check for it first when deciding the Rich representation.
        if self.non_abi3_symbols:
            yield f"[red]:thumbs_down: [green]{self.so}[/green] has non-ABI3 symbols"

            table = Table()
            table.add_column("Symbol")
            for sym in self.non_abi3_symbols:
                table.add_row(sym.name)

            yield table
        elif self.computed > self.baseline:
            yield (
                f"[yellow]:thumbs_down: [green]{self.so}[/green] uses the Python "
                f"[blue]{self.computed}[/blue] ABI, but is tagged for the Python "
                f"[red]{self.baseline}[/red] ABI"
            )

            table = Table()
            table.add_column("Symbol")
            table.add_column("Version")
            for obj in self.future_abi3_objects:
                table.add_row(obj.symbol.name, str(obj.added))
            yield table
        else:
            yield f"[green]:thumbs_up: {self.so}"


def audit(so: SharedObject, assume_minimum_abi3: PyVersion = PyVersion(3, 2)) -> AuditResult:
    # We might fail to retrieve a minimum abi3 baseline if our context
    # (the shared object or its containing wheel) isn't actually tagged
    # as abi3 compatible.
    baseline = so.abi3_version(assume_lowest=assume_minimum_abi3)
    if baseline is None:
        raise AuditError("failed to determine ABI version baseline: not abi3 tagged?")

    # In principle, our computed abi3 version could be lower than our baseline version,
    # if for example an abi3-py36 wheel only used interfaces present in abi3-py35.
    # But this wouldn't actually *make* the wheel abi3-py35, since CPython
    # does not guarantee backwards compatibility between abi3 versions.
    computed = baseline
    non_abi3_symbols = set()
    future_abi3_objects = set()

    status.update(f"{so}: analyzing symbols")
    logger.debug(f"auditing {so}")
    try:
        for sym in so:
            maybe_abi3 = FUNCTIONS.get(sym)
            if maybe_abi3 is None:
                maybe_abi3 = DATAS.get(sym)

            if maybe_abi3 is not None:
                if maybe_abi3.added > computed:
                    computed = maybe_abi3.added
                if maybe_abi3.added > baseline:
                    future_abi3_objects.add(maybe_abi3)
            elif sym.name.startswith(("Py", "_Py")):
                # Exclude module initialization symbols. Technically
                # this should always be `PyInit_{filename}` but there can
                # be multiple if a shared object contains multiple extensions;
                # see https://github.com/pypa/abi3audit/issues/111.
                if sym.name.startswith("PyInit_"):
                    continue
                # Local symbols are fine, since they are inlined functions
                # from the CPython limited API.
                if sym not in _ALLOWED_SYMBOLS and sym.visibility != "local":
                    non_abi3_symbols.add(sym)
    except Exception as exc:
        raise AuditError(f"failed to collect symbols in shared object: {exc}")

    return AuditResult(so, baseline, computed, non_abi3_symbols, future_abi3_objects)
