# tests/test_blocs_parser.py
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

@pytest.fixture(autouse=True)
def clean_context():
    clear_contexts()
    push_context(source="<test>")
    yield
    clear_contexts()

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
def minimal_bloc(tmp_dir) -> Path:
    """Write a minimal valid .bloc file and return its path."""
    bloc = tmp_dir / "minimal.bloc"
    bloc.write_text(
        "block minimal /// minimal test block\n"
        "pin float input in /// input\n"
        "pin float output out /// output\n"
        "function update /// update\n"
    )
    return bloc


@pytest.fixture
def param_bloc(tmp_dir) -> Path:
    """Write a .bloc file with parameters and return its path."""
    bloc = tmp_dir / "param_bloc.bloc"
    bloc.write_text(
        "block param_bloc /// block with parameters\n"
        "param NCHAN u32 default=1 min=1 max=8 /// number of channels\n"
        "param HAS_ENABLE bool default=0 /// enable flag\n"
        "pin float input in /// input\n"
        "function update /// update\n"
    )
    return bloc


def make_blocs(tmp_dir: Path, bloc_path: Path, extra: str = "") -> tuple[str, str]:
    """
    Return a tuple of (.blocs string, source path) for use with parse_blocs_string().
    Uses relative paths based on tests/data/tmp/ location.
    """
    rel = bloc_path.relative_to(tmp_dir).as_posix()
    blocs_str = f"blockdef myblock {rel}{extra}\n"
    source = "tests/data/tmp/test.blocs"
    return blocs_str, source

# ---------------------------------------------------------------------------
# cmd_blockdef tests
# ---------------------------------------------------------------------------

