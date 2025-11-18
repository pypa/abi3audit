from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest
from abi3info.models import Function, PyVersion, Symbol

from abi3audit._audit import audit


@dataclass(frozen=True, unsafe_hash=True)
class SharedObject:
    symbols: Iterator[Symbol]
    baseline: PyVersion
    computed: PyVersion
    future_abi3_objects: Iterator[Function] = field(default_factory=list)
    non_abi3_symbols: Iterator[Symbol] = field(default_factory=list)

    def abi3_version(self, assume_lowest) -> PyVersion:
        return self.baseline

    def __iter__(self) -> Iterator[Symbol]:
        yield from self.symbols


shared_objects = [
    SharedObject(
        baseline=PyVersion(3, 10),
        computed=PyVersion(3, 10),
        symbols=[
            Symbol("PyType_GetModule", "global"),
            Symbol("Py_TYPE", "local"),
            Symbol("Py_REFCNT", "local"),
            Symbol("Py_XDECREF", "local"),
        ],
    ),
    SharedObject(
        baseline=PyVersion(3, 9),
        computed=PyVersion(3, 10),
        symbols=[
            Symbol("PyType_GetModule", "global"),
            Symbol("Py_TYPE", "local"),
            Symbol("Py_REFCNT", "local"),
            Symbol("Py_XDECREF", "local"),
        ],
        future_abi3_objects=[
            Function(
                Symbol("PyType_GetModule", None), PyVersion(3, 10), ifdef=None, abi_only=False
            ),
        ],
    ),
    SharedObject(
        baseline=PyVersion(3, 9),
        computed=PyVersion(3, 14),
        symbols=[
            Symbol("PyType_GetModule", "global"),
            Symbol("Py_TYPE", "global"),
            Symbol("Py_REFCNT", "local"),
            Symbol("Py_XDECREF", "local"),
        ],
        future_abi3_objects=[
            Function(
                Symbol("PyType_GetModule", None), PyVersion(3, 10), ifdef=None, abi_only=False
            ),
            Function(Symbol("Py_TYPE", None), PyVersion(3, 14), ifdef=None, abi_only=False),
        ],
    ),
    SharedObject(
        baseline=PyVersion(3, 9),
        computed=PyVersion(3, 10),
        symbols=[
            Symbol("PyType_GetModule", "global"),
            Symbol("Py_TYPE", "local"),
            Symbol("Py_foo_bar", "global"),
        ],
        future_abi3_objects=[
            Function(
                Symbol("PyType_GetModule", None), PyVersion(3, 10), ifdef=None, abi_only=False
            ),
        ],
        non_abi3_symbols=[
            Symbol("Py_foo_bar", None),
        ],
    ),
]


@pytest.mark.parametrize("so", shared_objects)
def test_audit_result_unit_test(so):
    result = audit(so, so.baseline)
    assert result.baseline == so.baseline
    assert result.computed == so.computed
    assert result.future_abi3_objects == set(so.future_abi3_objects)
    assert result.non_abi3_symbols == set(so.non_abi3_symbols)
