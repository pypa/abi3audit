"""
Core auditing logic for shared objects.
"""

from dataclasses import dataclass
from typing import Optional

from abi3info import DATAS, FUNCTIONS
from abi3info.models import PyVersion, Symbol

from abi3audit._object import SharedObject


@dataclass(frozen=True, eq=True, slots=True)
class AuditResult:
    so: SharedObject
    baseline: Optional[PyVersion]
    computed: Optional[PyVersion]
    non_abi3_symbols: list[Symbol]

    def __bool__(self) -> bool:
        # Misuse resistance: audit results contain too much information
        # to be reduced to a single true/false dimension, so prevent
        # users from assuming that they're truthy when they "succeed."
        return False


def audit(so: SharedObject) -> AuditResult:
    baseline = so.abi3_version()
    computed = None
    non_abi3_symbols = []
    for sym in so:
        maybe_abi3 = FUNCTIONS.get(sym)
        if maybe_abi3 is None:
            maybe_abi3 = DATAS.get(sym)

        if maybe_abi3 is not None:
            if computed is None or maybe_abi3.added > computed:
                computed = maybe_abi3.added
        elif sym.name.startswith("Py_") or sym.name.startswith("_Py_"):
            non_abi3_symbols.append(sym)

    return AuditResult(so, baseline, computed, non_abi3_symbols)
