import pytest

from abi3audit._cli import _ensure_version

@pytest.mark.parametrize(
    "version, ok", 
    (
        ("3.3", True,),
        ("3.12", True,),
        ("3.a", False,),
        ("2.7", False,),
        ("3.1", False,),
        ("4.0", False,),
        ("5", False,),
        ("3", False,),
        ("3.7.1", False,),
    )
)
def test_ensure_version(version, ok):
    if ok:
        version_ints = _ensure_version(version)
        assert isinstance(version_ints, tuple)
        assert isinstance(version_ints[0], int)
        assert isinstance(version_ints[1], int)
        assert len(version_ints) == 2
    else:
        with pytest.raises(ValueError):
            _ensure_version(version)
