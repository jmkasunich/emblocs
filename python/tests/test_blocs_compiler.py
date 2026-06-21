# tests/test_blocs_compiler.py
from __future__ import annotations
import os
import time
import pytest
from pathlib import Path

import blocs_compiler
from blocs_compiler import expand_path, get_blockspec, main
from emblocs import Design
from parse_common import ctx
from conftest import TMP_DIR, PYTHON_DIR, GOOD_DIR

COMPILER_GOOD_DIR = GOOD_DIR / "compiler"
COMPILER_TMP_DIR  = TMP_DIR / "compiler"
BLOCKSPEC_TMP_DIR = TMP_DIR / "blockspec_tests"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_context():
    ctx.clear()
    ctx.push(source="<test>")
    yield
    ctx.clear()

@pytest.fixture(autouse=True)
def ensure_dirs():
    COMPILER_TMP_DIR.mkdir(parents=True, exist_ok=True)
    BLOCKSPEC_TMP_DIR.mkdir(parents=True, exist_ok=True)

@pytest.fixture
def compiler_good_timestamps():
    """Ensure .h and .c files in COMPILER_GOOD_DIR are newer than .bloc files."""
    for bloc in COMPILER_GOOD_DIR.glob("*.bloc"):
        h = bloc.with_suffix(".h")
        c = bloc.with_suffix(".c")
        if h.exists():
            h.touch()
        if c.exists():
            c.touch()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExpandPath:
    """Unit tests for blocs_compiler.expand_path()"""

    def test_relative_dot(self, monkeypatch):
        monkeypatch.setattr(blocs_compiler, 'blocs_dir', COMPILER_GOOD_DIR)
        result = expand_path(".")
        assert result == COMPILER_GOOD_DIR.resolve()

    def test_relative_subdir(self, monkeypatch):
        monkeypatch.setattr(blocs_compiler, 'blocs_dir', COMPILER_GOOD_DIR)
        result = expand_path("subdir")
        assert result == (COMPILER_GOOD_DIR / "subdir").resolve()

    def test_absolute_path(self, monkeypatch):
        monkeypatch.setattr(blocs_compiler, 'blocs_dir', COMPILER_GOOD_DIR)
        result = expand_path(COMPILER_GOOD_DIR.as_posix())
        assert result == COMPILER_GOOD_DIR.resolve()

    def test_emblocs_root(self, monkeypatch):
        monkeypatch.setattr(blocs_compiler, 'blocs_dir', COMPILER_GOOD_DIR)
        result = expand_path("$EMBLOCS/src/components")
        assert result == (blocs_compiler.EMBLOCS_ROOT / "src/components").resolve()

    def test_emblocs_no_subpath(self, monkeypatch):
        monkeypatch.setattr(blocs_compiler, 'blocs_dir', COMPILER_GOOD_DIR)
        result = expand_path("$EMBLOCS")
        assert result == blocs_compiler.EMBLOCS_ROOT.resolve()

    def test_env_var(self, monkeypatch):
        monkeypatch.setattr(blocs_compiler, 'blocs_dir', COMPILER_GOOD_DIR)
        monkeypatch.setenv('MY_BLOCKS', COMPILER_GOOD_DIR.as_posix())
        result = expand_path("$MY_BLOCKS/subdir")
        assert result == (COMPILER_GOOD_DIR / "subdir").resolve()

    def test_env_var_no_subpath(self, monkeypatch):
        monkeypatch.setattr(blocs_compiler, 'blocs_dir', COMPILER_GOOD_DIR)
        monkeypatch.setenv('MY_BLOCKS', COMPILER_GOOD_DIR.as_posix())
        result = expand_path("$MY_BLOCKS")
        assert result == COMPILER_GOOD_DIR.resolve()

    def test_env_var_unset(self, monkeypatch, capsys):
        monkeypatch.setattr(blocs_compiler, 'blocs_dir', COMPILER_GOOD_DIR)
        monkeypatch.delenv('MY_BLOCKS', raising=False)
        result = expand_path("$MY_BLOCKS/subdir")
        actual = capsys.readouterr().err.strip()
        expected = "<test>: error: environment variable $MY_BLOCKS is not set"
        assert actual == expected, f"\nEXPECT: {expected!r}\nACTUAL: {actual!r}\n"
        assert result is None

    def test_windows_backslash(self, monkeypatch):
        monkeypatch.setattr(blocs_compiler, 'blocs_dir', COMPILER_GOOD_DIR)
        result = expand_path(".\\subdir")
        assert result == (COMPILER_GOOD_DIR / "subdir").resolve()



