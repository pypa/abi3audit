"""
Native extension extraction interfaces and implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator, Optional
from zipfile import ZipFile

from abi3audit._object import SharedObject, _Dll, _Dylib, _So

_SHARED_OBJECT_SUFFIXES = [".so", ".dylib", ".pyd"]


def _glob_all_objects(path: Path) -> Iterator[Path]:
    for suffix in _SHARED_OBJECT_SUFFIXES:
        yield from path.glob(f"**/*{suffix}")


class InvalidSpec(Exception):
    """
    Raised when abi3audit doesn't know how to convert a user's auditing
    specification into something that can be extracted.
    """

    pass


@dataclass(frozen=True, eq=True, slots=True)
class Spec:
    name: str

    def extractor(self) -> Extractor:
        if self.name.endswith(".whl"):
            return WheelExtractor(self)
        elif any(self.name.endswith(suf) for suf in _SHARED_OBJECT_SUFFIXES):
            return SharedObjectExtractor(self)
        else:
            # TODO: Support for pulling from PyPI, among other things.
            raise InvalidSpec(f"invalid or unsupported input specification: {self.name}")

    def __str__(self) -> str:
        return self.name


class WheelExtractor:
    def __init__(self, spec: Spec) -> None:
        self.spec = spec
        self.path = Path(self.spec.name)

        if not self.path.is_file():
            raise InvalidSpec(f"not a file: {self.path}")

    def __iter__(self) -> Iterator[SharedObject]:
        with TemporaryDirectory() as td, ZipFile(self.path, "r") as zf:
            exploded_path = Path(td)
            zf.extractall(exploded_path)

            for so_path in _glob_all_objects(exploded_path):
                child = SharedObjectExtractor(Spec(str(so_path)), parent=self)
                yield from child


class SharedObjectExtractor:
    def __init__(self, spec: Spec, parent: Optional[WheelExtractor] = None) -> None:
        self.spec = spec
        self.path = Path(self.spec.name)
        self.parent = parent

        if not self.path.is_file():
            raise InvalidSpec(f"not a file: {self.path}")

    def __iter__(self) -> Iterator[SharedObject]:
        match self.path.suffix:
            case ".so":
                yield _So(self)
            case ".dylib":
                yield _Dylib(self)
            case ".pyd":
                yield _Dll(self)


Extractor = WheelExtractor | SharedObjectExtractor
