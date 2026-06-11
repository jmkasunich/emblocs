# tests/test_blocs_parser.py
from __future__ import annotations
import os
import pytest
from pathlib import Path
from parse_common import (Token, ctx)
from blocs_parser import (
    lex_lines, set_get_block_spec,
    parse_blocs, parse_blocs_string, parse_blocs_file,
)
from bloc_parser import parse_bloc_file
from emblocs import (
    PinType, Design, BlockSpec,
)


from conftest import TMP_DIR, PYTHON_DIR, GOOD_DIR


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_context():
    ctx.clear()
    ctx.push(source="<test>")
    yield
    ctx.clear()

def block_spec_getter(name: str, design: Design) -> BlockSpec | None:
    bloc_path = GOOD_DIR / f"{name}.bloc"
    if not bloc_path.is_file():
        ctx.error(f"'{name}.bloc' not found on block search path")
        return None
    return parse_bloc_file(bloc_path.as_posix())

@pytest.fixture(autouse=True)
def set_block_spec_callback():
    set_get_block_spec(block_spec_getter)
    yield

@pytest.fixture
def test_blocs(tmp_dir) -> Path:
    """return path to standard test file"""
    return tmp_dir / "test.blocs"

def rcwd(p: Path) -> str:
    """ return path relative to current working directory, as a posix string. """
    return Path(os.path.relpath(p, PYTHON_DIR)).as_posix()

BLOCS_SRC = Path(os.path.relpath(TMP_DIR / "test.blocs", PYTHON_DIR)).as_posix()

@pytest.fixture
def blockdefs_x3():
    """ provides a design with three blockdefs for testing block commands.
        note that the command produces output to stderr, so clear the
        capture using capsys.readouterr() before starting the actual test."""
    blocs_str = (
        f"blockdef simple     simple\n"
        f"blockdef param_v1   parameterized NCHAN=2 MASK=3 HAS_ENABLE=0\n"
        f"blockdef param_v2   parameterized NCHAN=4 MASK=0xA HAS_ENABLE=1\n"
    )
    design = Design(abs_path="test_design")
    result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
    assert result is True
    assert len(design.block_defs) == 3
    return design

