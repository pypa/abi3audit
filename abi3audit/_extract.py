"""
Native extension extraction interfaces and implementations.
"""

from __future__ import annotations

import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator, NewType, Optional
from zipfile import ZipFile

import requests
from packaging import utils
from packaging.tags import Tag

import abi3audit._object as _object

_DISTRIBUTION_NAME_RE = r"^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$"
_SHARED_OBJECT_SUFFIXES = [".so", ".pyd"]


def _glob_all_objects(path: Path) -> Iterator[Path]:
    for suffix in _SHARED_OBJECT_SUFFIXES:
        yield from path.glob(f"**/*.abi3{suffix}")


class InvalidSpec(Exception):
    """
    Raised when abi3audit doesn't know how to convert a user's auditing
    specification into something that can be extracted.
    """

    pass


Spec = NewType("Spec", str)


def extractor(spec: Spec) -> Extractor:
    if spec.endswith(".whl"):
        return WheelExtractor(spec)
    elif any(spec.endswith(suf) for suf in _SHARED_OBJECT_SUFFIXES):
        return SharedObjectExtractor(spec)
    else:
        return PyPIExtractor(spec)


class WheelExtractor:
    def __init__(self, spec: Spec) -> None:
        self.spec = spec
        self.path = Path(self.spec)

        if not self.path.is_file():
            raise InvalidSpec(f"not a file: {self.path}")

    # TODO: Do this during initialization instead, so that we can turn
    # more things into early errors (like the wheel not being abi3-tagged).
    @property
    def tagset(self) -> frozenset[Tag]:
        return utils.parse_wheel_filename(self.path.name)[-1]

    def __iter__(self) -> Iterator[_object.SharedObject]:
        with TemporaryDirectory() as td, ZipFile(self.path, "r") as zf:
            exploded_path = Path(td)
            zf.extractall(exploded_path)

            for so_path in _glob_all_objects(exploded_path):
                child = SharedObjectExtractor(Spec(str(so_path)), parent=self)
                yield from child


class SharedObjectExtractor:
    def __init__(self, spec: Spec, parent: Optional[WheelExtractor] = None) -> None:
        self.spec = spec
        self.path = Path(self.spec)
        self.parent = parent

        if not self.path.is_file():
            raise InvalidSpec(f"not a file: {self.path}")

    def __iter__(self) -> Iterator[_object.SharedObject]:
        match self.path.suffix:
            case ".so":
                # Python uses .so for extensions on macOS as well, rather
                # than the normal .dylib extension. As a result, we have to
                # suss out the underlying format from the wheel's tags.
                if self.parent and any("macosx" in t.platform for t in self.parent.tagset):
                    yield _object._Dylib(self)
                else:
                    yield _object._So(self)
            case ".pyd":
                yield _object._Dll(self)


class PyPIExtractor:
    def __init__(self, spec: Spec) -> None:
        self.spec = spec

        if not re.match(_DISTRIBUTION_NAME_RE, str(spec), re.IGNORECASE):
            raise InvalidSpec(f"'{self.spec}' does not look like a package distribution")

    def __iter__(self) -> Iterator[_object.SharedObject]:
        resp = requests.get(
            f"https://pypi.org/pypi/{self.spec}/json", headers={"Accept-Encoding": "gzip"}
        )
        body = resp.json()

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
                    continue

                resp = requests.get(dist["url"])
                with TemporaryDirectory() as td:
                    wheel_path = Path(td) / dist["filename"]
                    wheel_path.write_bytes(resp.content)

                    child = WheelExtractor(Spec(str(wheel_path)))
                    yield from child


Extractor = WheelExtractor | SharedObjectExtractor | PyPIExtractor
