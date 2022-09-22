"""
Core auditing logic for shared objects.
"""

from dataclasses import dataclass

from abi3info import DATAS, FUNCTIONS
from abi3info.models import PyVersion, Symbol

from abi3audit._object import SharedObject


@dataclass(frozen=True, eq=True, slots=True)
class AuditResult:
    so: SharedObject
    baseline: PyVersion
    computed: PyVersion
    non_abi3_symbols: set[Symbol]
    future_abi3_symbols: set[Symbol]

    def __bool__(self) -> bool:
        # Misuse resistance: audit results contain too much information
        # to be reduced to a single true/false dimension, so prevent
        # users from assuming that they're truthy when they "succeed."
        return False


def audit(so: SharedObject) -> AuditResult:
    baseline = so.abi3_version()
    # In principle, our computed abi3 version could be lower than our baseline version,
    # if for example an abi3-py36 wheel only used interfaces present in abi3-py35.
    # But this wouldn't actually *make* the wheel abi3-py35, since CPython
    # does not guarantee backwards compatibility between abi3 versions.
    computed = baseline
    non_abi3_symbols = set()
    future_abi3_symbols = set()
    for sym in so:
        maybe_abi3 = FUNCTIONS.get(sym)
        if maybe_abi3 is None:
            maybe_abi3 = DATAS.get(sym)

        if maybe_abi3 is not None:
            if maybe_abi3.added > computed:
                computed = maybe_abi3.added
            if maybe_abi3.added > baseline:
                future_abi3_symbols.add(sym)
        elif sym.name.startswith("Py_") or sym.name.startswith("_Py_"):
            non_abi3_symbols.add(sym)

    return AuditResult(so, baseline, computed, non_abi3_symbols, future_abi3_symbols)