@pytest.fixture
def blocks_x4(test_blocs):
    """Provides a design with three blockdefs and four block instances
    for testing signal, thread, and subcommand behavior.
    Two instances share the same blockdef (simple) to test independence.
    Note: produces stderr output; call capsys.readouterr() before testing."""
    blocs_str = (
        f"blockdef simple     simple\n"
        f"blockdef param_v1   parameterized NCHAN=2 MASK=3 HAS_ENABLE=0\n"
        f"blockdef param_v2   parameterized NCHAN=4 MASK=0xA HAS_ENABLE=1\n"
        f"block b1 simple\n"
        f"block b2 simple\n"
        f"block b3 param_v1\n"
        f"block b4 param_v2\n"
        f"thread fast 1000000\n"
        f"thread slow 10000000\n"
        f"signal sig_float float\n"
        f"signal sig_bool  bool\n"
        f"signal sig_u32   u32\n"
        f"signal sig_s32   s32\n"
    )
    design = Design(abs_path="test_design")
    result = parse_blocs_string(blocs_str, design, source=rcwd(test_blocs))
    assert result is True
    assert len(design.block_defs) == 3
    assert len(design.blocks) == 4
    assert len(design.signals) == 4
    assert len(design.threads) == 2
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
#        design = Design(abs_path="test_design")
#        result = parse_blocs_string(blocs_str, design, source=source)
#        assert result is True
#        assert "myblock" in design.block_defs

    def test_basic_blockdef(self, capsys):
        blocs_str = f"blockdef myblock simple\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert result is True
        assert "myblock" in design.block_defs
        assert "in" in design.block_defs["myblock"].pins
        assert "out" in design.block_defs["myblock"].pins
        assert "update" in design.block_defs["myblock"].functions

    def test_blockdef_with_params(self, capsys):
        blocs_str = f"blockdef myblock parameterized NCHAN=3 MASK=7 HAS_ENABLE=1\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert result is True
        assert design.block_defs["myblock"].params["NCHAN"] == 3
        assert design.block_defs["myblock"].params["MASK"] == 7
        assert design.block_defs["myblock"].params["HAS_ENABLE"] == 1

    def test_blockdef_two_variants_one_bloc(self, capsys):
        blocs_str = (f"blockdef block1 parameterized NCHAN=3 MASK=7 HAS_ENABLE=1\n"
                     f"blockdef block2 parameterized NCHAN=4 MASK=0xA HAS_ENABLE=0\n")
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert result is True
        assert design.block_defs["block1"].params["NCHAN"] == 3
        assert design.block_defs["block1"].params["MASK"] == 7
        assert design.block_defs["block1"].params["HAS_ENABLE"] == 1
        assert design.block_defs["block2"].params["NCHAN"] == 4
        assert design.block_defs["block2"].params["MASK"] == 10
        assert design.block_defs["block2"].params["HAS_ENABLE"] == 0

    def test_blockdef_unknown_param_warns(self, capsys):
        blocs_str = f"blockdef myblock simple UNKNOWN=3\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1:25: warning: unmatched parameter 'UNKNOWN' will be ignored\n"
            "tests/data/tmp/test.blocs: 0 error(s), 1 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert result is True

    def test_blockdef_missing_param_uses_default_informs(self, capsys):
        blocs_str = f"blockdef myblock parameterized MASK=7\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1: info: parameter 'NCHAN' not supplied, using default value 2\n"
            "tests/data/tmp/test.blocs:1: info: parameter 'HAS_ENABLE' not supplied, using default value 0\n"
            "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 2 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert result is True
        assert design.block_defs["myblock"].params["NCHAN"] == 2
        assert design.block_defs["myblock"].params["MASK"] == 7
        assert design.block_defs["myblock"].params["HAS_ENABLE"] == 0

    def test_blockdef_too_few_tokens_fails(self, capsys):
        blocs_str = f"blockdef parameterized\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1: error: 'blockdef' requires a new def name and a source block name\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert result is False

    def test_blockdef_missing_name_fails(self, capsys):
        blocs_str = f"blockdef parameterized NCHAN=3 MASK=7 HAS_ENABLE=1\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1:24: error: invalid source block name 'NCHAN=3'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert result is False

    def test_blockdef_missing_path_fails(self, capsys):
        blocs_str = f"blockdef myblock NCHAN=3 MASK=7 HAS_ENABLE=1\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1:18: error: invalid source block name 'NCHAN=3'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert result is False

    def test_blockdef_invalid_name_fails(self, capsys):
        blocs_str = f"blockdef 123bad simple\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1:10: error: invalid blockdef name '123bad'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert result is False

    def test_blockdef_invalid_param_name_fails(self, capsys):
        blocs_str = f"blockdef myblock simple 123BAD=3\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1:25: error: invalid parameter name '123BAD'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert result is False

    def test_blockdef_file_not_found_fails(self, capsys):
        blocs_str = f"blockdef myblock no_such_block\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1:18: error: 'no_such_block.bloc' not found on block search path\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert result is False

    def test_blockdef_duplicate_name_fails(self, capsys):
        blocs_str = ( f"blockdef myblock simple\n"
                      f"blockdef myblock simple\n")
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:2:10: error: name 'myblock' is already in use\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert result is False

    def test_blockdef_invalid_param_value_fails(self, capsys):
        blocs_str = f"blockdef myblock parameterized NCHAN=notanumber MASK=7 HAS_ENABLE=1\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1:32: error: invalid value 'notanumber' for 'NCHAN': expected an integer\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert result is False

    def test_blockdef_out_of_range_param_value_fails(self, capsys):
        blocs_str = f"blockdef myblock parameterized NCHAN=12 MASK=7 HAS_ENABLE=1\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        expect = (
            "tests/data/tmp/test.blocs:1: error: parameter 'NCHAN' value 12 is greater than max (4)\n"
            "tests/data/tmp/test.blocs:1: error: failed to resolve 'parameterized' as 'myblock'\n"
            "tests/data/tmp/test.blocs: 2 error(s), 0 warning(s), 0 info(s)")
        assert actual == expect, f"\nEXPECT: {expect!r}\nACTUAL: {actual!r}\n"
        assert result is False


