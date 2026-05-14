# python/tests/conftest.py
import os
import pytest
from pathlib import Path

TESTS_DIR  = Path(__file__).parent          # python/tests/
PYTHON_DIR = TESTS_DIR.parent               # python/
DATA_DIR   = TESTS_DIR / "data"
GOOD_DIR   = DATA_DIR / "good"
BAD_DIR    = DATA_DIR / "bad"

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