class TestGetBlockspec:
    """Unit tests for blocs_compiler.get_blockspec()"""

    MINIMAL_BLOC = "/// test block\nfunction update\n"
    MINIMAL_H    = "// generated header\n"
    MINIMAL_C    = "// implementation\n"

    def test_happy_path(self, monkeypatch, capsys):
        d = BLOCKSPEC_TMP_DIR / "happy"
        d.mkdir(parents=True, exist_ok=True)
        (d / "testblock.bloc").write_text(self.MINIMAL_BLOC)
        time.sleep(0.01)
        (d / "testblock.h").write_text(self.MINIMAL_H)
        (d / "testblock.c").write_text(self.MINIMAL_C)
        design = Design(abs_path="test")
        design.search_paths.append(d)
        result = get_blockspec("testblock", design)
        actual = capsys.readouterr().err.strip()
        assert actual == "", f"\nEXPECT: ''\nACTUAL: {actual!r}\n"
        assert result is not None
        assert result.name == "testblock"
        assert "testblock" in design.block_specs

    def test_cache_hit(self, monkeypatch, capsys):
        d = BLOCKSPEC_TMP_DIR / "cache"
        d.mkdir(parents=True, exist_ok=True)
        (d / "testblock.bloc").write_text(self.MINIMAL_BLOC)
        time.sleep(0.01)
        (d / "testblock.h").write_text(self.MINIMAL_H)
        (d / "testblock.c").write_text(self.MINIMAL_C)
        design = Design(abs_path="test")
        design.search_paths.append(d)
        result1 = get_blockspec("testblock", design)
        capsys.readouterr()
        result2 = get_blockspec("testblock", design)
        actual = capsys.readouterr().err.strip()
        assert actual == "", f"\nEXPECT: ''\nACTUAL: {actual!r}\n"
        assert result1 is result2

    def test_not_found(self, capsys):
        design = Design(abs_path="test")
        design.search_paths.append(BLOCKSPEC_TMP_DIR)
        result = get_blockspec("no_such_block", design)
        actual = capsys.readouterr().err.strip()
        expected = (
            f"<test>:0:0: error: 'no_such_block.bloc' not found on search path\n"
            f"<test>:0:0: info: block search path is:\n"
            f"    {Path(BLOCKSPEC_TMP_DIR).as_posix()}")
        assert actual == expected, f"\nEXPECT: {expected!r}\nACTUAL: {actual!r}\n"
        assert result is None

    def test_missing_h(self, capsys):
        d = BLOCKSPEC_TMP_DIR / "missing_h"
        d.mkdir(parents=True, exist_ok=True)
        (d / "testblock.bloc").write_text(self.MINIMAL_BLOC)
        (d / "testblock.c").write_text(self.MINIMAL_C)
        design = Design(abs_path="test")
        design.search_paths.append(d)
        result = get_blockspec("testblock", design)
        actual = capsys.readouterr().err.strip()
        expected = (
            "<test>:0:0: error: block header not found: 'testblock.h';\n"
            "<test>:0:0: info: run bloc_compiler.py on testblock.bloc and/or"
            " edit testblock.c to bring block up to date")
        assert actual == expected, f"\nEXPECT: {expected!r}\nACTUAL: {actual!r}\n"
        assert result is None

    def test_missing_c(self, capsys):
        d = BLOCKSPEC_TMP_DIR / "missing_c"
        d.mkdir(parents=True, exist_ok=True)
        (d / "testblock.bloc").write_text(self.MINIMAL_BLOC)
        (d / "testblock.h").write_text(self.MINIMAL_H)
        design = Design(abs_path="test")
        design.search_paths.append(d)
        result = get_blockspec("testblock", design)
        actual = capsys.readouterr().err.strip()
        expected = (
            "<test>:0:0: error: block source not found: 'testblock.c'\n"
            "<test>:0:0: info: run bloc_compiler.py on testblock.bloc and/or"
            " edit testblock.c to bring block up to date")
        assert actual == expected, f"\nEXPECT: {expected!r}\nACTUAL: {actual!r}\n"
        assert result is None

    def test_old_h(self, capsys):
        d = BLOCKSPEC_TMP_DIR / "old_h"
        d.mkdir(parents=True, exist_ok=True)
        (d / "testblock.h").write_text(self.MINIMAL_H)
        time.sleep(0.01)
        (d / "testblock.bloc").write_text(self.MINIMAL_BLOC)
        (d / "testblock.c").write_text(self.MINIMAL_C)
        design = Design(abs_path="test")
        design.search_paths.append(d)
        result = get_blockspec("testblock", design)
        actual = capsys.readouterr().err.strip()
        expected = (
            "<test>:0:0: error: 'testblock.h' is older than 'testblock.bloc'\n"
            "<test>:0:0: info: run bloc_compiler.py on testblock.bloc and/or"
            " edit testblock.c to bring block up to date")
        assert actual == expected, f"\nEXPECT: {expected!r}\nACTUAL: {actual!r}\n"
        assert result is None

    def test_old_c(self, capsys):
        d = BLOCKSPEC_TMP_DIR / "old_c"
        d.mkdir(parents=True, exist_ok=True)
        (d / "testblock.c").write_text(self.MINIMAL_C)
        time.sleep(0.01)
        (d / "testblock.bloc").write_text(self.MINIMAL_BLOC)
        (d / "testblock.h").write_text(self.MINIMAL_H)
        design = Design(abs_path="test")
        design.search_paths.append(d)
        result = get_blockspec("testblock", design)
        actual = capsys.readouterr().err.strip()
        expected = (
            "<test>:0:0: error: 'testblock.c' is older than 'testblock.bloc'\n"
            "<test>:0:0: info: run bloc_compiler.py on testblock.bloc and/or"
            " edit testblock.c to bring block up to date")
        assert actual == expected, f"\nEXPECT: {expected!r}\nACTUAL: {actual!r}\n"
        assert result is None

    def test_empty_search_path(self, capsys):
        design = Design(abs_path="test")
        # no search paths added
        result = get_blockspec("testblock", design)
        actual = capsys.readouterr().err.strip()
        expected = (
            "<test>: error: block search path is empty;"
            " missing 'search' command(s)?")
        assert actual == expected, f"\nEXPECT: {expected!r}\nACTUAL: {actual!r}\n"
        assert result is None

