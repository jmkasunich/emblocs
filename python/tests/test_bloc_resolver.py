# tests/test_bloc_resolver.py
# Tests for bloc_resolver.py

from __future__ import annotations
import pytest
from parse_common import ctx
from emblocs import BlockSpec, ParamSpec, PinType, PinDir
from bloc_parser import parse_bloc_string
from bloc_resolver import _build_variables, resolve


@pytest.fixture(autouse=True)
def clean_context():
    ctx.clear()
    ctx.push(source="<test>")
    yield
    ctx.clear()


# ---------------------------------------------------------------------------
# _build_variables tests
#
# Tested in isolation via hand-built BlockSpec(params=[...]) objects --
# _build_variables only needs spec.params and an active ctx.
# ---------------------------------------------------------------------------

class TestBuildVariables:

    def test_all_defaults(self):
        spec = BlockSpec(abs_path="test.bloc", name="foo", params=[
            ParamSpec(name="N", param_type="u32", default=2, min_val=1, max_val=8),
        ])
        variables = _build_variables(spec, {})
        assert variables == {"N": 2}

    def test_supplied_override(self):
        spec = BlockSpec(abs_path="test.bloc", name="foo", params=[
            ParamSpec(name="N", param_type="u32", default=2, min_val=1, max_val=8),
        ])
        variables = _build_variables(spec, {"N": 5})
        assert variables == {"N": 5}

    def test_bool_not_0_or_1_warning(self, capsys):
        spec = BlockSpec(abs_path="test.bloc", name="foo", params=[
            ParamSpec(name="FLAG", param_type="bool", default=0,
                      min_val=0, max_val=0xFFFFFFFF),
        ])
        variables = _build_variables(spec, {"FLAG": 2})
        actual = capsys.readouterr().err.strip()
        expected = "<test>:0: warning: parameter 'FLAG' is bool; value 2 is not 0 or 1"
        assert actual == expected
        assert variables == {"FLAG": 2}

    def test_u32_below_min(self, capsys):
        spec = BlockSpec(abs_path="test.bloc", name="foo", params=[
            ParamSpec(name="N", param_type="u32", default=2, min_val=1, max_val=8),
        ])
        variables = _build_variables(spec, {"N": 0})
        actual = capsys.readouterr().err.strip()
        expected = "<test>:0: error: parameter 'N' value 0 is less than min (1)"
        assert actual == expected
        assert variables is None

    def test_u32_above_max(self, capsys):
        spec = BlockSpec(abs_path="test.bloc", name="foo", params=[
            ParamSpec(name="N", param_type="u32", default=2, min_val=1, max_val=8),
        ])
        variables = _build_variables(spec, {"N": 100})
        actual = capsys.readouterr().err.strip()
        expected = "<test>:0: error: parameter 'N' value 100 is greater than max (8)"
        assert actual == expected
        assert variables is None

    def test_multiple_errors_all_reported(self, capsys):
        spec = BlockSpec(abs_path="test.bloc", name="foo", params=[
            ParamSpec(name="A", param_type="u32", default=2, min_val=1, max_val=8),
            ParamSpec(name="B", param_type="u32", default=2, min_val=1, max_val=8),
        ])
        variables = _build_variables(spec, {"A": 0, "B": 100})
        actual = capsys.readouterr().err.strip()
        expected = (
            "<test>:0: error: parameter 'A' value 0 is less than min (1)\n"
            "<test>:0: error: parameter 'B' value 100 is greater than max (8)"
        )
        assert actual == expected
        assert variables is None

    def test_one_valid_one_invalid(self, capsys):
        spec = BlockSpec(abs_path="test.bloc", name="foo", params=[
            ParamSpec(name="A", param_type="u32", default=2, min_val=1, max_val=8),
            ParamSpec(name="B", param_type="u32", default=2, min_val=1, max_val=8),
        ])
        variables = _build_variables(spec, {"A": 5, "B": 100})
        actual = capsys.readouterr().err.strip()
        expected = "<test>:0: error: parameter 'B' value 100 is greater than max (8)"
        assert actual == expected
        assert variables is None

