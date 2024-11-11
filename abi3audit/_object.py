"""
Models and logic for handling different types of shared objects.
"""

from __future__ import annotations

import logging
import struct
from collections.abc import Iterator
from typing import Any, Union

import pefile
from abi3info.models import PyVersion, Symbol, Visibility
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

    def abi3_version(self, assume_lowest: PyVersion) -> PyVersion | None:
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
            if assume_lowest is None:
                assume_lowest = PyVersion(3, 2)

            logger.debug(
                "no wheel to infer abi3 version from; assuming (%s)",
                assume_lowest,
            )
            return assume_lowest

        # With no wheel tags and no filename tag, fall back on the assumed ABI
        # version (which is possibly None).
        return assume_lowest

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

    def __init__(self, extractor: extract.SharedObjectExtractor):
        super().__init__(extractor)

        with self._extractor.path.open(mode="rb") as io, ELFFile(io) as elf:
            # HACK: If the ELF contains a comment section, look for an indicator
            # that the binary was produced by GCC. If so, we treat STB_LOOS
            # as STB_GNU_UNIQUE, i.e. another kind of local symbol linkage.
            comment = elf.get_section_by_name(".comment")
            if comment is None:
                logger.debug(f"{self._extractor.path} has no .comment")
                self._loos_is_gnu_unique = False
            else:
                self._loos_is_gnu_unique = b"GCC" in comment.data()
                logger.debug(f"{self._extractor.path} has .comment, {self._loos_is_gnu_unique=}")

    def __iter__(self) -> Iterator[Symbol]:
        def get_visibility(_sym: Any) -> Visibility | None:
            elfviz: str = _sym.entry.st_info.bind
            if elfviz == "STB_LOCAL":
                return "local"
            elif elfviz == "STB_LOOS" and self._loos_is_gnu_unique:
                return "local"
            elif elfviz == "STB_GLOBAL":
                return "global"
            elif elfviz == "STB_WEAK":
                return "weak"
            else:
                logger.warning(f"unexpected ELF visibility value {elfviz!r}")
                return None

        with self._extractor.path.open(mode="rb") as io, ELFFile(io) as elf:
            # The dynamic linker on Linux uses .dynsym, not .symtab, for
            # link editing and relocation. However, an extension that was
            # compiled as non-abi3 might have CPython functions inlined into
            # it, and we'd like to detect those. As such, we scan both symbol
            # tables.
            symtab = elf.get_section_by_name(".symtab")
            if symtab is not None:
                for sym in symtab.iter_symbols():
                    yield Symbol(sym.name, visibility=get_visibility(sym))

            dynsym = elf.get_section_by_name(".dynsym")
            if dynsym is not None:
                for sym in dynsym.iter_symbols():
                    yield Symbol(sym.name, visibility=get_visibility(sym))


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
                for offset, size in macho_slices:
                    io.seek(offset)
                    raw_macho = io.read(size)

                    with mach_o.MachO.from_bytes(raw_macho) as macho:
                        yield macho

    def __iter__(self) -> Iterator[Symbol]:
        def get_visibility(_macho_sym: Any) -> Visibility:
            # N_TYPE is the bitmask giving the Mach-O symbol type.
            # Possible values are:
            # 0x0 - symbol undefined, missing section field.
            # 0x2 - symbol absolute, missing section field.
            # 0xe - symbol defined in section type given by _macho_sym.sect
            # 0xc - symbol undefined w/ prebound value, missing section field.
            # 0xa - symbol is the same as the one found in table at index _macho_sym.value.
            # (See https://github.com/aidansteele/osx-abi-macho-file-format-reference/blob/master/README.md#nlist_64)
            # We assume that if the N_TYPE is 0xe, the linkage is internal,
            # and that everything else comes from a shared library.
            N_TYPE = 0xE
            if _macho_sym.type & N_TYPE == N_TYPE:
                return "local"
            return "global"

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

            N_EXT = 0x01
            for symbol in symtab_cmd.symbols:
                # The Mach-O symbol table includes all kinds of junk, including
                # symbolic entries for debuggers. We exclude all of
                # these non-function/data entries, as well as any symbols
                # that are not marked as external (since we're linking against
                # the Python interpreter for the ABI).
                # A symbol is marked as external if the N_EXT (rightmost) bit
                # of its `type` attribute is set.
                if (name := symbol.name) is None or (symbol.type & N_EXT != N_EXT):
                    continue

                # All symbols on macOS are prefixed with _; remove it.
                yield Symbol(name[1:], visibility=get_visibility(symbol))


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
                    # On Windows, all present symbols are also global -
                    # that is, __declspec(dllexport) is equal to -fvisibility=hidden
                    # plus __attribute__((visibility(default))).
                    yield Symbol(imp.name.decode(), visibility="global")


SharedObject = Union[_So, _Dll, _Dylib]
