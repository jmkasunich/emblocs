# tests/test_blocs_parser.py
import os
import pytest
from pathlib import Path
from parse_common import (
    Token,
     push_context, pop_context, clear_contexts, _context_stack,
     Severity,
)
from blocs_parser import (
    lex_lines,
    parse_blocs, parse_blocs_string, parse_blocs_file,
    _bloc_spec_cache,
)

from conftest import TMP_DIR, PYTHON_DIR


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_context():
    clear_contexts()
    push_context(source="<test>")
    yield
    clear_contexts()


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the bloc spec cache before each test."""
    _bloc_spec_cache.clear()
    yield
    _bloc_spec_cache.clear()


@pytest.fixture
def simple_bloc(good_dir) -> Path:
    """return path to standard test file"""
    return good_dir / "simple.bloc"

@pytest.fixture
def param_bloc(good_dir) -> Path:
    """return path to standard test file"""
    return good_dir / "parameterized.bloc"

@pytest.fixture
def test_blocs(tmp_dir) -> Path:
    """return path to standard test file"""
    return tmp_dir / "test.blocs"


def rtmp(p: Path) -> str:
    """ return path relative to tmp_dir, as a posix string. """
    return Path(os.path.relpath(p, TMP_DIR)).as_posix()

def rcwd(p: Path) -> str:
    """ return path relative to current working directory, as a posix string. """
    return Path(os.path.relpath(p, PYTHON_DIR)).as_posix()

BLOCS_SRC = Path(os.path.relpath(TMP_DIR / "test.blocs", PYTHON_DIR)).as_posix()

@pytest.fixture
def blockdefs_x3(simple_bloc, param_bloc, test_blocs):
    """ provides a design with three blockdefs for testing block commands.
        note that the command produces output to stderr, so clear the
        capture using capsys.readouterr() before starting the actual test."""
    blocs_str = (
        f"blockdef simple     {rtmp(simple_bloc)}\n"
        f"blockdef param_v1   {rtmp(param_bloc)} NCHAN=2 MASK=3 HAS_ENABLE=0\n"
        f"blockdef param_v2   {rtmp(param_bloc)} NCHAN=4 MASK=0xA HAS_ENABLE=1\n"
    )
    design = parse_blocs_string(blocs_str, source=BLOCS_SRC)
    assert design is not None
    assert len(design.block_defs) == 3
    return design



# ---------------------------------------------------------------------------
# Lexer tests
# ---------------------------------------------------------------------------

class TestLexLines:

    def test_simple_command(self):
        lines = ["blockdef foo bar.bloc\n"]
        result = lex_lines(lines)
        assert len(result) == 1
        assert len(result[0]) == 3
        assert result[0][0] == Token("blockdef", 1, 1)
        assert result[0][1] == Token("foo",      1, 10)
        assert result[0][2] == Token("bar.bloc", 1, 14)

    def test_leading_whitespace(self):
        lines = ["  blockdef foo bar.bloc\n"]
        result = lex_lines(lines)
        assert len(result) == 1
        assert len(result[0]) == 3
        assert result[0][0] == Token("blockdef", 1, 3)
        assert result[0][1] == Token("foo",      1, 12)
        assert result[0][2] == Token("bar.bloc", 1, 16)

    def test_leading_tab(self):
        lines = ["\tblockdef foo bar.bloc\n"]
        result = lex_lines(lines)
        assert len(result) == 1
        assert len(result[0]) == 3
        assert result[0][0] == Token("blockdef", 1, 2)
        assert result[0][1] == Token("foo",      1, 11)
        assert result[0][2] == Token("bar.bloc", 1, 15)

    def test_command_with_comment(self):
        lines = ["blockdef foo # comment\n"]
        result = lex_lines(lines)
        assert len(result) == 1
        assert len(result[0]) == 2
        assert result[0][0] == Token("blockdef", 1, 1)
        assert result[0][1] == Token("foo",      1, 10)

    def test_empty_string(self):
        lines = [""]
        result = lex_lines(lines)
        assert len(result) == 0

    def test_nothing_but_comment(self):
        lines = ["     # two-word comment\n", "# another comment\n"]
        result = lex_lines(lines)
        assert len(result) == 0

    def test_nothing_but_whitespace(self):
        lines = ["   \n"]
        result = lex_lines(lines)
        assert len(result) == 0

    def test_nothing_but_newline(self):
        lines = ["\n"]
        result = lex_lines(lines)
        assert len(result) == 0

    def test_command_with_continuation(self):
        lines = ["blockdef foo \\\n", "bar.bloc\n"]
        result = lex_lines(lines)
        assert len(result) == 1
        assert len(result[0]) == 3
        assert result[0][0] == Token("blockdef", 1, 1)
        assert result[0][1] == Token("foo",      1, 10)
        assert result[0][2] == Token("bar.bloc", 2, 1)

    def test_multiple_continuation(self):
        lines = ["blockdef foo \\\n", "     bar.bloc\\\n", "     baz  \n",
                 "  blockdef qux \\\n","  quux\n"]
        result = lex_lines(lines)
        assert len(result) == 2
        assert len(result[0]) == 4
        assert result[0][0] == Token("blockdef", 1, 1)
        assert result[0][1] == Token("foo",      1, 10)
        assert result[0][2] == Token("bar.bloc", 2, 6)
        assert result[0][3] == Token("baz",      3, 6)
        assert len(result[1]) == 3
        assert result[1][0] == Token("blockdef", 4, 3)
        assert result[1][1] == Token("qux",      4, 12)
        assert result[1][2] == Token("quux",     5, 3)

    def test_continuation_in_comment(self):
        lines = [" foo   # two-word comment\\\n", " bar  \\\n", "blat\n"]
        result = lex_lines(lines)
        assert len(result) == 2
        assert len(result[0]) == 1
        assert result[0][0] == Token("foo", 1, 2)
        assert len(result[1]) == 2
        assert result[1][0] == Token("bar", 2, 2)
        assert result[1][1] == Token("blat", 3, 1)

    def test_blank_continuation(self):
        lines = ["blockdef foo \\\n","   \\\n", "bar.bloc\n"]
        result = lex_lines(lines)
        assert len(result) == 1
        assert len(result[0]) == 3
        assert result[0][0] == Token("blockdef", 1, 1)
        assert result[0][1] == Token("foo",      1, 10)
        assert result[0][2] == Token("bar.bloc", 3, 1)

    def test_eof_after_continuation(self, capsys):
        lines = ["blockdef foo \\\n"]
        result = lex_lines(lines)
        actual = capsys.readouterr().err.strip()
        expected = "<test>:1: error: unexpected end of file after line continuation"
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )
        # result should be empty since the command was never completed
        assert len(result) == 0



# ---------------------------------------------------------------------------
# cmd_blockdef tests
# ---------------------------------------------------------------------------

class TestCmdBlockdef:

#    def test_basic_blockdef(self, tmp_dir, minimal_bloc):
#        blocs_str, source = make_blocs(tmp_dir, minimal_bloc)
#        design = parse_blocs_string(blocs_str, source=source)
#        assert design is not None
#        assert "myblock" in design.block_defs

    def test_basic_blockdef(self, simple_bloc, capsys):
        blocs_str = f"blockdef myblock {rtmp(simple_bloc)}\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert design is not None
        assert "myblock" in design.block_defs
        assert "in" in design.block_defs["myblock"].pins
        assert "out" in design.block_defs["myblock"].pins
        assert "update" in design.block_defs["myblock"].functions

    def test_blockdef_cached(self, simple_bloc, capsys):
        blocs_str = (f"blockdef block1  {rtmp(simple_bloc)}\n"
                     f"blockdef block2 {rtmp(simple_bloc)}\n")
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert design is not None
        assert len(_bloc_spec_cache) == 1
        assert "block1" in design.block_defs
        assert "block2" in design.block_defs

    def test_blockdef_with_params(self, param_bloc, capsys):
        blocs_str = f"blockdef myblock {rtmp(param_bloc)} NCHAN=3 MASK=7 HAS_ENABLE=1\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert design is not None
        assert design.block_defs["myblock"].params["NCHAN"] == 3
        assert design.block_defs["myblock"].params["MASK"] == 7
        assert design.block_defs["myblock"].params["HAS_ENABLE"] == 1

    def test_blockdef_two_variants_one_bloc(self, param_bloc, capsys):
        blocs_str = (f"blockdef block1 {rtmp(param_bloc)} NCHAN=3 MASK=7 HAS_ENABLE=1\n"
                     f"blockdef block2 {rtmp(param_bloc)} NCHAN=4 MASK=0xA HAS_ENABLE=0\n")
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert design is not None
        assert design.block_defs["block1"].params["NCHAN"] == 3
        assert design.block_defs["block1"].params["MASK"] == 7
        assert design.block_defs["block1"].params["HAS_ENABLE"] == 1
        assert design.block_defs["block2"].params["NCHAN"] == 4
        assert design.block_defs["block2"].params["MASK"] == 10
        assert design.block_defs["block2"].params["HAS_ENABLE"] == 0

    def test_blockdef_unknown_param_warns(self, simple_bloc, capsys):
        blocs_str = f"blockdef myblock {rtmp(simple_bloc)} UNKNOWN=3\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1:38: warning: unmatched parameter 'UNKNOWN' will be ignored\n"
            "tests/data/tmp/test.blocs: 0 error(s), 1 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert design is not None

    def test_blockdef_missing_param_uses_default_informs(self, param_bloc, capsys):
        blocs_str = f"blockdef myblock {rtmp(param_bloc)} MASK=7\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1: info: parameter 'NCHAN' not supplied, using default value 2\n"
            "tests/data/tmp/test.blocs:1: info: parameter 'HAS_ENABLE' not supplied, using default value 0\n"
            "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 2 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert design is not None
        assert design.block_defs["myblock"].params["NCHAN"] == 2
        assert design.block_defs["myblock"].params["MASK"] == 7
        assert design.block_defs["myblock"].params["HAS_ENABLE"] == 0

    def test_blockdef_too_few_tokens_fails(self, param_bloc, capsys):
        blocs_str = f"blockdef {rtmp(param_bloc)}\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1: error: 'blockdef' requires a name and a path\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert design is None

    def test_blockdef_missing_name_fails(self, param_bloc, capsys):
        blocs_str = f"blockdef {rtmp(param_bloc)} NCHAN=3 MASK=7 HAS_ENABLE=1\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1:10: error: invalid blockdef name '../good/parameterized.bloc'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert design is None

    def test_blockdef_missing_path_fails(self, param_bloc, capsys):
        blocs_str = f"blockdef myblock NCHAN=3 MASK=7 HAS_ENABLE=1\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1:18: error: bloc file not found: 'NCHAN=3'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert design is None

    def test_blockdef_invalid_name_fails(self, simple_bloc, capsys):
        blocs_str = f"blockdef 123bad {rtmp(simple_bloc)}\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1:10: error: invalid blockdef name '123bad'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert design is None

    def test_blockdef_invalid_param_name_fails(self, simple_bloc, capsys):
        blocs_str = f"blockdef myblock {rtmp(simple_bloc)} 123BAD=3\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1:38: error: invalid parameter name '123BAD'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert design is None

    def test_blockdef_file_not_found_fails(self, capsys):
        blocs_str = f"blockdef myblock not_a_file.bloc\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1:18: error: bloc file not found: 'not_a_file.bloc'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert design is None

    def test_blockdef_duplicate_name_fails(self, simple_bloc, capsys):
        blocs_str = ( f"blockdef myblock {rtmp(simple_bloc)}\n"
                      f"blockdef myblock {rtmp(simple_bloc)}\n")
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:2:10: error: name 'myblock' is already in use\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert design is None

    def test_blockdef_invalid_param_value_fails(self, param_bloc, capsys):
        blocs_str = f"blockdef myblock {rtmp(param_bloc)} NCHAN=notanumber MASK=7 HAS_ENABLE=1\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1:45: error: invalid value 'notanumber' for 'NCHAN'; expected an integer\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert design is None

    def test_blockdef_out_of_range_param_value_fails(self, param_bloc, capsys):
        blocs_str = f"blockdef myblock {rtmp(param_bloc)} NCHAN=12 MASK=7 HAS_ENABLE=1\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1: error: parameter 'NCHAN' value 12 is greater than max (4)\n"
            "tests/data/tmp/test.blocs:1: error: failed to resolve '../good/parameterized.bloc' as 'myblock'\n"
            "tests/data/tmp/test.blocs: 2 error(s), 0 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert design is None


# ---------------------------------------------------------------------------
# cmd_block tests
# ---------------------------------------------------------------------------

class TestCmdBlock:

    def test_block_basic(self, blockdefs_x3, capsys):
        capsys.readouterr()  # discard fixture output
        blocs_str = "block b1 simple\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC, design=blockdefs_x3)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert design is not None
        assert "b1" in design.blocks
        assert design.blocks["b1"].block_def.name == "simple"
        assert "in" in design.blocks["b1"].pins
        assert "out" in design.blocks["b1"].pins
        assert "update" in design.blocks["b1"].functions
        assert "b1" in design.namespace

    def test_block_two_instances(self, blockdefs_x3, capsys):
        capsys.readouterr()  # discard fixture output
        blocs_str = "block b1 simple\nblock b2 simple\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC, design=blockdefs_x3)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert design is not None
        assert "b1" in design.blocks
        assert "b2" in design.blocks
        assert design.blocks["b1"] is not design.blocks["b2"]

    def test_block_missing_args_fails(self, blockdefs_x3, capsys):
        capsys.readouterr()  # discard fixture output
        blocs_str = "block\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC, design=blockdefs_x3)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1: error: 'block' requires an instance name and a blockdef name\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert design is None

    def test_block_missing_blockdef_name_fails(self, blockdefs_x3, capsys):
        capsys.readouterr()  # discard fixture output
        blocs_str = "block b1\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC, design=blockdefs_x3)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1: error: 'block' requires an instance name and a blockdef name\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert design is None

    def test_block_invalid_instance_name_fails(self, blockdefs_x3, capsys):
        capsys.readouterr()  # discard fixture output
        blocs_str = "block 123bad simple\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC, design=blockdefs_x3)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:7: error: invalid block instance name '123bad'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert design is None

    def test_block_invalid_blockdef_name_fails(self, blockdefs_x3, capsys):
        capsys.readouterr()  # discard fixture output
        blocs_str = "block b1 123bad\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC, design=blockdefs_x3)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:10: error: invalid blockdef name '123bad'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert design is None

    def test_block_extra_token_fails(self, blockdefs_x3, capsys):
        capsys.readouterr()  # discard fixture output
        blocs_str = "block b1 simple extra\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC, design=blockdefs_x3)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:17: error: unexpected token 'extra' after blockdef name\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert design is None

    def test_block_unknown_blockdef_name_fails(self, blockdefs_x3, capsys):
        capsys.readouterr()  # discard fixture output
        blocs_str = "block b1 nosuchblockdef\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC, design=blockdefs_x3)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1: error: unknown block definition 'nosuchblockdef'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert design is None

    def test_block_duplicate_instance_name_fails(self, blockdefs_x3, capsys):
        capsys.readouterr()  # discard fixture output
        blocs_str = "block b1 simple\nblock b1 simple\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC, design=blockdefs_x3)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:2: error: name 'b1' is already in use\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert design is None

    def test_block_name_conflicts_with_blockdef_fails(self, blockdefs_x3, capsys):
        capsys.readouterr()  # discard fixture output
        blocs_str = "block simple simple\n"
        design = parse_blocs_string(blocs_str, source=BLOCS_SRC, design=blockdefs_x3)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1: error: name 'simple' is already in use\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert design is None