# ---------------------------------------------------------------------------
# resolve() top-level tests
# ---------------------------------------------------------------------------

class TestResolveTopLevel:

    def test_invalid_variant_name(self, capsys):
        spec = parse_bloc_string("/// foo block\nfunction update\n")
        ctx.clear()
        ctx.push(source="<test>")
        block_def = resolve(spec, "1bad", "test.bloc")
        actual = capsys.readouterr().err.strip()
        expected = "<test>:0:0: error: invalid variant name '1bad'"
        assert actual == expected
        assert block_def is None

    def test_happy_path_field_mapping(self):
        spec = parse_bloc_string(
            "/// the foo block\n"
            "param u32 N default=2 min=1 max=8 /// channel count\n"
            "include <mylib.h>\n"
            "var float accumulator;\n"
            "pin float input in /// the input\n"
            "function update /// the update function\n"
        )
        assert spec is not None
        ctx.clear()
        ctx.push(source="<test>")
        block_def = resolve(spec, "foo_variant", "components/foo.bloc")
        assert block_def is not None
        assert block_def.name == "foo_variant"
        assert block_def.abs_path.endswith("<string>")
        assert block_def.orig_path == "components/foo.bloc"
        assert block_def.description == " the foo block"
        assert block_def.params == {"N": 2}
        assert block_def.includes == ["<mylib.h>"]
        assert [f.name for f in block_def.ordered_fields] == ["accumulator", "in_"]
        assert list(block_def.pins.keys()) == ["in"]
        assert list(block_def.functions.keys()) == ["update"]
        assert list(block_def.namespace.keys()) == ["in", "update"]

    def test_supplied_params_none_uses_defaults(self):
        spec = parse_bloc_string(
            "/// foo block\n"
            "param u32 N default=2 min=1 max=8\n"
            "function update\n"
        )
        assert spec is not None
        ctx.clear()
        ctx.push(source="<test>")
        block_def = resolve(spec, "foo_variant", "test.bloc", None)
        assert block_def is not None
        assert block_def.params == {"N": 2}

# ---------------------------------------------------------------------------
# scalar pin expansion tests
# ---------------------------------------------------------------------------

class TestExpandScalarPin:

    def test_scalar_pin(self):
        spec = parse_bloc_string(
            "/// foo block\n"
            "pin float input in /// the input\n"
            "function update\n"
        )
        assert spec is not None
        ctx.clear()
        ctx.push(source="<test>")
        block_def = resolve(spec, "foo_variant", "test.bloc")
        assert block_def is not None

        pin = block_def.pins["in"]
        assert pin.name == "in"
        assert pin.field_indices == ()
        assert pin.description == " the input"

        field = pin.field
        assert field.name == "in_"
        assert field.dims == ()
        assert field.pin_type == PinType.FLOAT
        assert field.direction == PinDir.INPUT
        assert field.c_decl is None

        # the pin's field is the same object that appears in ordered_fields,
        # representing one C struct field shared by the FieldDef and PinDef
        assert block_def.ordered_fields[0] is field

# ---------------------------------------------------------------------------
# array pin expansion tests
# ---------------------------------------------------------------------------

