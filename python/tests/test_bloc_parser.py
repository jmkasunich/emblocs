# tests/test_bloc_parser.py
# Tests for bloc_parser.py

from __future__ import annotations
import pytest
from parse_common import ctx, read_source_string
from bloc_parser import parse_bloc_string, parse_bloc_file, parse_bloc, Section, ParseState
import bloc_parser   # for monkeypatching in lexer tests
from emblocs import BlockSpec, DimSpec, PinType, PinDir, U32_MAX


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_context():
    ctx.clear()
    ctx.push(source="<test>")
    yield
    ctx.clear()

def _run_lexer(text, monkeypatch):
    """
    Run parse_bloc() on text with parse_statement() stubbed out.

    Returns a list of (token_texts, description) tuples, one per call
    that parse_bloc() would have made to parse_statement(). This isolates
    parse_bloc()'s line-processing logic -- comment stripping, description
    handling, and statement flushing -- from per-keyword parsing.
    """
    calls = []
    def fake_parse_statement(spec, state, tokens, description):
        calls.append(([t.text for t in tokens], description))
        state.section = Section.PARAMS
    monkeypatch.setattr(bloc_parser, "parse_statement", fake_parse_statement)
    lines = read_source_string(text)
    parse_bloc(lines)
    ctx.pop()
    return calls

# ---------------------------------------------------------------------------
# parse_bloc() line-processing ("lexer") tests
#
# parse_statement() is stubbed out via _run_lexer(), so these tests verify
# only comment stripping, description handling, and statement flushing --
# not per-keyword parsing.
# ---------------------------------------------------------------------------

class TestBlocLexing:

    def test_simple_statement(self, monkeypatch):
        calls = _run_lexer("foo bar\n", monkeypatch)
        assert calls == [(["foo", "bar"], "")]

    def test_comment_stripped(self, monkeypatch):
        calls = _run_lexer("foo bar // a comment\n", monkeypatch)
        assert calls == [(["foo", "bar"], "")]

    def test_standalone_single_line_description(self, monkeypatch):
        calls = _run_lexer("/// a standalone description\n", monkeypatch)
        assert calls == [([], " a standalone description")]

    def test_standalone_multiline_description(self, monkeypatch):
        calls = _run_lexer(
            "/// first line\n"
            "/// second line\n"
            "function update\n",
            monkeypatch)
        assert calls == [
            ([], " first line\n second line"),
            (["function", "update"], ""),
        ]

    def test_standalone_multiline_description_after_token(self, monkeypatch):
        calls = _run_lexer(
            "foo bar\n"
            "/// first line\n"
            "/// second line\n"
            "function update\n",
            monkeypatch)
        assert calls == [
            (["foo", "bar"], ""),
            ([], " first line\n second line"),
            (["function", "update"], ""),
        ]

    def test_single_line_description(self, monkeypatch):
        calls = _run_lexer("foo bar /// the foo statement\n", monkeypatch)
        assert calls == [(["foo", "bar"], " the foo statement")]

    def test_multiline_description(self, monkeypatch):
        calls = _run_lexer(
            "foo bar /// first line\n"
            "/// second line\n"
            "function update\n",
            monkeypatch)
        assert calls == [
            (["foo", "bar"], " first line\n second line"),
            (["function", "update"], ""),
        ]

    def test_indented_multiline_description(self, monkeypatch):
        calls = _run_lexer(
            "foo /// first line\n"
            "    /// second line\n"
            "    ///   indented third line\n"
            "function update\n",
            monkeypatch)
        assert calls == [
            (["foo"], " first line\n second line\n   indented third line"),
            (["function", "update"], ""),
        ]

    def test_trailing_whitespace_stripped_leading_preserved(self, monkeypatch):
        calls = _run_lexer("foo bar ///   text   \n", monkeypatch)
        assert calls == [(["foo", "bar"], "   text")]

    def test_blank_and_comment_only_lines(self, monkeypatch):
        calls = _run_lexer(
            "foo bar\n"
            "\n"
            "// just a comment\n"
            "function update\n",
            monkeypatch)
        assert calls == [
            (["foo", "bar"], ""),
            (["function", "update"], ""),
        ]

    def test_end_of_input_flush_tokens(self, monkeypatch):
        # last statement has no trailing blank line
        calls = _run_lexer("foo bar", monkeypatch)
        assert calls == [(["foo", "bar"], "")]

    def test_end_of_input_flush_description(self, monkeypatch):
        # last statement has no trailing blank line
        calls = _run_lexer("/// description", monkeypatch)
        assert calls == [([], " description")]

    def test_multiple_statements_no_bleed_over(self, monkeypatch):
        calls = _run_lexer(
            "foo bar /// the foo statement\n"
            "pin float input in /// input value\n"
            "// a plain comment, ignored\n"
            "function update /// the update function\n",
            monkeypatch)
        assert calls == [
            (["foo", "bar"], " the foo statement"),
            (["pin", "float", "input", "in"], " input value"),
            (["function", "update"], " the update function"),
        ]