class TestMain:
    """Tests for blocs_compiler.main()"""

    def test_no_args(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code == 2  # argparse exits with 2 for usage errors

    def test_missing_blocs_file(self, capsys):
        result = main([str(COMPILER_GOOD_DIR / "nonexistent.blocs"),
                      str(COMPILER_TMP_DIR)])
        actual = capsys.readouterr().err.strip()
        expected = (
            f"blocs_compiler.py: error: file not found: {Path(COMPILER_GOOD_DIR / 'nonexistent.blocs').as_posix()!r}\n"
            f"blocs_compiler.py: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expected, f"\nEXPECT: {expected!r}\nACTUAL: {actual!r}\n"
        assert result == 1

    def test_missing_build_dir(self, capsys):
        result = main([str(COMPILER_GOOD_DIR / "simple_test.blocs"),
                      str(COMPILER_TMP_DIR / "nonexistent")])
        actual = capsys.readouterr().err.strip()
        expected = (
            f"blocs_compiler.py: error: build directory not found: {Path(COMPILER_TMP_DIR / 'nonexistent').as_posix()!r}\n"
            f"blocs_compiler.py: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expected, f"\nEXPECT: {expected!r}\nACTUAL: {actual!r}\n"
        assert result == 1

    def test_happy_path(self, monkeypatch, capsys, compiler_good_timestamps):
        captured = {}

        def fake_generate_variants(design, build_dir):
            captured['design'] = design
            captured['build_dir'] = build_dir

        def fake_generate_system_files(design, build_dir):
            pass

        monkeypatch.setattr(blocs_compiler, 'generate_variants', fake_generate_variants)
        monkeypatch.setattr(blocs_compiler, 'generate_system_files', fake_generate_system_files)

        result = main([str(COMPILER_GOOD_DIR / "simple_test.blocs"),
                      str(COMPILER_TMP_DIR)])
        actual = capsys.readouterr().err.strip()
        expected = (
            "simple_test.blocs: 0 error(s), 0 warning(s), 0 info(s)\n"
            "blocs_compiler.py: 0 error(s), 0 warning(s), 0 info(s)")
        assert actual == expected, f"\nEXPECT: {expected!r}\nACTUAL: {actual!r}\n"
        assert result == 0
        assert 'design' in captured
        design = captured['design']
        assert len(design.block_defs) == 1
        assert 'simple' in design.block_defs
        assert len(design.blocks) == 1
        assert 'b1' in design.blocks
        assert len(design.search_paths) == 1
        assert design.search_paths[0] == COMPILER_GOOD_DIR.resolve()

    def test_parse_failure(self, monkeypatch, capsys):
        # .blocs file with a syntax error
        bad_blocs = COMPILER_TMP_DIR / "bad_test.blocs"
        bad_blocs.write_text("# bad test\nblockdef\n")

        def fake_generate_variants(design, build_dir):
            pass

        def fake_generate_system_files(design, build_dir):
            pass

        monkeypatch.setattr(blocs_compiler, 'generate_variants', fake_generate_variants)
        monkeypatch.setattr(blocs_compiler, 'generate_system_files', fake_generate_system_files)

        result = main([str(bad_blocs), str(COMPILER_TMP_DIR)])
        actual = capsys.readouterr().err.strip()
        expected = (
            f"bad_test.blocs:2: error: 'blockdef' requires a new def name and a source block name\n"
            f"bad_test.blocs: 1 error(s), 0 warning(s), 0 info(s)\n"
            f"blocs_compiler.py: error: parsing failed: {Path(COMPILER_TMP_DIR / "bad_test.blocs").as_posix()!r}\n"
            f"blocs_compiler.py: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expected, f"\nEXPECT: {expected!r}\nACTUAL: {actual!r}\n"
        assert result == 1