# ---------------------------------------------------------------------------
# cmd_block tests
# ---------------------------------------------------------------------------

class TestCmdBlock:

    def test_block_basic(self, blockdefs_x3, capsys):
        capsys.readouterr()  # discard fixture output
        blocs_str = "block b1 simple\n"
        design = blockdefs_x3
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert "b1" in design.blocks
        assert design.blocks["b1"].block_def.name == "simple"
        assert "in" in design.blocks["b1"].pins
        assert "out" in design.blocks["b1"].pins
        assert "update" in design.blocks["b1"].functions
        assert "b1" in design.namespace

    def test_block_two_instances(self, blockdefs_x3, capsys):
        capsys.readouterr()  # discard fixture output
        blocs_str = "block b1 simple\nblock b2 simple\n"
        design = blockdefs_x3
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert "b1" in design.blocks
        assert "b2" in design.blocks
        assert design.blocks["b1"] is not design.blocks["b2"]

    def test_block_missing_args_fails(self, blockdefs_x3, capsys):
        capsys.readouterr()  # discard fixture output
        blocs_str = "block\n"
        design = blockdefs_x3
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1: error: 'block' requires an instance name and a blockdef name\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_block_missing_blockdef_name_fails(self, blockdefs_x3, capsys):
        capsys.readouterr()  # discard fixture output
        blocs_str = "block b1\n"
        design = blockdefs_x3
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1: error: 'block' requires an instance name and a blockdef name\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_block_invalid_instance_name_fails(self, blockdefs_x3, capsys):
        capsys.readouterr()  # discard fixture output
        blocs_str = "block 123bad simple\n"
        design = blockdefs_x3
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:7: error: invalid block instance name '123bad'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_block_invalid_blockdef_name_fails(self, blockdefs_x3, capsys):
        capsys.readouterr()  # discard fixture output
        blocs_str = "block b1 123bad\n"
        design = blockdefs_x3
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:10: error: invalid blockdef name '123bad'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_block_extra_token_fails(self, blockdefs_x3, capsys):
        capsys.readouterr()  # discard fixture output
        blocs_str = "block b1 simple extra\n"
        design = blockdefs_x3
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:17: error: 'b1' (BlockInstance) has no subcommands, got 'extra'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_block_unknown_blockdef_name_fails(self, blockdefs_x3, capsys):
        capsys.readouterr()  # discard fixture output
        blocs_str = "block b1 nosuchblockdef\n"
        design = blockdefs_x3
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1: error: unknown block definition 'nosuchblockdef'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_block_duplicate_instance_name_fails(self, blockdefs_x3, capsys):
        capsys.readouterr()  # discard fixture output
        blocs_str = "block b1 simple\nblock b1 simple\n"
        design = blockdefs_x3
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:2: error: name 'b1' is already in use\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

# ---------------------------------------------------------------------------
# cmd_signal tests
# ---------------------------------------------------------------------------