class TestExpandArrayPin:

    def test_1d_array_pin(self):
        spec = parse_bloc_string(
            "/// foo block\n"
            "param u32 NUM_CHAN default=2 min=1 max=8\n"
            "pin raw output ch{i:2}_out[i=NUM_CHAN] /// mux output\n"
            "function update\n"
        )
        assert spec is not None
        ctx.clear()
        ctx.push(source="<test>")
        block_def = resolve(spec, "foo_variant", "test.bloc", {"NUM_CHAN": 3})
        assert block_def is not None

        # dimension size comes from the supplied value, not the default
        field = block_def.ordered_fields[0]
        assert field.dims == (3,)

        assert sorted(block_def.pins.keys()) == ["ch00_out", "ch01_out", "ch02_out"]
        assert block_def.pins["ch00_out"].field_indices == (0,)
        assert block_def.pins["ch01_out"].field_indices == (1,)
        assert block_def.pins["ch02_out"].field_indices == (2,)

    def test_2d_array_pin(self):
        spec = parse_bloc_string(
            "/// foo block\n"
            "param u32 NUM_CHAN default=2 min=1 max=8\n"
            "param u32 NUM_INPUT default=2 min=2 max=10\n"
            "pin raw input ch{c:2}_in{i:1}[i=NUM_INPUT][c=NUM_CHAN] /// mux input\n"
            "function update\n"
        )
        assert spec is not None
        ctx.clear()
        ctx.push(source="<test>")
        block_def = resolve(spec, "foo_variant", "test.bloc",
                             {"NUM_CHAN": 2, "NUM_INPUT": 3})
        assert block_def is not None

        field = block_def.ordered_fields[0]
        assert field.dims == (3, 2)

        assert sorted(block_def.pins.keys()) == [
            "ch00_in0", "ch00_in1", "ch00_in2",
            "ch01_in0", "ch01_in1", "ch01_in2",
        ]
        # field_indices order follows pin_spec.dims (bracket declaration
        # order: [i=NUM_INPUT][c=NUM_CHAN]), i.e. (i, c) -- not the order
        # the index variables appear in the name template (c before i)
        assert block_def.pins["ch00_in1"].field_indices == (1, 0)
        assert block_def.pins["ch01_in2"].field_indices == (2, 1)

# ---------------------------------------------------------------------------
# export condition tests
#
# export_condition == None is already exercised by every test in
# TestExpandScalarPin and TestExpandArrayPin (all slots exported).
# ---------------------------------------------------------------------------

class TestExportCondition:

    def test_sparse_export_arithmetic_condition(self):
        spec = parse_bloc_string(
            "/// foo block\n"
            "param u32 NUM_CHAN default=4 min=1 max=8\n"
            "pin raw output ch{i:2}_out[i=NUM_CHAN] if i&1 /// odd channels only\n"
            "function update\n"
        )
        assert spec is not None
        ctx.clear()
        ctx.push(source="<test>")
        block_def = resolve(spec, "foo_variant", "test.bloc", {"NUM_CHAN": 4})
        assert block_def is not None

        # the struct field is fully allocated regardless of export
        assert block_def.ordered_fields[0].dims == (4,)
        # only odd-indexed slots are exported as EMBLOCS pins
        assert sorted(block_def.pins.keys()) == ["ch01_out", "ch03_out"]

    def test_sparse_export_bitmask_condition_uses_resolved_value(self):
        spec = parse_bloc_string(
            "/// foo block\n"
            "param u32 MASK default=0x0009\n"
            "pin bool input pin{i:2}_in[i=8] if (MASK>>i)&1 /// gpio inputs\n"
            "function update\n"
        )
        assert spec is not None
        ctx.clear()
        ctx.push(source="<test>")
        # supplied MASK=0x05 (bits 0,2), not the default 0x0009 (bits 0,3)
        block_def = resolve(spec, "foo_variant", "test.bloc", {"MASK": 0x05})
        assert block_def is not None

        assert block_def.ordered_fields[0].dims == (8,)
        assert sorted(block_def.pins.keys()) == ["pin00_in", "pin02_in"]

# ---------------------------------------------------------------------------
# #if condition tests
# ---------------------------------------------------------------------------

