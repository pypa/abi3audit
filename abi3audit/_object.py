"""
Models and logic for handling different types of shared objects.
"""

from __future__ import annotations

from typing import Iterator

from abi3info.models import Symbol
from elftools.elf.elffile import ELFFile

import abi3audit._extract as extract


class _SharedObjectBase:
    """
    A mixin for common behavior between all types of shared objects.
    """

    def __init__(self, extractor: extract.SharedObjectExtractor):
        self._extractor = extractor


class _So(_SharedObjectBase):
    """
    An ELF-formatted shared object.
    """

    def __iter__(self) -> Iterator[Symbol]:
        with self._extractor.path.open(mode="rb") as io, ELFFile(io) as elf:
            symtab = elf.get_section_by_name(".symtab")
            if symtab is None:
                raise ValueError("shared object has no symbol table")
            for sym in symtab.iter_symbols():
                yield Symbol(sym.name)

    def __str__(self) -> str:
        if self._extractor.parent is None:
            return self._extractor.path.name
        else:
            return f"{self._extractor.path.name} ({self._extractor.parent.path.name})"


class _Dylib(_SharedObjectBase):
    """
    A Mach-O-formatted macOS dynamic library.
    """

    def __iter__(self) -> Iterator[Symbol]:
        yield from ()


class _Dll(_SharedObjectBase):
    """
    A PE-formatted Windows DLL.
    """

    def __iter__(self) -> Iterator[Symbol]:
        yield from ()


SharedObject = _So | _Dll | _Dylib