# ---------------------------------------------------------------------------
# header tests
# ---------------------------------------------------------------------------

    def test_block_name_and_description(self):
        spec = parse_bloc_string(
            "/// test block\n"
            "function update\n",
            source="foo.bloc"
        )
        assert spec is not None
        assert spec.name == "foo"
        assert spec.description == " test block"

    def test_block_name_and_long_description(self):
        spec = parse_bloc_string(
            "/// test block\n"
            "/// with long\n"
            "/// description\n"
            "function update\n",
            source="foo.bloc"
        )
        assert spec is not None
        assert spec.name == "foo"
        assert spec.description == " test block\n with long\n description"

    def test_misplaced_description(self, capsys):
        spec = parse_bloc_string(
            "/// test block\n"
            "function update\n"
            "/// misplaced\n",
            source="foo.bloc"
        )
        actual = capsys.readouterr().err.strip()
        expected = "foo.bloc:3: error: misplaced description"
        assert actual == expected
        assert spec is None

    def test_misplaced_description_2(self, capsys):
        spec = parse_bloc_string(
            "/// test block\n"
            "function update\n"
            "/// misplaced\n"
            "function f2\n",
            source="foo.bloc"
        )
        actual = capsys.readouterr().err.strip()
        expected = "foo.bloc:3: error: misplaced description"
        assert actual == expected
        assert spec is None

    def test_unterminated_if(self, capsys):
        spec = parse_bloc_string(
            "/// test block\n"
            "#if 1\n"
            "function update",
            source="foo.bloc"
        )
        actual = capsys.readouterr().err.strip()
        expected = "foo.bloc: error: end-of-file with 1 unterminated '#if' statements"
        assert actual == expected
        assert spec is None




# ---------------------------------------------------------------------------
# parse_param tests
# ---------------------------------------------------------------------------

