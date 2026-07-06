# python/tests/conftest.py
from __future__ import annotations
import os
import pytest
from pathlib import Path
import ctypes
import platform
import subprocess
import inspect

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "hardware: marks tests that require physical hardware (loopback serial port)"
    )
    config.addinivalue_line(
        "markers",
        "hardware_perf: marks tests that need loopback and are used for performance eval"
    )

TESTS_DIR  = Path(__file__).parent          # python/tests/
PYTHON_DIR = TESTS_DIR.parent               # python/
DATA_DIR   = TESTS_DIR / "data"
GOOD_DIR   = DATA_DIR / "good"
BAD_DIR    = DATA_DIR / "bad"
TMP_DIR = DATA_DIR / "tmp"

@pytest.fixture(autouse=True)
def set_working_dir():
    original = os.getcwd()
    os.chdir(PYTHON_DIR)
    yield
    os.chdir(original)

@pytest.fixture
def good_dir():
    return Path("tests/data/good")

@pytest.fixture
def bad_dir():
    return Path("tests/data/bad")

@pytest.fixture
def tmp_dir():
    """Predictable temp directory for test files; excluded from git."""
    TMP_DIR.mkdir(exist_ok=True)
    return TMP_DIR


# ---------------------------------------------------------------------------
# General C library infrastructure
# ---------------------------------------------------------------------------

@pytest.fixture
def c_object_pool():
    """
    A dict, fresh per test, for keeping ctypes callback trampolines
    (and any other C-side objects, e.g. CPacket instances) alive for
    the duration of the test. Keyed by C address; the value is
    whatever Python object needs to stay referenced. See
    register_callback() for the companion helper that builds and
    registers a callback trampoline into a pool like this one.
    """
    return {}


def register_callback(shape, function, pool=None):
    """
    Helper for mapping Python functions that will be used as callbacks
    from C.  In the C API wrapper for a module, define the shape of any
    callback functions that are needed, for example:

    FOO_FUNC = ctypes.CFUNCTYPE(ctypes.c_uint16, ctypes.c_uint8)

    This means that FOO_FUNC "returns uint16, accepts uint8"

    Define your python function to match:

    def my_foo(x: int ) -> int:

    Then

    cb = register_callback(FOO_FUNC, my_foo, pool=c_object_pool)

    'cb' can be passed to functions that expect a FOO_FUNC callback.

    If 'function' is None, returns an object that will be resolved
    to a NULL pointer.  Useful for C code that has optional callbacks.

    'pool' registers the callback object in a pool (dict), which ensures
    that it will not be garbage collected until the pool is destroyed.
    """
    if function is None:
        return ctypes.cast(None, shape)
    expected = len(shape._argtypes_)
    actual = len(inspect.signature(function).parameters)
    if actual != expected:
        raise TypeError(f"callback must take {expected} argument(s), got {actual}")
    cb = shape(function)
    if pool is not None:
        address = ctypes.cast(cb, ctypes.c_void_p).value
        pool[address] = cb
    return cb


# ---------------------------------------------------------------------------
# Bundle C library infrastructure
# ---------------------------------------------------------------------------

BUNDLE_BUILD_DIR = TMP_DIR / "bundle"

def _bundle_dll_path() -> Path:
    system = platform.system()
    if system == "Windows":
        name = "bundle.dll"
    elif system == "Darwin":
        name = "bundle.dylib"
    else:
        name = "bundle.so"
    return TMP_DIR / name

@pytest.fixture(scope="session")
def bundle_dll():
    """Configures, builds, and loads the Bundle C shared library."""
    subprocess.run(
        ["cmake", "-S", str(TESTS_DIR), "-B", str(BUNDLE_BUILD_DIR), "-G", "Ninja"],
        check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    subprocess.run(
        ["cmake", "--build", str(BUNDLE_BUILD_DIR)],
        check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    return ctypes.CDLL(str(_bundle_dll_path()))

@pytest.fixture(scope="session")
def bundle_api(bundle_dll):
    from bundle_capi import BundleCAPI
    return BundleCAPI(bundle_dll)


# ---------------------------------------------------------------------------
# Hardware test infrastructure
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption('--loopback-port',
                     help='Serial port with loopback jumper for hardware tests')
    parser.addoption('--loopback-baud', default='115200',
                     help='Baud rate for loopback tests')


@pytest.fixture
def loopback_port(request):
    port = request.config.getoption('--loopback-port')
    if port is None:
        pytest.skip('no loopback port specified (use --loopback-port=COMx)')
    return port


@pytest.fixture
def loopback_baud(request):
    return int(request.config.getoption('--loopback-baud'))
