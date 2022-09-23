import pytest

from abi3audit._extract import InvalidSpec, Spec, WheelExtractor


class TestWheelExtractor:
    def test_init(self):
        with pytest.raises(InvalidSpec):
            WheelExtractor(Spec("not-a-real-file"))
