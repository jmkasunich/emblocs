# tests/test_bloc_parser.py
# Tests for bloc_parser.py

import pytest
from parse_common import (
    push_context, pop_context, clear_contexts, _context_stack,
)
from bloc_parser import parse_bloc_string, parse_bloc_file
from emblocs import BlockSpec, PinType, PinDir


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_context():
    clear_contexts()
    push_context(source="<test>")
    yield
    clear_contexts()


# ---------------------------------------------------------------------------
# parse_bloc_string happy path tests
# ---------------------------------------------------------------------------

class TestParseBlocString:

    def test_minimal_block(self):
        spec = parse_bloc_string(
            "block foo /// test block\n"
            "function update /// update\n"
        )
        assert spec is not None
        assert spec.name == "foo"

    def test_block_description(self):
        spec = parse_bloc_string(
            "block foo /// first line\n"
            "/// second line\n"
            "function update\n"
        )
        assert spec is not None
        assert "first line" in spec.description
        assert "second line" in spec.description

    def test_scalar_pin(self):
        spec = parse_bloc_string(
            "block foo /// test\n"
            "pin float input in /// input\n"
        )
        assert spec is not None
        assert len(spec.statements) == 1
        pin = spec.statements[0].statement
        assert pin.name_template == "in"
        assert pin.pin_type == PinType.FLOAT
        assert pin.direction == PinDir.INPUT

    def test_all_pin_types(self):
        spec = parse_bloc_string(
            "block foo /// test\n"
            "pin bool  input a\n"
            "pin u32   input b\n"
            "pin s32   input c\n"
            "pin float input d\n"
            "pin raw   input e\n"
        )
        assert spec is not None
        assert len(spec.statements) == 5

    def test_param_declaration(self):
        spec = parse_bloc_string(
            "block foo /// test\n"
            "param NCHAN u32 default=1 min=1 max=8 /// channels\n"
            "function update\n"
        )
        assert spec is not None
        assert len(spec.params) == 1
        assert spec.params[0].name == "NCHAN"
        assert spec.params[0].default == 1
        assert spec.params[0].min_val == 1
        assert spec.params[0].max_val == 8

    def test_var_declaration(self):
        spec = parse_bloc_string(
            "block foo /// test\n"
            "var float accumulated;\n"
        )
        assert spec is not None
        assert len(spec.statements) == 1
        var = spec.statements[0].statement
        assert var.field_name == "accumulated"

    def test_function_declaration(self):
        spec = parse_bloc_string(
            "block foo /// test\n"
            "function update /// update function\n"
        )
        assert spec is not None
        assert len(spec.statements) == 1
        func = spec.statements[0].statement
        assert func.name == "update"

    def test_if_endif(self):
        spec = parse_bloc_string(
            "block foo /// test\n"
            "param HAS_ENABLE bool default=0\n"
            "#if HAS_ENABLE\n"
            "pin bool input enable\n"
            "#endif\n"
        )
        assert spec is not None
        assert len(spec.statements) == 1
        stmt = spec.statements[0]
        assert stmt.conditions == ["HAS_ENABLE"]

    def test_unterminated_if_fails_message(self, capsys):
        spec = parse_bloc_string(
            "block foo /// test\n"
            "param HAS_ENABLE bool default=0\n"
            "#if HAS_ENABLE\n"
            "pin bool input enable\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>: error: end-of-file with 1 unterminated '#if' statements"
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )
        assert spec is None

    def test_duplicate_block_fails_message(self, capsys):
        spec = parse_bloc_string(
            "block foo /// test\n"
            "block bar /// test\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:1: error: 'block' declared more than once"
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )
        assert spec is None

    def test_no_block_statement_fails_message(self, capsys):
        spec = parse_bloc_string("pin float input in\n")
        actual = capsys.readouterr().err.strip()
        expected = "<string>: error: no 'block' declaration found"
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )
        assert spec is None

    def test_missing_block_name_fails_message(self, capsys):
        spec = parse_bloc_string("block\n")
        actual = capsys.readouterr().err.strip()
        expected = "<string>:1:1: error: 'block' declaration requires a name"
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )
        assert spec is None
