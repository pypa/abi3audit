"""
Native extension extraction interfaces and implementations.
"""

from __future__ import annotations

import glob
import logging
import re
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Union
from zipfile import ZipFile

from abi3info.models import PyVersion
from packaging import utils
from packaging.tags import Tag

import abi3audit._object as _object
from abi3audit._cache import caching_session
from abi3audit._state import console, status

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
    """
    Represents a Python wheel, presumed to be present on disk.

    A wheel can contain multiple Python extensions, as shared objects.
    """

    def _extractor(self) -> Extractor:
        """
        Returns an extractor for this wheel's shared objects.
        """
        return WheelExtractor(self)


class SharedObjectSpec(str):
    """
    Represents a single shared object, presumed to be present on disk.

    A shared object may or may not be a Python extension.
    """

    def _extractor(self) -> Extractor:
        """
        Returns a "trivial" extractor for this shared object.
        """
        return SharedObjectExtractor(self)


class PyPISpec(str):
    """
    Represents a package on PyPI.

    A package may have zero or more published wheels, of which zero or more
    may be tagged as abi3 compatible.
    """

    def _extractor(self) -> Extractor:
        """
        Returns an extractor for each shared object in each published abi3 wheel.
        """
        return PyPIExtractor(self)


Spec = Union[WheelSpec, SharedObjectSpec, PyPISpec]


def make_specs(val: str, assume_minimum_abi3: PyVersion | None = None) -> list[Spec]:
    """
    Constructs a (minimally) valid list of `Spec` instances from the given input.
    """
    if val.endswith(".whl"):
        # NOTE: Windows is notable for not supporting globs in its shells.
        # If the user specifies a glob, expand it for them.
        if "*" in val:
            return [WheelSpec(s) for s in glob.glob(val)]
        return [WheelSpec(val)]
    elif any(val.endswith(suf) for suf in _SHARED_OBJECT_SUFFIXES):
        # NOTE: We allow untagged shared objects when they're indirectly
        # audited (e.g. via an abi3 wheel), but when auditing them directly we
        # only allow them if we have a minimum abi3 version to check against.
        if assume_minimum_abi3 is None and ".abi3." not in val:
            raise InvalidSpec(
                "--assume-minimum-abi3 must be used when extension "
                "does not contain '.abi3.' infix"
            )
        return [SharedObjectSpec(val)]
    elif re.match(_DISTRIBUTION_NAME_RE, val, re.IGNORECASE):
        return [PyPISpec(val)]
    else:
        raise InvalidSpec(
            f"'{val}' does not look like a valid wheel, shared object, or package name"
        )


class ExtractorError(ValueError):
    """
    Raised when abi3audit doesn't know how to (or can't) extract shared objects
    from the requested source.
    """

    pass


class WheelExtractor:
    """
    An extractor for Python wheels.

    This extractor collects and yields each shared object in the specified wheel.
    """

    def __init__(self, spec: WheelSpec, parent: PyPIExtractor | None = None) -> None:
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
    """
    An extractor for shared objects.

    This extractor is "trivial", since it yields a shared object corresponding to
    the spec it created with.
    """

    def __init__(self, spec: SharedObjectSpec, parent: WheelExtractor | None = None) -> None:
        self.spec = spec
        self.path = Path(self.spec)
        self.parent = parent

        if not self.path.is_file():
            raise ExtractorError(f"not a file: {self.path}")

    def _elf_magic(self) -> bool:
        with self.path.open("rb") as io:
            magic = io.read(4)
            return magic == b"\x7fELF"

    def __iter__(self) -> Iterator[_object.SharedObject]:
        if self.path.suffix == ".so":
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
        elif self.path.suffix == ".pyd":
            yield _object._Dll(self)

    def __str__(self) -> str:
        return self.path.name


class PyPIExtractor:
    """
    An extractor for packages published on PyPI.

    This extractor yields each shared object in each abi3-tagged wheel present
    on PyPI.
    """

    def __init__(self, spec: PyPISpec) -> None:
        self.spec = spec
        self.parent = None
        self._session = caching_session()

    def __iter__(self) -> Iterator[_object.SharedObject]:
        status.update(f"{self}: querying PyPI")

        # TODO: Error handling for this request.
        resp = self._session.get(
            f"https://pypi.org/pypi/{self.spec}/json", headers={"Accept-Encoding": "gzip"}
        )

        if not resp.ok:
            console.log(f"[red]:skull: {self}: PyPI returned {resp.status_code}")
            yield from ()
            return

        body = resp.json()

        status.update(f"{self}: collecting distributions from PyPI")
        releases = body.get("releases")
        if not releases:
            console.log(f"[red]:confused: {self}: no releases on PyPI")
            yield from ()
            return

        for dists in releases.values():
            for dist in dists:
                # If it's not a wheel, we can't audit it.
                if not dist["filename"].endswith(".whl"):
                    continue

                # If it's not an abi3 wheel, we don't have anything interesting
                # to say about it.
                # TODO: Maybe include non-abi3 wheels so that we can detect
                # wheels that can be safely marked as abi3?
                #
                # NOTE: Unfortunately, there are some wheels on PyPI that don't
                # have valid (PEP427) filenames, like:
                #
                #   pyffmpeg-2.0.5-cp35.cp36.cp37.cp38.cp39-macosx_10_14_x86_64.whl
                #
                # ...which is missing an ABI tag.
                #
                # There's not much we can do about these other than fail in
                # a controlled fashion and warn the user.
                try:
                    tagset = utils.parse_wheel_filename(dist["filename"])[-1]
                except utils.InvalidWheelFilename as exc:
                    console.log(f"[red]:skull: {self}: {exc}")
                    continue

                if not any(t.abi == "abi3" for t in tagset):
                    logger.debug(f"skipping non-abi3 wheel: {dist['filename']}")
                    continue

                status.update(f"{self}: {dist['filename']}: retrieving wheel")
                resp = self._session.get(dist["url"])
                with TemporaryDirectory() as td:
                    wheel_path = Path(td) / dist["filename"]
                    wheel_path.write_bytes(resp.content)

                    child = WheelExtractor(WheelSpec(wheel_path), parent=self)
                    yield from child

    def __str__(self) -> str:
        return self.spec


Extractor = Union[WheelExtractor, SharedObjectExtractor, PyPIExtractor]