class TestIfCondition:

    def _resolve_with(self, spec, supplied):
        ctx.clear()
        ctx.push(source="<test>")
        return resolve(spec, "foo_variant", "test.bloc", supplied)

    def test_if_true_includes_statement(self):
        spec = parse_bloc_string(
            "/// foo block\n"
            "param bool HAS_ENABLE default=0\n"
            "#if HAS_ENABLE\n"
            "pin bool input enable /// enable pin\n"
            "#endif\n"
            "function update\n"
        )
        assert spec is not None
        block_def = self._resolve_with(spec, {"HAS_ENABLE": 1})
        assert block_def is not None
        assert sorted(block_def.pins.keys()) == ["enable"]
        assert [f.name for f in block_def.ordered_fields] == ["enable_"]
        assert sorted(block_def.namespace.keys()) == ["enable", "update"]

    def test_if_false_excludes_statement_entirely(self):
        spec = parse_bloc_string(
            "/// foo block\n"
            "param bool HAS_ENABLE default=0\n"
            "#if HAS_ENABLE\n"
            "pin bool input enable /// enable pin\n"
            "#endif\n"
            "function update\n"
        )
        assert spec is not None
        block_def = self._resolve_with(spec, {"HAS_ENABLE": 0})
        assert block_def is not None
        # unlike a false 'if' export condition (topic F), a false #if
        # means the field is never allocated at all
        assert block_def.pins == {}
        assert block_def.ordered_fields == []
        assert sorted(block_def.namespace.keys()) == ["update"]

    def test_nested_if_requires_all_true(self):
        spec = parse_bloc_string(
            "/// foo block\n"
            "param bool HAS_A default=0\n"
            "param bool HAS_B default=0\n"
            "#if HAS_A\n"
            "#if HAS_B\n"
            "pin bool input both /// requires both\n"
            "#endif\n"
            "#endif\n"
            "function update\n"
        )
        assert spec is not None

        block_def = self._resolve_with(spec, {"HAS_A": 1, "HAS_B": 1})
        assert sorted(block_def.pins.keys()) == ["both"]

        for combo in [(1, 0), (0, 1), (0, 0)]:
            block_def = self._resolve_with(
                spec, {"HAS_A": combo[0], "HAS_B": combo[1]})
            assert block_def.pins == {}, f"failed for HAS_A={combo[0]}, HAS_B={combo[1]}"

# ---------------------------------------------------------------------------
# value-dependent expression error tests
#
# These expressions are validated at parse time against spec.defaults, but
# resolve() evaluates them against the actual supplied parameter values --
# so an expression that's fine with the defaults can still fail here for a
# particular supplied value (e.g. division by a parameter that resolves to
# zero). Array sizes are kept at 1 so each test produces a single error line.
# ---------------------------------------------------------------------------

class TestValueDependentExpressionErrors:

    def _resolve_with(self, spec, supplied):
        ctx.clear()
        ctx.push(source="<test>")
        return resolve(spec, "foo_variant", "test.bloc", supplied)

    def test_dimension_size_error(self, capsys):
        spec = parse_bloc_string(
            "/// foo block\n"
            "param u32 DIVISOR default=1 min=0 max=10\n"
            "param u32 BASE default=4 min=1 max=20\n"
            "pin float input ch{i:1}[i=BASE/DIVISOR]\n"
            "function update\n"
        )
        assert spec is not None
        block_def = self._resolve_with(spec, {"DIVISOR": 0})
        actual = capsys.readouterr().err.strip()
        expected = ("<test>:0:0: error: dimension size error in pin 'ch{i:1}': "
                     "expression 'BASE/DIVISOR': operator 'Div': division by zero")
        assert actual == expected
        assert block_def is None

    def test_export_condition_error(self, capsys):
        spec = parse_bloc_string(
            "/// foo block\n"
            "param u32 DIVISOR default=1 min=0 max=4\n"
            "param u32 NUM_CHAN default=1 min=1 max=8\n"
            "pin raw output ch{i:1}_out[i=NUM_CHAN] if i/DIVISOR\n"
            "function update\n"
        )
        assert spec is not None
        block_def = self._resolve_with(spec, {"DIVISOR": 0})
        actual = capsys.readouterr().err.strip()
        expected = ("<test>:0:0: error: export condition error in pin 'ch{i:1}_out': "
                     "expression 'i/DIVISOR': operator 'Div': division by zero")
        assert actual == expected
        assert block_def is None

    def test_if_condition_error(self, capsys):
        spec = parse_bloc_string(
            "/// foo block\n"
            "param u32 DIVISOR default=1 min=0 max=4\n"
            "#if 1/DIVISOR\n"
            "pin bool input enable\n"
            "#endif\n"
            "function update\n"
        )
        assert spec is not None
        block_def = self._resolve_with(spec, {"DIVISOR": 0})
        actual = capsys.readouterr().err.strip()
        expected = ("<test>:0:0: error: condition expression error '1/DIVISOR': "
                     "expression '1/DIVISOR': operator 'Div': division by zero")
        assert actual == expected
        assert block_def is None

    def test_template_expression_error(self, capsys):
        spec = parse_bloc_string(
            "/// foo block\n"
            "param u32 DIVISOR default=1 min=0 max=4\n"
            "param u32 NUM_CHAN default=1 min=1 max=4\n"
            "pin raw output ch{i/DIVISOR:1}_out[i=NUM_CHAN]\n"
            "function update\n"
        )
        assert spec is not None
        block_def = self._resolve_with(spec, {"DIVISOR": 0})
        actual = capsys.readouterr().err.strip()
        expected = ("<test>:0:0: error: template expression error 'i/DIVISOR': "
                     "expression 'i/DIVISOR': operator 'Div': division by zero")
        assert actual == expected
        assert block_def is None

