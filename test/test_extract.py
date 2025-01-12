import pytest
from abi3info.models import PyVersion

from abi3audit._extract import (
    ExtractorError,
    InvalidSpec,
    PyPISpec,
    SharedObjectSpec,
    WheelExtractor,
    WheelSpec,
    make_specs,
)


def test_make_spec():
    assert make_specs("foo.whl") == [WheelSpec("foo.whl")]
    assert make_specs("foo.abi3.so") == [SharedObjectSpec("foo.abi3.so")]
    assert make_specs("foo") == [PyPISpec("foo")]

    # Shared objects need to be tagged with `.abi3` or --assume-minimum-abi3
    # must be used.
    with pytest.raises(InvalidSpec, match="--assume-minimum-abi3"):
        make_specs("foo.so")

    make_specs("foo.so", assume_minimum_abi3=PyVersion(3, 2)) == [SharedObjectSpec("foo.so")]

    # Anything that doesn't look like a wheel, shared object, or PyPI package fails.
    with pytest.raises(InvalidSpec):
        make_specs("foo?")


class TestWheelExtractor:
    def test_init(self):
        with pytest.raises(ExtractorError):
            WheelExtractor(WheelSpec("not-a-real-file"))
