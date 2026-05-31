# python/tests/conftest.py
from __future__ import annotations
import os
import pytest
from pathlib import Path

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