# ---------------------------------------------------------------------------
# duplicate-name-after-resolution tests
#
# Two array pins can have different field_names (passing the parse-time
# namespace check, which uses literal-zero field names) yet still produce
# overlapping EMBLOCS names for certain parameter values. E.g. a{i:1}[i=N]
# and a1{j:1}[j=N] both produce the name "a10" when N>=11.
# ---------------------------------------------------------------------------

class TestDuplicateNameAfterResolution:

    def _spec(self):
        spec = parse_bloc_string(
            "/// foo block\n"
            "param u32 N default=2 min=1 max=20\n"
            "pin float input a{i:1}[i=N]\n"
            "pin float input a1{j:1}[j=N]\n"
            "function update\n"
        )
        assert spec is not None
        # confirm the two pins have different field_names, i.e. this
        # spec passes bloc_parser's namespace check
        field_names = [stmt.statement.field_name for stmt in spec.statements
                        if hasattr(stmt.statement, "field_name")]
        assert field_names == ["a0_", "a10_"]
        return spec

    def test_collision_for_specific_param_value(self, capsys):
        spec = self._spec()
        ctx.clear()
        ctx.push(source="<test>")
        block_def = resolve(spec, "foo_variant", "test.bloc", {"N": 11})
        actual = capsys.readouterr().err.strip()
        expected = "<test>:0:0: error: duplicate name 'a10' after resolution"
        assert actual == expected
        assert block_def is None

    def test_no_collision_for_small_param_value(self):
        spec = self._spec()
        ctx.clear()
        ctx.push(source="<test>")
        block_def = resolve(spec, "foo_variant", "test.bloc", {"N": 2})
        assert block_def is not None
        assert sorted(block_def.pins.keys()) == ["a0", "a1", "a10", "a11"]

# ---------------------------------------------------------------------------
# resolve() propagation of _build_variables() failure
# ---------------------------------------------------------------------------

class TestResolvePropagatesParamValidation:

    def test_out_of_range_param_causes_resolve_to_return_none(self, capsys):
        spec = parse_bloc_string(
            "/// foo block\n"
            "param u32 N default=2 min=1 max=8\n"
            "function update\n"
        )
        assert spec is not None
        ctx.clear()
        ctx.push(source="<test>")
        block_def = resolve(spec, "foo_variant", "test.bloc", {"N": 100})
        actual = capsys.readouterr().err.strip()
        expected = "<test>:0: error: parameter 'N' value 100 is greater than max (8)"
        assert actual == expected
        assert block_def is None
