"""
Core auditing logic for shared objects.
"""

from dataclasses import dataclass
from typing import Optional

from abi3info import FUNCTIONS, DATAS
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


def audit(so: SharedObject) -> AuditResult:
    # TODO: Infer baseline from the shared object's filename + containing
    # wheel filename, if available.
    baseline = None
    computed = None
    for sym in so:
        maybe_abi3 = FUNCTIONS.get(sym)
        if maybe_abi3 is None:
            maybe_abi3 = DATAS.get(sym)

        if maybe_abi3 is not None:
            if computed is None or maybe_abi3.added > computed:
                computed = maybe_abi3.added

    return AuditResult(so, baseline, computed, True)
