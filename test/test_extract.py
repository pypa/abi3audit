import pytest

from abi3audit._extract import ExtractorError, WheelExtractor, WheelSpec


class TestWheelExtractor:
    def test_init(self):
        with pytest.raises(ExtractorError):
            WheelExtractor(WheelSpec("not-a-real-file"))
