# tests/test_blocs_parser.py
import pytest
from parse_common import Token, push_context, pop_context, clear_contexts, _context_stack
from blocs_parser import lex_lines, parse_blocs, parse_blocs_string

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

class TestParseBlocs:
    pass  # tests to be added
