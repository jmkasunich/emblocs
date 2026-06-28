# python/tests/conftest.py
from __future__ import annotations
import os
import pytest
from pathlib import Path

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
