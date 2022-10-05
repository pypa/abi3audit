"""
Models and logic for handling different types of shared objects.
"""

from __future__ import annotations

import logging
import struct
from typing import Iterator, Optional

import pefile
from abi3info.models import PyVersion, Symbol
from elftools.elf.elffile import ELFFile

import abi3audit._extract as extract
from abi3audit._vendor import mach_o

logger = logging.getLogger(__name__)


class SharedObjectError(Exception):
    pass


class _SharedObjectBase:
    """
    A mixin for common behavior between all types of shared objects.
    """

    def __init__(self, extractor: extract.SharedObjectExtractor):
        self._extractor = extractor
        self.path = self._extractor.path

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
            logger.warning("no wheel to infer abi3 version from; assuming the lowest (3.2)")
            return PyVersion(3, 2)

        # With no wheel tags and no filename tag, we have nothing to go on.
        return None

    def __str__(self) -> str:
        parents = []
        current = self._extractor.parent
        while current is not None:
            parents.append(str(current))
            current = current.parent  # type: ignore[assignment]
        return f"{': '.join(reversed(parents))}: {self._extractor}"


class _So(_SharedObjectBase):
    """
    An ELF-formatted shared object.
    """

    def __iter__(self) -> Iterator[Symbol]:
        with self._extractor.path.open(mode="rb") as io, ELFFile(io) as elf:
            symtab = elf.get_section_by_name(".symtab")
            if symtab is not None:
                for sym in symtab.iter_symbols():
                    yield Symbol(sym.name)

            # NOTE: Experimentally, some versions of pyO3 create
            # extensions with the symbols in .dynsym instead of .symtab.
            dynsym = elf.get_section_by_name(".dynsym")
            if dynsym is not None:
                for sym in dynsym.iter_symbols():
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
        except Exception:
            logger.debug(f"mach-o decode for {self._extractor.path} failed; trying as a fat mach-o")
            # To handle "fat" Mach-Os, we do some ad-hoc parsing below:
            # * Check that we're really in a fat Mach-O and, if
            #   we are, figure out whether it's a 32-bit or 64-bit style one;
            # * Figure out how many architecture slices (nfat_arch) there are;
            # * Loop over each, grabbing the inner Mach-O's file offset and size;
            # * Passing the raw data at that offset to the "thin" Mach-O parser
            macho_slices = []
            with self._extractor.path.open("rb") as io:
                (magic,) = struct.unpack(">I", io.read(4))
                if magic == 0xCAFEBABE:
                    fieldspec = (">I", 4)
                elif magic == 0xCAFEBABF:
                    fieldspec = (">Q", 8)
                else:
                    # NOTE: There are technically two other magics for little-endian
                    # Mach-O Fat headers, but they never appear in the wild.
                    raise SharedObjectError(
                        f"bad magic: {hex(magic)} (not FAT_MAGIC or FAT_MAGIC_64)"
                    )

                (nfat_arch,) = struct.unpack(fieldspec[0], io.read(fieldspec[1]))
                for _ in range(nfat_arch):
                    # Move past cputype and cpusubtype (both uint32)
                    _ = io.read(8)
                    (mach_offset,) = struct.unpack(fieldspec[0], io.read(fieldspec[1]))
                    (mach_size,) = struct.unpack(fieldspec[0], io.read(fieldspec[1]))
                    macho_slices.append((mach_offset, mach_size))
                    # Move past align (uint32) and, if it's 64-bit, reserved (uint32) as well
                    _ = io.read(4)
                    if fieldspec[1] == 8:
                        _ = io.read(4)

                # Finally, parse each Mach-O.
                logger.debug(f"fat macho: identified {nfat_arch} mach-o slices: {macho_slices}")
                for (offset, size) in macho_slices:
                    io.seek(offset)
                    raw_macho = io.read(size)

                    with mach_o.MachO.from_bytes(raw_macho) as macho:
                        yield macho

    def __iter__(self) -> Iterator[Symbol]:
        for macho in self._each_macho():
            symtab_cmd = next(
                (
                    lc.body
                    for lc in macho.load_commands
                    if lc.type == mach_o.MachO.LoadCommandType.symtab
                ),
                None,
            )
            if symtab_cmd is None:
                raise SharedObjectError("shared object has no symbol table")

            for symbol in symtab_cmd.symbols:
                # TODO(ww): Do a better job of filtering here.
                # The Mach-O symbol table includes all kinds of junk, including
                # symbolic entries for debuggers. We should exclude all of
                # these non-function/data entries, as well as any symbols
                # that isn't marked as external (since we're linking against
                # the Python interpreter for the ABI).
                if (name := symbol.name) is None:
                    continue

                # All symbols on macOS are prefixed with _; remove it.
                yield Symbol(name[1:])


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
                    if imp.name is None:
                        logger.debug(f"weird: skipping import data entry without name: {imp}")
                        continue
                    yield Symbol(imp.name.decode())


SharedObject = _So | _Dll | _Dylib
