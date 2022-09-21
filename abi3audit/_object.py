"""
Models and logic for handling different types of shared objects.
"""

from __future__ import annotations

from typing import Iterator, Optional

import pefile
from abi3info.models import PyVersion, Symbol
from elftools.elf.elffile import ELFFile

import abi3audit._extract as extract
from abi3audit._vendor import mach_o


class SharedObjectError(Exception):
    pass


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
            # Multiple tagsets can be marked as abi3; when this happens,
            # we select the highest interpreter version.
            tagset = self._extractor.parent.tagset
            pyversions = [
                PyVersion.parse_python_tag(t.interpreter) for t in tagset if t.abi == "abi3"
            ]
            if len(pyversions) > 0:
                return max(pyversions)

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
                raise SharedObjectError("shared object has no symbol table")
            for sym in symtab.iter_symbols():
                yield Symbol(sym.name)


class _Dylib(_SharedObjectBase):
    """
    A Mach-O-formatted macOS dynamic library.
    """

    def _each_macho(self) -> Iterator[mach_o.MachO]:
        # This Mach-O parser doesn't currently support "fat" Mach-Os, where
        # multiple single-arch Mach-Os are embedded as slices.
        try:
            with mach_o.MachO.from_file(self._extractor.path) as macho:
                yield macho
        except:
            _ = self._extractor.path.read_bytes()
            raise SharedObjectError("unimplemented")

    def __iter__(self) -> Iterator[Symbol]:
        yield from ()
        return

        # WIP.
        for macho in self._each_macho():
            # with mach_o.MachO.from_file(self._extractor.path) as macho:
            symtab_cmd = next(
                (lc for lc in macho.load_commands if lc.type == mach_o.LoadCommandType.symtab), None
            )
            if symtab_cmd is None:
                raise SharedObjectError("shared object has no symbol table")

            for symbol in symtab_cmd.symbols:
                print(symbol.name)
                yield from ()


class _Dll(_SharedObjectBase):
    """
    A PE-formatted Windows DLL.
    """

    def __iter__(self) -> Iterator[Symbol]:
        with pefile.PE(self._extractor.path) as pe:
            pe.parse_data_directories()
            for import_data in pe.DIRECTORY_ENTRY_IMPORT:
                for imp in import_data.imports:
                    # TODO(ww): Root-cause this; imports should always be named
                    # (in my understanding of import tables in PE).
                    if imp.name is not None:
                        yield Symbol(imp.name.decode())


SharedObject = _So | _Dll | _Dylib