class TestCmdBlockdef:

    def test_basic_blockdef(self, tmp_dir, minimal_bloc):
        blocs_str, source = make_blocs(tmp_dir, minimal_bloc)
        design = parse_blocs_string(blocs_str, source=source)
        assert design is not None
        assert "myblock" in design.block_defs

    def test_blockdef_pins_resolved(self, tmp_dir, minimal_bloc):
        blocs_str, source = make_blocs(tmp_dir, minimal_bloc)
        design = parse_blocs_string(blocs_str, source=source)
        assert design is not None
        assert "in" in design.block_defs["myblock"].pins
        assert "out" in design.block_defs["myblock"].pins

    def test_blockdef_functions_resolved(self, tmp_dir, minimal_bloc):
        blocs_str, source = make_blocs(tmp_dir, minimal_bloc)
        design = parse_blocs_string(blocs_str, source=source)
        assert design is not None
        assert "update" in design.block_defs["myblock"].functions

    def test_blockdef_cached(self, tmp_dir, minimal_bloc):
        blocs_str, source = make_blocs(tmp_dir, minimal_bloc)
        parse_blocs_string(blocs_str, source=source)
        assert len(_bloc_spec_cache) == 1

    def test_blockdef_cache_reused(self, tmp_dir, minimal_bloc):
        """Two blockdefs from same .bloc file share one cache entry."""
        rel = minimal_bloc.relative_to(tmp_dir).as_posix()
        blocs_str = (f"blockdef block1 {rel}\n"
                     f"blockdef block2 {rel}\n")
        source = (tmp_dir / "test.blocs").as_posix()
        design = parse_blocs_string(blocs_str, source=source)
        assert design is not None
        assert len(_bloc_spec_cache) == 1
        assert "block1" in design.block_defs
        assert "block2" in design.block_defs

    def test_blockdef_with_params(self, tmp_dir, param_bloc, capsys):
        rel = param_bloc.relative_to(tmp_dir).as_posix()
        blocs_str = f"blockdef myblock {rel} NCHAN=4\n"
        source = (tmp_dir / "test.blocs").as_posix()
        design = parse_blocs_string(blocs_str, source=source)
        assert design is not None
        assert design.block_defs["myblock"].params["NCHAN"] == 4

    def test_blockdef_unknown_param_warns_message(self, tmp_dir, minimal_bloc, capsys):
        blocs_str, source = make_blocs(tmp_dir, minimal_bloc, extra=" UNKNOWN=1")
        design = parse_blocs_string(blocs_str, source=source)
        actual = capsys.readouterr().err.strip()
        expected = (
            "tests/data/tmp/test.blocs:1:31: warning: unmatched parameter 'UNKNOWN' will be ignored\n"
            "tests/data/tmp/test.blocs: 0 error(s), 1 warning(s), 0 info(s)")
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )
        assert design is not None

    def test_blockdef_missing_param_uses_default_informs_message(self, tmp_dir, param_bloc, capsys):
        blocs_str, source = make_blocs(tmp_dir, param_bloc)
        design = parse_blocs_string(blocs_str, source=source)
        actual = capsys.readouterr().err.strip()
        expected = (
            "tests/data/tmp/test.blocs:1: info: parameter 'NCHAN' not supplied, using default value 1\n"
            "tests/data/tmp/test.blocs:1: info: parameter 'HAS_ENABLE' not supplied, using default value 0\n"
            "tests/data/tmp/test.blocs: 0 error(s), 0 warning(s), 2 info(s)")
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )
        assert design is not None
        assert design.block_defs["myblock"].params["NCHAN"] == 1
        assert design.block_defs["myblock"].params["HAS_ENABLE"] == 0

    def test_blockdef_missing_name_fails_message(self, tmp_dir, capsys):
        design = parse_blocs_string("blockdef\n", source="test.blocs")
        actual = capsys.readouterr().err.strip()
        expected = (
            "test.blocs:1: error: 'blockdef' requires a name and a path\n"
            "test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )
        assert design is None

    def test_blockdef_missing_path_fails_message(self, tmp_dir, capsys):
        design = parse_blocs_string("blockdef myblock\n", source="test.blocs")
        actual = capsys.readouterr().err.strip()
        expected = (
            "test.blocs:1: error: 'blockdef' requires a name and a path\n"
            "test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )
        assert design is None

    def test_blockdef_invalid_name_fails_message(self, tmp_dir, minimal_bloc, capsys):
        blocs_str, source = make_blocs(tmp_dir, minimal_bloc)
        blocs_str = blocs_str.replace("myblock", "123bad")
        design = parse_blocs_string(blocs_str, source=source)
        actual = capsys.readouterr().err.strip()
        expected = (
            "tests/data/tmp/test.blocs:1:10: error: invalid blockdef name '123bad'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )
        assert design is None

    def test_blockdef_invalid_param_name_fails_message(self, tmp_dir, minimal_bloc, capsys):
        blocs_str, source = make_blocs(tmp_dir, minimal_bloc, extra=" 123=1")
        design = parse_blocs_string(blocs_str, source=source)
        actual = capsys.readouterr().err.strip()
        expected = (
            "tests/data/tmp/test.blocs:1:31: error: invalid parameter name '123'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )
        assert design is None

    def test_blockdef_file_not_found_fails_message(self, tmp_dir, capsys):
        design = parse_blocs_string("blockdef myblock nonexistent.bloc\n",
                                  source="test.blocs")
        actual = capsys.readouterr().err.strip()
        expected = (
            "test.blocs:1:18: error: bloc file not found: 'nonexistent.bloc'\n"
            "test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )
        assert design is None

    def test_blockdef_duplicate_name_fails_message(self, tmp_dir, minimal_bloc, capsys):
        blocs_str, source = make_blocs(tmp_dir, minimal_bloc)
        blocs_str = blocs_str + blocs_str
        design = parse_blocs_string(blocs_str, source=source)
        actual = capsys.readouterr().err.strip()
        expected = (
            "tests/data/tmp/test.blocs:2:10: error: name 'myblock' is already in use\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )
        assert design is None

    def test_blockdef_invalid_param_value_fails_message(self, tmp_dir, param_bloc, capsys):
        blocs_str, source = make_blocs(tmp_dir, param_bloc,
                                          extra=" NCHAN=notanumber")
        design = parse_blocs_string(blocs_str, source=source)
        actual = capsys.readouterr().err.strip()
        expected = (
            "tests/data/tmp/test.blocs:1:34: error: invalid value 'notanumber' for 'NCHAN'; expected an integer\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )
        assert design is None

    def test_blockdef_out_of_range_param_value_fails_message(self, tmp_dir, param_bloc, capsys):
        blocs_str, source = make_blocs(tmp_dir, param_bloc,
                                          extra=" NCHAN=12 HAS_ENABLE=1")
        design = parse_blocs_string(blocs_str, source=source)
        actual = capsys.readouterr().err.strip()
        expected = (
            "tests/data/tmp/test.blocs:1: error: parameter 'NCHAN' value 12 is greater than max (8)\n"
            "tests/data/tmp/test.blocs:1: error: failed to resolve 'param_bloc.bloc' as 'myblock'\n"
            "tests/data/tmp/test.blocs: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )
        assert design is None
