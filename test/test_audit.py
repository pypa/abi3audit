from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

import pytest
import requests

from abi3audit._audit import audit
from abi3audit._extract import make_specs

logger = logging.getLogger("abi3audit-tests")


WHEELHOUSE = Path(__file__).parent / "wheelhouse"
WHEELHOUSE.mkdir(exist_ok=True)


_PACKAGE = "cryptography"
_VERSION = "42.0.7"
_PY = ("cp37", "cp39")
_PLATFORMS = (
    "macosx_10_12_universal2",
    "manylinux_2_17_aarch64.manylinux2014_aarch64",
    "manylinux_2_17_x86_64.manylinux2014_x86_64",
    "manylinux_2_28_aarch64",
    "manylinux_2_28_x86_64",
    "musllinux_1_1_aarch64",
    "musllinux_1_1_x86_64",
    "musllinux_1_2_aarch64",
    "musllinux_1_2_x86_64",
    "win32",
    "win_amd64",
)


@dataclass(frozen=True, unsafe_hash=True)
class Wheel:
    package: str
    version: str
    python: str
    platform: str

    def download(self, url: str, integrity: str, dest: Path = WHEELHOUSE) -> Path:
        wheel = dest / self.tag()
        if wheel.exists():
            logger.debug(f"serving wheel {self.tag()} directly from local path {dest}")
            return wheel

        logger.debug(f"downloading wheel {self.tag()} from URL {url} into {dest}.")
        resp = requests.get(url, stream=True)
        resp.raise_for_status()
        h = hashlib.sha256()
        with open(wheel, "wb") as wfd:
            for chunk in resp.iter_content(chunk_size=16 * 1024):
                h.update(chunk)
                wfd.write(chunk)

        hashval = h.hexdigest()
        if hashval != integrity:
            wheel.unlink()
            raise RuntimeError(
                f"SHA-256 hash value mismatch: expected hash {integrity}, got {hashval}"
            )
        return wheel

    def tag(self) -> str:
        return f"{self.package}-{self.version}-{self.python}-abi3-{self.platform}.whl"

    def __str__(self):
        return self.tag()


class WheelLinkParser(HTMLParser):
    def __init__(self, wheels: Iterable[Wheel]):
        super().__init__()
        self.wheels = {w.tag(): w for w in wheels}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str]]):
        if tag != "a" or not attrs:
            return
        # href attribute is always first on PyPI simple anchor tags.
        _, url = attrs[0]
        wheel_and_sha = url.rsplit("/", 1)[1]
        # URLs have the format /$WHEELTAG#sha256=$SHASUM.
        wheeltag, integrity = wheel_and_sha.split("#", 1)
        # split off the leading "sha256=".
        integrity = integrity[7:]

        if wheeltag in self.wheels:
            self.wheels[wheeltag].download(url=url, integrity=integrity)


@pytest.mark.parametrize(
    "wheel",
    [Wheel(_PACKAGE, _VERSION, py, platform) for py in _PY for platform in _PLATFORMS],
    ids=str,
)
def test_audit_results_on_golden_wheels(wheel):
    wheel_downloader = WheelLinkParser([wheel])
    simple_cryptography_pypi_page = requests.get(f"https://pypi.org/simple/{_PACKAGE}/")
    simple_cryptography_pypi_page.raise_for_status()
    # downloads the wheels when finding the appropriate URLs in the HTML doc.
    wheel_downloader.feed(simple_cryptography_pypi_page.content.decode())

    spec = make_specs(str(WHEELHOUSE / wheel.tag()))[0]
    for so in spec._extractor():
        # a trimmed version of the loop in abi3audit._cli.main().
        result = audit(so)
        assert bool(result), f"got non-abi3 symbols {result.non_abi3_symbols}"
