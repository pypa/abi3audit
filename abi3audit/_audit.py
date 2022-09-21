"""
Core auditing logic for shared objects.
"""

from dataclasses import dataclass
from typing import Optional

from abi3info import DATAS, FUNCTIONS
from abi3info.models import PyVersion

from abi3audit._object import SharedObject


@dataclass(frozen=True, eq=True, slots=True)
class AuditResult:
    so: SharedObject
    baseline: Optional[PyVersion]
    computed: Optional[PyVersion]
    passed: bool

    @property
    def can_downgrade_to(self) -> PyVersion:
        raise ValueError

    def __bool__(self) -> bool:
        return self.passed


@dataclass(frozen=True, eq=True, slots=True)
class AuditSuccess(AuditResult):
    passed: bool = True


@dataclass(frozen=True, eq=True, slots=True)
class AuditFailure(AuditResult):
    passed: bool = False


def audit(so: SharedObject) -> AuditResult:
    baseline = so.abi3_version()
    computed = None
    for sym in so:
        maybe_abi3 = FUNCTIONS.get(sym)
        if maybe_abi3 is None:
            maybe_abi3 = DATAS.get(sym)

        if maybe_abi3 is not None:
            if computed is None or maybe_abi3.added > computed:
                computed = maybe_abi3.added
        elif sym.name.startswith("Py_") or sym.name.startswith("_Py_"):
            return AuditFailure(so, baseline, computed)

    # Finally, the moment of truth: if the computed ABI is higher than the
    # baseline ABI, then we know that the shared object's containing wheel
    # is tagged lower than it should be.
    if baseline and computed > baseline:
        return AuditFailure(so, baseline, computed)
    return AuditSuccess(so, baseline, computed)
