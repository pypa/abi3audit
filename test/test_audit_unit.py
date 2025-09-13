import pytest
from typing import Iterator
from dataclasses import dataclass, field
from abi3info.models import PyVersion, Symbol, Visibility, Function

from abi3audit._audit import audit

@dataclass(frozen=True, unsafe_hash=True)
class SharedObject:
    assume: PyVersion
    computed: PyVersion
    symbols: Iterator[Symbol]
    future_abi3_objects: Iterator[Function] = field(default_factory=list)
    non_abi3_symbols: Iterator[Symbol] = field(default_factory=list)

    def abi3_version(self, assume_lowest) -> PyVersion:
        return self.assume

    def __iter__(self) -> Iterator[Symbol]:
        for symbol in self.symbols:
            yield symbol

shared_objects = [
  SharedObject(
    assume = PyVersion(3, 10),
    computed = PyVersion(3, 10),
    symbols = [
      Symbol("PyType_GetModule", "global"),
      Symbol("Py_TYPE", "local"),
      Symbol("Py_REFCNT", "local"),
      Symbol("Py_XDECREF", "local"),
    ],
  ),
  SharedObject(
    assume = PyVersion(3, 9),
    computed = PyVersion(3, 10),
    symbols = [
      Symbol("PyType_GetModule", "global"),
      Symbol("Py_TYPE", "local"),
      Symbol("Py_REFCNT", "local"),
      Symbol("Py_XDECREF", "local"),
    ],
    future_abi3_objects = [
      Function(Symbol("PyType_GetModule", None), PyVersion(3, 10), ifdef=None, abi_only=False),
    ],
  ),
  SharedObject(
    assume = PyVersion(3, 9),
    computed = PyVersion(3, 14),
    symbols = [
      Symbol("PyType_GetModule", "global"),
      Symbol("Py_TYPE", "global"),
      Symbol("Py_REFCNT", "local"),
    ],
    future_abi3_objects = [
      Function(Symbol("PyType_GetModule", None), PyVersion(3, 10), ifdef=None, abi_only=False),
      Function(Symbol("Py_TYPE", None), PyVersion(3, 14), ifdef=None, abi_only=False),
    ],
  ),
  SharedObject(
    assume = PyVersion(3, 9),
    computed = PyVersion(3, 10),
    symbols = [
      Symbol("PyType_GetModule", "global"),
      Symbol("Py_TYPE", "local"),
      Symbol("Py_foo_bar", "global"),
    ],
    future_abi3_objects = [
      Function(Symbol("PyType_GetModule", None), PyVersion(3, 10), ifdef=None, abi_only=False),
    ],
    non_abi3_symbols = [
      Symbol("Py_foo_bar", None),
    ],
  ),
]

@pytest.mark.parametrize(
    "so", shared_objects
)
def test_audit_result_unit_test(so):
    result = audit(so, so.assume)
    assert result.computed == so.computed
    assert list(result.future_abi3_objects) == so.future_abi3_objects
    assert list(result.non_abi3_symbols) == so.non_abi3_symbols
