"""
Core auditing logic for shared objects.
"""

from dataclasses import dataclass

from abi3audit._object import SharedObject


@dataclass(frozen=True, eq=True, slots=True)
class AuditResult:
    pass


def audit(object: SharedObject) -> AuditResult:
    pass
