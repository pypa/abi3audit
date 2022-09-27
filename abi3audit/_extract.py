"""
Native extension extraction interfaces and implementations.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator, Optional
from zipfile import ZipFile

import requests
from packaging import utils
from packaging.tags import Tag

import abi3audit._object as _object
from abi3audit._state import status

logger = logging.getLogger(__name__)

_DISTRIBUTION_NAME_RE = r"^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$"
_SHARED_OBJECT_SUFFIXES = [".so", ".pyd"]


def _glob_all_objects(path: Path) -> Iterator[Path]:
    # NOTE: abi3 extensions are normally tagged with .abi3.SUFFIX,
    # e.g. _foo.abi3.so. Experimentally however, not all are, so we
    # don't filter on the presence of that additional tag.
    for suffix in _SHARED_OBJECT_SUFFIXES:
        yield from path.glob(f"**/*{suffix}")


class InvalidSpec(ValueError):
    """
    Raised when abi3audit doesn't know how to convert a user's auditing
    specification into something that can be extracted.
    """

    pass


class WheelSpec(str):
    def _extractor(self) -> Extractor:
        return WheelExtractor(self)


class SharedObjectSpec(str):
    def _extractor(self) -> Extractor:
        return SharedObjectExtractor(self)


class PyPISpec(str):
    def _extractor(self) -> Extractor:
        return PyPIExtractor(self)


Spec = WheelSpec | SharedObjectSpec | PyPISpec


def make_spec(val: str) -> Spec:
    if val.endswith(".whl"):
        return WheelSpec(val)
    elif any(val.endswith(suf) for suf in _SHARED_OBJECT_SUFFIXES):
        # NOTE: We allow untagged shared objects when they're indirectly
        # audited (e.g. via an abi3 wheel), but not directly (since
        # without a tag here we don't know if it's abi3 at all).
        if ".abi3." not in val:
            raise InvalidSpec(f"'{val}' looks like a shared object but is not tagged as abi3")
        return SharedObjectSpec(val)
    elif re.match(_DISTRIBUTION_NAME_RE, val, re.IGNORECASE):
        return PyPISpec(val)
    else:
        raise InvalidSpec(f"'{val}' does not look like a valid spec")


class ExtractorError(ValueError):
    """
    Raised when abi3audit doesn't know how to (or can't) extract shared objects
    from the requested source.
    """

    pass


class WheelExtractor:
    def __init__(self, spec: WheelSpec, parent: Optional[PyPIExtractor] = None) -> None:
        self.spec = spec
        self.path = Path(self.spec)
        self.parent = parent

        if not self.path.is_file():
            raise ExtractorError(f"not a file: {self.path}")

    # TODO: Do this during initialization instead, so that we can turn
    # more things into early errors (like the wheel not being abi3-tagged).
    @property
    def tagset(self) -> frozenset[Tag]:
        return utils.parse_wheel_filename(self.path.name)[-1]

    def __iter__(self) -> Iterator[_object.SharedObject]:
        status.update(f"{self}: collecting shared objects")
        with TemporaryDirectory() as td, ZipFile(self.path, "r") as zf:
            exploded_path = Path(td)
            zf.extractall(exploded_path)

            for so_path in _glob_all_objects(exploded_path):
                child = SharedObjectExtractor(SharedObjectSpec(so_path), parent=self)
                yield from child

    def __str__(self) -> str:
        return self.path.name


class SharedObjectExtractor:
    def __init__(self, spec: SharedObjectSpec, parent: Optional[WheelExtractor] = None) -> None:
        self.spec = spec
        self.path = Path(self.spec)
        self.parent = parent

        if not self.path.is_file():
            raise ExtractorError(f"not a file: {self.path}")

    def _elf_magic(self) -> bool:
        with self.path.open("rb") as io:
            magic = io.read(4)
            return magic == b"\x7FELF"

    def __iter__(self) -> Iterator[_object.SharedObject]:
        match self.path.suffix:
            case ".so":
                # Python uses .so for extensions on macOS as well, rather
                # than the normal .dylib extension. As a result, we have to
                # suss out the underlying format from the wheel's tags,
                # or from the magic bytes as a last result.
                if (
                    self.parent
                    and any("macosx" in t.platform for t in self.parent.tagset)
                    or not self._elf_magic()
                ):
                    yield _object._Dylib(self)
                else:
                    yield _object._So(self)
            case ".pyd":
                yield _object._Dll(self)

    def __str__(self) -> str:
        return self.path.name


class PyPIExtractor:
    def __init__(self, spec: PyPISpec) -> None:
        self.spec = spec
        self.parent = None

    def __iter__(self) -> Iterator[_object.SharedObject]:
        status.update(f"{self}: querying PyPI")

        # TODO: Error handling for this request.
        resp = requests.get(
            f"https://pypi.org/pypi/{self.spec}/json", headers={"Accept-Encoding": "gzip"}
        )
        body = resp.json()

        status.update(f"{self}: collecting distributions from PyPI")
        for dists in body["releases"].values():
            for dist in dists:
                # If it's not a wheel, we can't audit it.
                if not dist["filename"].endswith(".whl"):
                    continue

                # If it's not an abi3 wheel, we don't have anything interesting
                # to say about it.
                # TODO: Maybe include non-abi3 wheels so that we can detect
                # wheels that can be safely marked as abi3?
                tagset = utils.parse_wheel_filename(dist["filename"])[-1]
                if not any(t.abi == "abi3" for t in tagset):
                    logger.debug(f"skipping non-abi3 wheel: {dist['filename']}")
                    continue

                status.update(f"{self}: {dist['filename']}: retrieving wheel")
                resp = requests.get(dist["url"])
                with TemporaryDirectory() as td:
                    wheel_path = Path(td) / dist["filename"]
                    wheel_path.write_bytes(resp.content)

                    child = WheelExtractor(WheelSpec(wheel_path), parent=self)
                    yield from child

    def __str__(self) -> str:
        return self.spec


Extractor = WheelExtractor | SharedObjectExtractor | PyPIExtractor
