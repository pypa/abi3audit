import pytest

from abi3audit._extract import (
    ExtractorError,
    InvalidSpec,
    PyPISpec,
    SharedObjectSpec,
    WheelExtractor,
    WheelSpec,
    make_spec,
)


def test_make_spec():
    assert make_spec("foo.whl") == WheelSpec("foo.whl")
    assert make_spec("foo.abi3.so") == SharedObjectSpec("foo.abi3.so")
    assert make_spec("foo") == PyPISpec("foo")

    # Shared objects need to be tagged with `.abi3`.
    with pytest.raises(InvalidSpec):
        make_spec("foo.so")

    # Anything that doesn't look like a wheel, shared object, or PyPI package fails.
    with pytest.raises(InvalidSpec):
        make_spec("foo@foo")


class TestWheelExtractor:
    def test_init(self):
        with pytest.raises(ExtractorError):
            WheelExtractor(WheelSpec("not-a-real-file"))
