import pytest
from abi3info.models import PyVersion

from abi3audit._cli import _PyVersionAction
from abi3audit._extract import SharedObjectExtractor, SharedObjectSpec, WheelExtractor, WheelSpec
from abi3audit._object import _SharedObjectBase


@pytest.mark.parametrize(
    "version, ok",
    (
        ("3.3", True),
        ("3.12", True),
        ("3.a", False),
        ("2.7", False),
        ("3.1", False),
        ("4.0", False),
        ("5", False),
        ("3", False),
        ("3.7.1", False),
    ),
)
def test_ensure_version(version, ok):
    if ok:
        pyversion = _PyVersionAction._ensure_pyversion(version)
        assert pyversion.major == 3
        assert pyversion.minor >= 2
    else:
        with pytest.raises(ValueError):
            _PyVersionAction._ensure_pyversion(version)


@pytest.mark.parametrize(
    "filename, assumed, baseline",
    (
        ("foo.abi3.so", None, PyVersion(3, 2)),
        ("foo.abi3t.so", None, PyVersion(3, 15)),
        ("foo.abi3t.so", PyVersion(3, 2), PyVersion(3, 15)),
        ("foo.abi3t.so", PyVersion(3, 16), PyVersion(3, 16)),
    ),
)
def test_bare_object_baseline(tmp_path, filename, assumed, baseline):
    path = tmp_path / filename
    path.touch()
    so = _SharedObjectBase(SharedObjectExtractor(SharedObjectSpec(path)))
    assert so.abi3_version(assumed) == baseline


@pytest.mark.parametrize(
    "tag, baseline",
    (
        ("cp310-abi3", PyVersion(3, 10)),
        ("cp315-abi3.abi3t", PyVersion(3, 15)),
        ("cp316-abi3t", PyVersion(3, 16)),
    ),
)
def test_wheel_baseline(tmp_path, tag, baseline):
    wheel = tmp_path / f"foo-1.0-{tag}-linux_x86_64.whl"
    wheel.touch()
    path = tmp_path / "foo.so"
    path.touch()
    parent = WheelExtractor(WheelSpec(wheel))
    so = _SharedObjectBase(SharedObjectExtractor(SharedObjectSpec(path), parent=parent))
    assert so.abi3_version(PyVersion(3, 2)) == baseline