class TestCmdSignal:

    def test_signal_basic_float(self, capsys):
        capsys.readouterr()
        blocs_str = "signal s1 float\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert "s1" in design.signals
        assert design.signals["s1"].sig_type == PinType.FLOAT
        assert "s1" in design.namespace

    def test_signal_basic_bool(self, capsys):
        capsys.readouterr()
        blocs_str = "signal s1 bool\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.signals["s1"].sig_type == PinType.BOOL

    def test_signal_basic_u32(self, capsys):
        capsys.readouterr()
        blocs_str = "signal s1 u32\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.signals["s1"].sig_type == PinType.U32

    def test_signal_basic_s32(self, capsys):
        capsys.readouterr()
        blocs_str = "signal s1 s32\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.signals["s1"].sig_type == PinType.S32

    def test_signal_default_value(self, capsys):
        capsys.readouterr()
        blocs_str = "signal s1 float\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.signals["s1"].value == 0.0

    def test_signal_missing_args_fails(self, capsys):
        capsys.readouterr()
        blocs_str = "signal\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1: error: 'signal' requires a signal name and a type\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_signal_missing_type_fails(self, capsys):
        capsys.readouterr()
        blocs_str = "signal s1\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1: error: 'signal' requires a signal name and a type\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_signal_invalid_name_fails(self, capsys):
        capsys.readouterr()
        blocs_str = "signal 123bad float\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:8: error: invalid signal name '123bad'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_signal_invalid_type_fails(self, capsys):
        capsys.readouterr()
        blocs_str = "signal s1 nosuchtype\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:11: error: invalid signal type 'nosuchtype'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_signal_duplicate_name_fails(self, capsys):
        capsys.readouterr()
        blocs_str = "signal s1 float\nsignal s1 float\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:2: error: name 's1' is already in use\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

# ---------------------------------------------------------------------------
# cmd_thread tests
# ---------------------------------------------------------------------------

class TestCmdThread:

    def test_thread_basic(self, capsys):
        blocs_str = "thread t1 1000000\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert "t1" in design.threads
        assert design.threads["t1"].period_ns == 1000000
        assert "t1" in design.namespace

    def test_thread_period_hex(self, capsys):
        blocs_str = "thread t1 0xF4240\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.threads["t1"].period_ns == 1000000

    def test_thread_period_expression(self, capsys):
        blocs_str = "thread t1 1000*1000\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.threads["t1"].period_ns == 1000000

    def test_thread_missing_args_fails(self, capsys):
        blocs_str = "thread\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1: error: 'thread' requires a thread name and a period\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_thread_missing_period_fails(self, capsys):
        blocs_str = "thread t1\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1: error: 'thread' requires a thread name and a period\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_thread_invalid_name_fails(self, capsys):
        blocs_str = "thread 123bad 1000000\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:8: error: invalid thread name '123bad'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_thread_zero_period_fails(self, capsys):
        blocs_str = "thread t1 0\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1: error: thread period must be positive, got 0\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_thread_negative_period_fails(self, capsys):
        blocs_str = "thread t1 -1000000\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:11: error: u32 value '-1000000' is out of range [0, 4294967295]\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_thread_invalid_period_fails(self, capsys):
        blocs_str = "thread t1 notanumber\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:11: error: invalid u32 value 'notanumber': "
            "expression 'notanumber': unknown variable: 'notanumber'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_thread_duplicate_name_fails(self, capsys):
        blocs_str = "thread t1 1000000\nthread t1 2000000\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:2: error: name 't1' is already in use\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

# ---------------------------------------------------------------------------
# namespace conflict tests (circular: A->B, B->C, C->D, D->A)
# ---------------------------------------------------------------------------

class TestCmdConflicts:

    def test_signal_conflicts_with_blockdef(self, test_blocs, capsys):
        blocs_str = (f"blockdef myblock simple\n"
                     f"signal myblock float\n")
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=rcwd(test_blocs))
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:2: error: name 'myblock' is already in use\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_blockdef_conflicts_with_thread(self, test_blocs, capsys):
        blocs_str = (f"thread mythread 1000000\n"
                     f"blockdef mythread simple\n")
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=rcwd(test_blocs))
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:2:10: error: name 'mythread' is already in use\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_thread_conflicts_with_block(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "thread b1 1000000\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1: error: name 'b1' is already in use\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_block_conflicts_with_signal(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = ("signal mysignal float\n"
                     "block mysignal simple\n")
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:2: error: name 'mysignal' is already in use\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

# ---------------------------------------------------------------------------
# subcmd '=' tests
# ---------------------------------------------------------------------------

