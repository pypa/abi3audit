import pytest

from abi3audit._cli import _PyVersionAction

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
        pyversion = _PyVersionAction._ensure_pyversion(version)
        assert pyversion.major == 3
        assert pyversion.minor >= 2
    else:
        with pytest.raises(ValueError):
            _PyVersionAction._ensure_pyversion(version)
