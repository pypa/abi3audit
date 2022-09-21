"""
Models and logic for handling different types of shared objects.
"""

from __future__ import annotations

from typing import Iterator, Optional

from abi3info.models import PyVersion, Symbol
from elftools.elf.elffile import ELFFile
from packaging import utils

import abi3audit._extract as extract


class _SharedObjectBase:
    """
    A mixin for common behavior between all types of shared objects.
    """

    def __init__(self, extractor: extract.SharedObjectExtractor):
        self._extractor = extractor

    def abi3_version(self) -> Optional[PyVersion]:
        # If we're dealing with a shared object that was extracted from a wheel,
        # we try and suss out the abi3 version from the wheel's own tags.
        if self._extractor.parent is not None:
            # Wheels can have "compressed tag sets", leaving us to search through
            # each Tags instance and figure out if it's an abi3 wheel or not.
            tagset = utils.parse_wheel_filename(self._extractor.parent.path.name)[-1]

            # Multiple tagsets can be marked as abi3. Normally this means that they all
            # also share the same CPython version, although I'm not sure if that's actually
            # formally guaranteed.
            # Just to be on the safe side, we collect all of them and select the one with
            # the lowest CPython interpreter version.
            pyversions = [
                PyVersion.parse_python_tag(t.interpreter) for t in tagset if t.abi == "abi3"
            ]
            if len(pyversions) > 0:
                return min(pyversions)

        # If we're dealing with a standalone shared object (or the above fell through),
        # we fall back on checking for the ".abi3" marker in the shared object's own
        # filename. This doesn't tell us anything about the specific abi3 version, so
        # we assume the lowest.
        if ".abi3" in self._extractor.path.suffixes:
            return PyVersion(3, 2)

        # With no wheel tags and no filename tag, we have nothing to go on.
        return None

    def __str__(self) -> str:
        if self._extractor.parent is None:
            return self._extractor.path.name
        else:
            return f"{self._extractor.path.name} ({self._extractor.parent.path.name})"


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
