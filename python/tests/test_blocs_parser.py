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
        assert result[0][0] == Token("blockdef", 1, 1)
        assert result[0][1] == Token("foo",      1, 10)
        assert result[0][2] == Token("bar.bloc", 1, 14)


class TestParseBlocs:
    pass  # tests to be added