class TestParseParam:

    def test_u32_param_with_min_max_and_description(self):
        spec = parse_bloc_string(
            "/// test block\n"
            "param u32 NCHAN default=2 min=1 max=8 /// number of channels\n"
            "function update\n"
        )
        assert spec is not None
        assert len(spec.params) == 1
        p = spec.params[0]
        assert p.name == "NCHAN"
        assert p.param_type == "u32"
        assert p.default == 2
        assert p.min_val == 1
        assert p.max_val == 8
        assert p.description == " number of channels"

    def test_bool_param_default_min_max(self):
        spec = parse_bloc_string(
            "/// test block\n"
            "param bool HAS_ENABLE default=1\n"
            "function update\n"
        )
        assert spec is not None
        assert len(spec.params) == 1
        p = spec.params[0]
        assert p.name == "HAS_ENABLE"
        assert p.param_type == "bool"
        assert p.default == 1
        assert p.min_val == 0
        assert p.max_val == U32_MAX
        assert p.description == ""

    def test_too_few_tokens(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param u32 N\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:1: error: 'param' requires name, type, and default=value"
        assert actual == expected
        assert spec is None

    def test_invalid_type(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param float N default=1\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:7: error: invalid parameter type 'float'; expected 'bool' or 'u32'"
        assert actual == expected
        assert spec is None

    def test_invalid_name(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param u32 1bad default=1\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:11: error: invalid parameter name: '1bad'"
        assert actual == expected
        assert spec is None

    def test_duplicate_name(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param u32 N default=1\n"
            "param u32 N default=2\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:3:11: error: duplicate parameter name: 'N'"
        assert actual == expected
        assert spec is None

    def test_unexpected_token(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param u32 N default=1 foo\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:23: error: unexpected token 'foo'; expected 'default=', 'min=', or 'max='"
        assert actual == expected
        assert spec is None

    def test_missing_value_after_equals(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param u32 N default=\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:13: error: missing value after 'default='"
        assert actual == expected
        assert spec is None

    def test_bad_expression(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param u32 N default=1+\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:13: error: bad default: expression '1+': invalid syntax"
        assert actual == expected
        assert spec is None

    def test_u32_out_of_range_high(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param u32 N default=0xFFFFFFFF1\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:13: error: default value 68719476721 is out of range for u32 [0, 4294967295]"
        assert actual == expected
        assert spec is None

    def test_u32_out_of_range_negative(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param u32 N default=-1\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:13: error: default value -1 is out of range for u32 [0, 4294967295]"
        assert actual == expected
        assert spec is None

    def test_bool_value_not_0_or_1_warning(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param bool N default=2\n"
            "function update\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:14: warning: default value 2 is not 0 or 1 for bool parameter"
        assert actual == expected
        assert spec is not None

    def test_duplicate_default_token(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param u32 N default=1 default=2\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:23: error: duplicate 'default=' token"
        assert actual == expected
        assert spec is None

    def test_missing_default(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param u32 N min=1 max=2\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2: error: 'param' requires a 'default=' value"
        assert actual == expected
        assert spec is None

    def test_bool_min_not_meaningful_warning(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param bool N default=1 min=1\n"
            "function update\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2: warning: 'min' is not meaningful for bool parameters"
        assert actual == expected
        assert spec is not None

    def test_bool_max_not_meaningful_warning(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param bool N default=0 max=1\n"
            "function update\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2: warning: 'max' is not meaningful for bool parameters"
        assert actual == expected
        assert spec is not None

    def test_min_greater_than_max(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param u32 N default=5 min=10 max=2\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2: error: min (10) is greater than max (2)"
        assert actual == expected
        assert spec is None

    def test_default_less_than_min(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param u32 N default=1 min=5 max=10\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2: error: default (1) is less than min (5)"
        assert actual == expected
        assert spec is None

    def test_default_greater_than_max(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param u32 N default=20 min=1 max=10\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2: error: default (20) is greater than max (10)"
        assert actual == expected
        assert spec is None

# ---------------------------------------------------------------------------
# parse_include tests
# ---------------------------------------------------------------------------

class TestParseInclude:

    def test_angle_bracket_include(self):
        spec = parse_bloc_string(
            "/// a block\n"
            "include <mylib.h>\n"
            "function update\n"
        )
        assert spec is not None
        assert spec.includes == ["<mylib.h>"]

    def test_quoted_include(self):
        spec = parse_bloc_string(
            '/// a block\n'
            'include "mylib.h"\n'
            'function update\n'
        )
        assert spec is not None
        assert spec.includes == ['"mylib.h"']

    def test_missing_filename(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "include\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:1: error: 'include' requires include filename"
        assert actual == expected
        assert spec is None

    def test_invalid_path_no_delimiters(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "include mylib.h\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:9: error: invalid include path: 'mylib.h'"
        assert actual == expected
        assert spec is None

    def test_invalid_path_mismatched_delimiters(self, capsys):
        spec = parse_bloc_string(
            '/// a block\n'
            'include <mylib.h"\n'
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:9: error: invalid include path: '<mylib.h\"'"
        assert actual == expected
        assert spec is None

    def test_invalid_path_too_short(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "include <>\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:9: error: invalid include path: '<>'"
        assert actual == expected
        assert spec is None

# ---------------------------------------------------------------------------
# parse_pin tests
# ---------------------------------------------------------------------------

class TestParsePin:

    def test_scalar_pin(self):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin float input in /// the input\n"
            "function update\n"
        )
        assert spec is not None
        pin = spec.statements[0].statement
        assert pin.name_template == "in"
        assert pin.field_name == "in_"
        assert pin.dedup_name == "in_"
        assert pin.pin_type == PinType.FLOAT
        assert pin.direction == PinDir.INPUT
        assert pin.dims == []
        assert pin.export_condition is None
        assert pin.description == " the input"

    def test_1d_array_pin(self):
        spec = parse_bloc_string(
            "/// a block\n"
            "param u32 NUM_CHAN default=2 min=1 max=8\n"
            "pin raw output ch{i:2}_out[i=NUM_CHAN] /// mux output\n"
            "function update\n"
        )
        assert spec is not None
        pin = spec.statements[0].statement
        assert pin.name_template == "ch{i:2}_out"
        assert pin.field_name == "ch00_out_"
        assert pin.dedup_name == "ch00_out_"
        assert pin.pin_type == PinType.RAW
        assert pin.direction == PinDir.OUTPUT
        assert pin.dims == [DimSpec(size_expr="NUM_CHAN", index_var="i")]
        assert pin.export_condition is None
        assert pin.description == " mux output"

    def test_2d_array_pin(self):
        spec = parse_bloc_string(
            "/// a block\n"
            "param u32 NUM_CHAN default=2 min=1 max=8\n"
            "param u32 NUM_INPUT default=2 min=2 max=10\n"
            "pin raw input ch{c:2}_in{i:1}[i=NUM_INPUT][c=NUM_CHAN] /// mux input\n"
            "function update\n"
        )
        assert spec is not None
        pin = spec.statements[0].statement
        assert pin.name_template == "ch{c:2}_in{i:1}"
        assert pin.field_name == "ch00_in0_"
        assert pin.dedup_name == "ch00_in0_"
        assert pin.pin_type == PinType.RAW
        assert pin.direction == PinDir.INPUT
        assert pin.dims == [
            DimSpec(size_expr="NUM_INPUT", index_var="i"),
            DimSpec(size_expr="NUM_CHAN", index_var="c"),
        ]
        assert pin.export_condition is None
        assert pin.description == " mux input"

    def test_1d_array_pin_with_export_condition(self):
        spec = parse_bloc_string(
            "/// a block\n"
            "param u32 NUM_CHAN default=4 min=1 max=8\n"
            "pin raw output ch{i:2}_out[i=NUM_CHAN] if i&1 /// odd channels only\n"
            "function update\n"
        )
        assert spec is not None
        pin = spec.statements[0].statement
        assert pin.name_template == "ch{i:2}_out"
        assert pin.field_name == "ch00_out_"
        assert pin.dedup_name == "ch00_out_"
        assert pin.pin_type == PinType.RAW
        assert pin.direction == PinDir.OUTPUT
        assert pin.dims == [DimSpec(size_expr="NUM_CHAN", index_var="i")]
        assert pin.export_condition == "i&1"
        assert pin.description == " odd channels only"

    def test_wrong_token_count_too_few(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin float input\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2: error: 'pin' declaration must have 4 or 6 tokens, got 3"
        assert actual == expected
        assert spec is None

    def test_wrong_token_count_five(self, capsys):
        # any 5-token pin declaration is rejected outright -- whether it's
        # "if" with no condition, a condition with no "if", or anything
        # else, the count check fires before either is examined
        spec = parse_bloc_string(
            "/// a block\n"
            "pin float input in if\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2: error: 'pin' declaration must have 4 or 6 tokens, got 5"
        assert actual == expected
        assert spec is None

    def test_wrong_token_count_too_many(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin float input in if x extra\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2: error: 'pin' declaration must have 4 or 6 tokens, got 7"
        assert actual == expected
        assert spec is None

    def test_unknown_pin_type(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin double input in\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:5: error: unknown pin type 'double'; expected one of ['bool', 'u32', 's32', 'float', 'raw']"
        assert actual == expected
        assert spec is None

    def test_unknown_pin_direction(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin float sideways in\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:11: error: unknown pin direction 'sideways'; expected 'input' or 'output'"
        assert actual == expected
        assert spec is None

    def test_empty_template(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin raw output [i=4] /// bad\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:16: error: pin name/template cannot be empty"
        assert actual == expected
        assert spec is None

    def test_dimension_missing_closing_bracket(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin raw output ch{i:2}_out[i=4 /// bad\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:16: error: missing closing ']' in dimension 'i=4'"
        assert actual == expected
        assert spec is None

    def test_dimension_missing_equals(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin raw output ch{i:2}_out[i4] /// bad\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:16: error: missing '=' in dimension 'i4'"
        assert actual == expected
        assert spec is None

    def test_dimension_invalid_index_variable(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin raw output ch{i:2}_out[1i=4] /// bad\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:16: error: invalid index variable '1i'"
        assert actual == expected
        assert spec is None

    def test_dimension_duplicate_index_variable(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin raw output ch{i:2}_in{j:1}[i=4][i=4] /// bad\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:16: error: index variable name 'i' already in use"
        assert actual == expected
        assert spec is None

    def test_dimension_index_variable_collides_with_param(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param u32 NCHAN default=2 min=1 max=8\n"
            "pin raw output ch{i:2}_out[NCHAN=4] /// bad\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:3:16: error: index variable name 'NCHAN' already in use"
        assert actual == expected
        assert spec is None

    def test_dimension_missing_size(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin raw output ch{i:2}_out[i=] /// bad\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:16: error: missing size in dimension 'i='"
        assert actual == expected
        assert spec is None

    def test_dimension_invalid_expression(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin raw output ch{i:2}_out[i=1+] /// bad\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:16: error: invalid dimension: expression '1+': invalid syntax"
        assert actual == expected
        assert spec is None

    def test_dimension_size_less_than_one(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin raw output ch{i:2}_out[i=0] /// bad\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:16: error: invalid dimension: 0; must be at least 1"
        assert actual == expected
        assert spec is None

    def test_malformed_template_specifier(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin raw output ch{i:10}_out /// bad\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:16: error: malformed template specifier in 'ch{i:10}_out'; expected {expr:N} where N is 1-9"
        assert actual == expected
        assert spec is None

    def test_invalid_field_name(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin float output 1out /// bad\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:18: error: template '1out' produces invalid field name '1out_'"
        assert actual == expected
        assert spec is None

    def test_duplicate_name_in_namespace(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin float input in /// first\n"
            "pin float output in /// dup\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:3:18: error: duplicate name 'in_' in block namespace"
        assert actual == expected
        assert spec is None

    def test_invalid_template_expression(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin raw output ch{BADVAR:2}_out /// bad\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:16: error: invalid template: expression 'BADVAR': unknown variable: 'BADVAR'"
        assert actual == expected
        assert spec is None

    def test_expected_if_keyword(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin float input in foo bar /// bad\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:20: error: expected 'if', got 'foo'"
        assert actual == expected
        assert spec is None

    def test_invalid_if_condition_expression(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin float input in if BADVAR /// bad\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:23: error: invalid 'if' condition: expression 'BADVAR': unknown variable: 'BADVAR'"
        assert actual == expected
        assert spec is None

# ---------------------------------------------------------------------------
# parse_var tests
# ---------------------------------------------------------------------------

class TestParseVar:

    def test_simple_var(self):
        spec = parse_bloc_string(
            "/// a block\n"
            "var float accumulated; // PID integrator state\n"
            "function update\n"
        )
        assert spec is not None
        var = spec.statements[0].statement
        assert var.field_name == "accumulated"
        assert var.dedup_name == "accumulated"
        assert var.c_decl == "float accumulated;"

    def test_pointer_var(self):
        spec = parse_bloc_string(
            "/// a block\n"
            "var GPIO_TypeDef *base_addr;\n"
            "function update\n"
        )
        assert spec is not None
        var = spec.statements[0].statement
        assert var.field_name == "base_addr"
        assert var.dedup_name == "base_addr"
        assert var.c_decl == "GPIO_TypeDef *base_addr;"

    def test_array_var(self):
        spec = parse_bloc_string(
            "/// a block\n"
            "var float history[4];\n"
            "function update\n"
        )
        assert spec is not None
        var = spec.statements[0].statement
        assert var.field_name == "history"
        assert var.dedup_name == "history"
        assert var.c_decl == "float history[4];"

    def test_too_few_tokens(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "var\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:1: error: 'var' statement requires a C declaration"
        assert actual == expected
        assert spec is None

    def test_missing_semicolon(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "var float acc\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:11: error: 'var' declaration must end with a semicolon"
        assert actual == expected
        assert spec is None

    def test_invalid_field_name(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "var float 123abc;\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:11: error: could not extract valid field name from 'var' declaration; got '123abc'"
        assert actual == expected
        assert spec is None

    def test_duplicate_name_in_namespace(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "var float acc;\n"
            "var u32 acc;\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:3:9: error: duplicate name 'acc' in block namespace"
        assert actual == expected
        assert spec is None

    def test_duplicate_name_collides_with_pin(self, capsys):
        # pin field names get a trailing '_', so a var must be declared
        # with a matching trailing underscore to collide
        spec = parse_bloc_string(
            "/// a block\n"
            "pin float input acc /// the accumulator pin\n"
            "var float acc_;\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:3:11: error: duplicate name 'acc_' in block namespace"
        assert actual == expected
        assert spec is None

# ---------------------------------------------------------------------------
# parse_function tests
# ---------------------------------------------------------------------------

class TestParseFunction:

    def test_happy_path(self):
        spec = parse_bloc_string(
            "/// a block\n"
            "function update /// the update function\n"
        )
        assert spec is not None
        func = spec.statements[0].statement
        assert func.name == "update"
        assert func.dedup_name == "update_"
        assert func.description == " the update function"

    def test_too_many_tokens(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "function update extra\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:1: error: 'function' declaration should be 'function <name>'"
        assert actual == expected
        assert spec is None

    def test_too_few_tokens(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "function\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:1: error: 'function' declaration should be 'function <name>'"
        assert actual == expected
        assert spec is None

    def test_invalid_function_name(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "function 1update\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:10: error: invalid function name: '1update'"
        assert actual == expected
        assert spec is None

    def test_duplicate_name_collides_with_pin(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "pin float input update /// a pin\n"
            "function update\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:3:10: error: duplicate name 'update' in block namespace"
        assert actual == expected
        assert spec is None

# ---------------------------------------------------------------------------
# parse_statement tests
# ---------------------------------------------------------------------------

class TestParseStatement:

    def test_unexpected_keyword_in_section(self, capsys):
        # 'param' is only legal in the PARAMS section; once a 'pin'
        # statement has moved parsing into BODY, 'param' is rejected
        spec = parse_bloc_string(
            "/// a block\n"
            "pin float input in\n"
            "param u32 N default=1\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:3:1: error: unexpected keyword 'param' in current section"
        assert actual == expected
        assert spec is None

    def test_if_requires_expression(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param bool HAS_ENABLE default=0\n"
            "#if\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:3:1: error: '#if' requires an expression"
        assert actual == expected
        assert spec is None

    def test_bad_if_condition(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param bool HAS_ENABLE default=0\n"
            "#if BADVAR\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:3:5: error: bad #if condition: expression 'BADVAR': unknown variable: 'BADVAR'"
        assert actual == expected
        assert spec is None

    def test_if_endif_condition_scoping(self):
        spec = parse_bloc_string(
            "/// a block\n"
            "param bool HAS_ENABLE default=0\n"
            "#if HAS_ENABLE\n"
            "pin bool input enable /// enable pin\n"
            "#endif\n"
            "function update\n"
        )
        assert spec is not None
        assert len(spec.statements) == 2
        pin_stmt, func_stmt = spec.statements
        assert pin_stmt.conditions == ["HAS_ENABLE"]
        assert func_stmt.conditions == []

    def test_endif_extra_tokens_warning(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "param bool HAS_ENABLE default=0\n"
            "#if HAS_ENABLE\n"
            "pin bool input enable\n"
            "#endif extra\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:5:8: warning: '#endif' takes no arguments"
        assert actual == expected
        assert spec is not None

    def test_endif_without_matching_if(self, capsys):
        spec = parse_bloc_string(
            "/// a block\n"
            "#endif\n"
        )
        actual = capsys.readouterr().err.strip()
        expected = "<string>:2:1: error: '#endif' without matching '#if'"
        assert actual == expected
        assert spec is None

# ---------------------------------------------------------------------------
# parse_bloc_file / parse_bloc_string wrapper tests
# ---------------------------------------------------------------------------

class TestParseBlocFile:

    def test_file_not_found(self, bad_dir, capsys):
        path = bad_dir / "does_not_exist.bloc"
        rel = path.as_posix()
        spec = parse_bloc_file(str(path))
        actual = capsys.readouterr().err.strip()
        expected = (
            f"{rel}: error: file not found\n"
            f"{rel}: 1 error(s), 0 warning(s), 0 info(s)"
        )
        assert actual == expected
        assert spec is None

    def test_successful_clean_parse(self, good_dir, capsys):
        spec = parse_bloc_file(str(good_dir / "simple.bloc"))
        actual = capsys.readouterr().err.strip()
        assert actual == ""
        assert spec is not None
        assert spec.name == "simple"

    def test_successful_parse_with_warning(self, bad_dir, capsys):
        path = bad_dir / "with_warning.bloc"
        rel = path.as_posix()
        spec = parse_bloc_file(str(path))
        actual = capsys.readouterr().err.strip()
        expected = (
            f"{rel}:2:17: warning: default value 2 is not 0 or 1 for bool parameter\n"
            f"{rel}: 0 error(s), 1 warning(s), 0 info(s)"
        )
        assert actual == expected
        assert spec is not None
        assert spec.name == "with_warning"


class TestParseBlocStringEncoding:

    def test_non_ascii_string(self, capsys):
        spec = parse_bloc_string("bl\u00e9oc foo\n")
        actual = capsys.readouterr().err.strip()
        expected = "<string>:1: error: non-ASCII character"
        assert actual == expected
        assert spec is None