class TestSubcmdEquals:

    def test_set_float_signal_inline(self, capsys):
        blocs_str = "signal s1 float =1.5\n"
        design = Design(abs_path="test_design")
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.signals["s1"].value == 1.5

    def test_set_float_signal_modification(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "sig_float =2.5\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.signals["sig_float"].value == 2.5

    def test_set_bool_signal_true(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "sig_bool =true\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.signals["sig_bool"].value == 1

    def test_set_bool_signal_false(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "sig_bool =false\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.signals["sig_bool"].value == 0

    def test_set_bool_signal_expression(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "sig_bool =4&3\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.signals["sig_bool"].value == 0

    def test_set_u32_signal(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "sig_u32 =42\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.signals["sig_u32"].value == 42

    def test_set_u32_signal_hex(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "sig_u32 =0xFF\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.signals["sig_u32"].value == 255

    def test_set_u32_signal_expression(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "sig_u32 =48*200\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.signals["sig_u32"].value == 9600

    def test_set_s32_signal(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "sig_s32 =-42\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.signals["sig_s32"].value == -42

    def test_set_float_signal_expression(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "sig_float =25.4/4\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert abs(design.signals["sig_float"].value - 6.35) < 1e-6

    def test_set_signal_empty_arg_fails(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "sig_float =\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:11: error: invalid float value '': expression '': invalid syntax\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_set_u32_signal_out_of_range_fails(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "sig_u32 =5000000000\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:9: error: u32 value '5000000000' is out of range [0, 4294967295]\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_set_s32_signal_out_of_range_fails(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "sig_s32 =5000000000\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:9: error: s32 value '5000000000' is out of range [-2147483648, 2147483647]\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_set_float_pin_inline(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "b1.in =3.14\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.blocks["b1"].pins["in"].signal.value == 3.14

    def test_set_float_pin_out_of_range_fails(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "b1.in =1e300\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:7: error: float value '1e300' is out of range for a 32-bit float\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False


# ---------------------------------------------------------------------------
# subcommand '+' tests
# ---------------------------------------------------------------------------

class TestSubcmdPlus:

    def test_link_signal_to_pin(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "sig_float +b1.in\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.blocks["b1"].pins["in"].signal is design.signals["sig_float"]

    def test_link_pin_to_signal(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "b1.in +sig_float\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.blocks["b1"].pins["in"].signal is design.signals["sig_float"]

    def test_link_signal_to_output_pin(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "sig_float +b1.out\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.signals["sig_float"].driver is design.blocks["b1"].pins["out"]

    def test_link_thread_to_function(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "fast +b1.update\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.blocks["b1"].functions["update"].thread is design.threads["fast"]

    def test_link_function_to_thread(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "b1.update +fast\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.blocks["b1"].functions["update"].thread is design.threads["fast"]

    def test_link_unknown_arg_fails(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "sig_float +nosuchpin\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:11: error: 'nosuchpin' not found in design\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_link_empty_arg_fails(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "sig_float +\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:11: error: '+' requires a name\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_link_inline_signal_creation(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "signal s1 float +b1.in\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.blocks["b1"].pins["in"].signal is design.signals["s1"]

    def test_link_inline_thread_creation(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "thread t1 500000 +b1.update\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.blocks["b1"].functions["update"].thread is design.threads["t1"]

    def test_link_pin_to_new_signal_fails(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = ("signal sig_float2 float\n"
                     "sig_float +b1.in\n"
                     "b1.in +sig_float2\n")
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:3:7: error: pin 'b1.in' is already connected to signal 'sig_float'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

# ---------------------------------------------------------------------------
# subcommand '-' tests
# ---------------------------------------------------------------------------

class TestSubcmdMinus:

    def test_unlink_pin_no_arg(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = ("sig_float +b1.in\n"
                     "b1.in -\n")
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.blocks["b1"].pins["in"].signal.is_dummy

    def test_unlink_function_no_arg(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = ("fast +b1.update\n"
                     "b1.update -\n")
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.blocks["b1"].functions["update"].thread is None

    def test_unlink_pin_from_signal(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = ("sig_float +b1.in\n"
                     "sig_float -b1.in\n")
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.blocks["b1"].pins["in"].signal.is_dummy

    def test_unlink_function_from_thread(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = ("fast +b1.update\n"
                     "fast -b1.update\n")
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.blocks["b1"].functions["update"].thread is None

    def test_unlink_pin_with_arg_fails(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "b1.in -sig_float\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:7: error: '-' does not take an argument for PinInstance\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_unlink_signal_no_arg_fails(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "sig_float -\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:11: error: '-' requires a name\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False


# ---------------------------------------------------------------------------
# subcommand '-+' tests
# ---------------------------------------------------------------------------

class TestSubcmdRelink:

    def test_relink_pin_to_new_signal(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = ("signal sig_float2 float\n"
                     "sig_float +b1.in\n"
                     "b1.in -+sig_float2\n")
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.blocks["b1"].pins["in"].signal is design.signals["sig_float2"]
        assert design.blocks["b1"].pins["in"] not in design.signals["sig_float"].readers

    def test_relink_pin_to_new_signal_rev(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = ("signal sig_float2 float\n"
                     "sig_float +b1.in\n"
                     "sig_float2 -+b1.in\n")
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.blocks["b1"].pins["in"].signal is design.signals["sig_float2"]
        assert design.blocks["b1"].pins["in"] not in design.signals["sig_float"].readers

    def test_relink_function_to_new_thread(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = ("fast +b1.update\n"
                     "b1.update -+slow\n")
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.blocks["b1"].functions["update"].thread is design.threads["slow"]
        assert design.blocks["b1"].functions["update"] not in design.threads["fast"].functions

    def test_relink_function_to_new_thread_rev(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = ("fast +b1.update\n"
                     "slow -+b1.update\n")
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.blocks["b1"].functions["update"].thread is design.threads["slow"]
        assert design.blocks["b1"].functions["update"] not in design.threads["fast"].functions

    def test_relink_unconnected_pin(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "b1.in -+sig_float\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.blocks["b1"].pins["in"].signal is design.signals["sig_float"]

    def test_relink_empty_arg_fails(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "b1.in -+\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:7: error: '-+' requires a name\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False

    def test_multiple_plus_subcommands(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "signal s1 float +b1.in +b2.in\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.blocks["b1"].pins["in"].signal is design.signals["s1"]
        assert design.blocks["b2"].pins["in"].signal is design.signals["s1"]

    def test_mixed_subcommands_on_one_line(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "signal s1 float =1.5 +b1.in\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.signals["s1"].value == 1.5
        assert design.blocks["b1"].pins["in"].signal is design.signals["s1"]

    def test_connect_then_disconnect_on_one_line(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "signal s1 float +b1.in -b1.in\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        assert design.blocks["b1"].pins["in"].signal.is_dummy

    def test_thread_multiple_functions(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "thread t1 500000 +b1.update +b2.update\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 0 info(s)"
        assert result is True
        funcs = design.threads["t1"].functions
        assert len(funcs) == 2
        assert funcs[0] is design.blocks["b1"].functions["update"]
        assert funcs[1] is design.blocks["b2"].functions["update"]

    def test_signal_multiple_subcommand_abort_on_error(self, blocks_x4, capsys):
        capsys.readouterr()
        blocs_str = "sig_float +b1.in =1.5 +b3.out =3 -b1.in\n"
        design = blocks_x4
        result = parse_blocs_string(blocs_str, design, source=BLOCS_SRC)
        actual = capsys.readouterr().err.strip()
        assert actual == (
            "tests/data/tmp/test.blocs:1:31: error: signal 'sig_float' is driven by 'b3.out'; cannot set value directly\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False
        assert blocks_x4.signals["sig_float"].value==1.5
        assert blocks_x4.blocks["b1"].pins["in"].signal == blocks_x4.signals["sig_float"]
