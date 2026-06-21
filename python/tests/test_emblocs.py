# tests/test_emblocs.py
# Tests for the EMBLOCS object model (emblocs.py)
# Focuses on Design methods: add_block_def, add_block_instance,
# add_signal, add_thread, and link/unlink operations.

from __future__ import annotations
import pytest
from pathlib import Path
from emblocs import (
    Design,
    BlockSpec, ParamSpec, DimSpec, PinSpec, FunctSpec, Statement,
    BlockDef, FieldDef, PinDef, FunctDef, VarDef,
    BlockInstance, Signal, Thread,
    PinType, PinDir,
    EmblocsError,
)
import emblocs  # for module level vars: recurse and descr_prefix


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_design():
    return Design(abs_path="test.blocs")


@pytest.fixture
def minimal_block_def():
    """A BlockDef with no pins, vars, or functions."""
    return BlockDef(
        name                 = "limit1",
        abs_path             = "limit1.bloc",
        orig_path            = "limit1.bloc",
        description          = "test block",
        params               = {},
        includes             = {},
        pins                 = {},
        functions            = {},
        namespace            = {},
        ordered_fields       = [],
    )

@pytest.fixture
def minimal_block_spec():
    """A BlockSpec with no params, includes, or statements."""
    return BlockSpec(
        abs_path = "test.bloc",
        name     = "myblock",
    )

@pytest.fixture
def another_block_def():
    """A second BlockDef for testing namespace conflicts."""
    return BlockDef(
        name                 = "mux",
        abs_path             = "mux.bloc",
        orig_path            = "mux.bloc",
        description          = "another test block",
        params               = {},
        includes             = {},
        pins                 = {},
        functions            = {},
        namespace            = {},
        ordered_fields       = [],
    )


# ---------------------------------------------------------------------------
# add_block_def tests
# ---------------------------------------------------------------------------

class TestAddBlockDef:

    def test_adds_to_block_defs(self, empty_design, minimal_block_def):
        empty_design.add_block_def(minimal_block_def)
        assert "limit1" in empty_design.block_defs

    def test_stores_correct_block_def(self, empty_design, minimal_block_def):
        empty_design.add_block_def(minimal_block_def)
        assert empty_design.block_defs["limit1"] is minimal_block_def

    def test_adds_to_namespace(self, empty_design, minimal_block_def):
        empty_design.add_block_def(minimal_block_def)
        assert "limit1" in empty_design.namespace

    def test_two_block_defs(self, empty_design, minimal_block_def,
                            another_block_def):
        empty_design.add_block_def(minimal_block_def)
        empty_design.add_block_def(another_block_def)
        assert "limit1" in empty_design.block_defs
        assert "mux" in empty_design.block_defs
        assert len(empty_design.block_defs) == 2

    def test_duplicate_name_raises(self, empty_design, minimal_block_def):
        empty_design.add_block_def(minimal_block_def)
        with pytest.raises(EmblocsError):
            empty_design.add_block_def(minimal_block_def)

    def test_duplicate_name_exact_message(self, empty_design, minimal_block_def):
        empty_design.add_block_def(minimal_block_def)
        with pytest.raises(EmblocsError) as exc:
            empty_design.add_block_def(minimal_block_def)
        actual = str(exc.value)
        expected = "name 'limit1' is already in use"
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )

    def test_name_conflict_with_signal(self, empty_design, minimal_block_def):
        """block_def name conflicts with a pre-existing namespace entry."""
        empty_design.namespace["limit1"] = None
        with pytest.raises(EmblocsError):
            empty_design.add_block_def(minimal_block_def)

# ---------------------------------------------------------------------------
# add_block_spec tests
# ---------------------------------------------------------------------------

class TestAddBlockSpec:

    def test_add_new_spec(self, empty_design, minimal_block_spec):
        result = empty_design.add_block_spec(minimal_block_spec)
        assert result is minimal_block_spec
        assert "myblock" in empty_design.block_specs
        assert empty_design.block_specs["myblock"] is minimal_block_spec

    def test_add_same_object_again(self, empty_design, minimal_block_spec):
        empty_design.add_block_spec(minimal_block_spec)
        result = empty_design.add_block_spec(minimal_block_spec)
        assert result is minimal_block_spec
        assert len(empty_design.block_specs) == 1
        assert empty_design.block_specs["myblock"] is minimal_block_spec

    def test_different_object_same_name_raises(self, empty_design, minimal_block_spec):
        duplicate = BlockSpec(abs_path="other.bloc", name="myblock")
        empty_design.add_block_spec(minimal_block_spec)
        with pytest.raises(EmblocsError) as exc:
            empty_design.add_block_spec(duplicate)
        assert str(exc.value) == "duplicate block spec name 'myblock'"
        assert empty_design.block_specs["myblock"] is minimal_block_spec
        assert len(empty_design.block_specs) == 1


# ---------------------------------------------------------------------------
# Fixtures for add_block_instance tests
# ---------------------------------------------------------------------------

@pytest.fixture
def design_with_limit1(empty_design, minimal_block_def):
    """A Design with limit1 BlockDef already added."""
    empty_design.add_block_def(minimal_block_def)
    return empty_design


@pytest.fixture
def block_def_with_pins():
    """A BlockDef with one input pin and one function."""
    in_field = FieldDef(
        name      = "in_",
        dims      = (),
        pin_type  = PinType.FLOAT,
        direction = PinDir.INPUT,
        c_decl    = None,
    )
    in_pin = PinDef(
        name         = "in",
        field        = in_field,
        field_indices = (),
    )
    update_func = FunctDef(
        name        = "update",
        description = "update function",
    )
    return BlockDef(
        name                 = "simple",
        abs_path             = "simple.bloc",
        orig_path            = "simple.bloc",
        description          = "block with pins",
        params               = {},
        includes             = {},
        pins                 = {"in": in_pin},
        functions            = {"update": update_func},
        namespace            = {"in": in_pin, "update": update_func},
        ordered_fields       = [in_field],
    )


@pytest.fixture
def design_with_simple(empty_design, block_def_with_pins):
    """A Design with simple BlockDef already added."""
    empty_design.add_block_def(block_def_with_pins)
    return empty_design


# ---------------------------------------------------------------------------
# add_block_instance tests
# ---------------------------------------------------------------------------

class TestAddBlockInstance:

    def test_adds_to_blocks(self, design_with_limit1):
        design_with_limit1.add_block_instance("lim1", "limit1")
        assert "lim1" in design_with_limit1.blocks

    def test_adds_to_namespace(self, design_with_limit1):
        design_with_limit1.add_block_instance("lim1", "limit1")
        assert "lim1" in design_with_limit1.namespace

    def test_instance_references_correct_block_def(self, design_with_limit1,
                                                    minimal_block_def):
        design_with_limit1.add_block_instance("lim1", "limit1")
        assert design_with_limit1.blocks["lim1"].block_def is minimal_block_def

    def test_instance_has_correct_name(self, design_with_limit1):
        design_with_limit1.add_block_instance("lim1", "limit1")
        assert design_with_limit1.blocks["lim1"].name == "lim1"

    def test_pins_populated_from_block_def(self, design_with_simple,
                                            block_def_with_pins):
        design_with_simple.add_block_instance("s1", "simple")
        instance = design_with_simple.blocks["s1"]
        assert "in" in instance.pins
        assert instance.pins["in"].pin_def is block_def_with_pins.pins["in"]

    def test_functions_populated_from_block_def(self, design_with_simple,
                                                 block_def_with_pins):
        design_with_simple.add_block_instance("s1", "simple")
        instance = design_with_simple.blocks["s1"]
        assert "update" in instance.functions
        assert instance.functions["update"].funct_def is block_def_with_pins.functions["update"]

    def test_pin_initially_unconnected(self, design_with_simple):
        design_with_simple.add_block_instance("s1", "simple")
        pin = design_with_simple.blocks["s1"].pins["in"]
        assert pin.signal is not None
        assert pin.signal.is_dummy

    def test_dummy_signal_created_for_pin(self, design_with_simple):
        design_with_simple.add_block_instance("s1", "simple")
        assert "dsig_s1_in" in design_with_simple.dummy_signals

    def test_dummy_signal_correct_type(self, design_with_simple):
        design_with_simple.add_block_instance("s1", "simple")
        dummy = design_with_simple.dummy_signals["dsig_s1_in"]
        assert dummy.sig_type == PinType.FLOAT

    def test_pin_back_reference(self, design_with_simple):
        design_with_simple.add_block_instance("s1", "simple")
        instance = design_with_simple.blocks["s1"]
        assert instance.pins["in"].block is instance

    def test_function_back_reference(self, design_with_simple):
        design_with_simple.add_block_instance("s1", "simple")
        instance = design_with_simple.blocks["s1"]
        assert instance.functions["update"].block is instance

    def test_function_initially_unassigned(self, design_with_simple):
        design_with_simple.add_block_instance("s1", "simple")
        assert design_with_simple.blocks["s1"].functions["update"].thread is None

    def test_duplicate_instance_name_raises(self, design_with_limit1):
        design_with_limit1.add_block_instance("lim1", "limit1")
        with pytest.raises(EmblocsError) as exc:
            design_with_limit1.add_block_instance("lim1", "limit1")
        assert str(exc.value) == "name 'lim1' is already in use"

    def test_unknown_block_def_raises(self, empty_design):
        with pytest.raises(EmblocsError) as exc:
            empty_design.add_block_instance("lim1", "nonexistent")
        assert str(exc.value) == "unknown block definition 'nonexistent'"

    def test_name_conflict_with_block_def(self, design_with_limit1):
        """Instance name conflicts with an existing BlockDef name."""
        with pytest.raises(EmblocsError):
            design_with_limit1.add_block_instance("limit1", "limit1")

    def test_two_instances_of_same_block_def(self, design_with_limit1):
        design_with_limit1.add_block_instance("lim1", "limit1")
        design_with_limit1.add_block_instance("lim2", "limit1")
        assert "lim1" in design_with_limit1.blocks
        assert "lim2" in design_with_limit1.blocks
        assert design_with_limit1.blocks["lim1"] is not design_with_limit1.blocks["lim2"]

# ---------------------------------------------------------------------------
# add_signal tests
# ---------------------------------------------------------------------------

class TestAddSignal:

    def test_adds_to_signals(self, empty_design):
        empty_design.add_signal("vel", PinType.FLOAT)
        assert "vel" in empty_design.signals

    def test_adds_to_namespace(self, empty_design):
        empty_design.add_signal("vel", PinType.FLOAT)
        assert "vel" in empty_design.namespace

    def test_returns_signal(self, empty_design):
        result = empty_design.add_signal("vel", PinType.FLOAT)
        assert isinstance(result, Signal)

    def test_returned_signal_has_correct_name(self, empty_design):
        result = empty_design.add_signal("vel", PinType.FLOAT)
        assert result.name == "vel"

    def test_returned_signal_has_correct_type(self, empty_design):
        result = empty_design.add_signal("vel", PinType.FLOAT)
        assert result.sig_type == PinType.FLOAT

    def test_signal_initially_has_no_driver(self, empty_design):
        result = empty_design.add_signal("vel", PinType.FLOAT)
        assert result.driver is None

    def test_signal_initially_has_no_readers(self, empty_design):
        result = empty_design.add_signal("vel", PinType.FLOAT)
        assert result.readers == []

    def test_all_valid_types(self, empty_design):
        for sig_type, name in [(PinType.BOOL,  "b"),
                                (PinType.U32,   "u"),
                                (PinType.S32,   "s"),
                                (PinType.FLOAT, "f")]:
            sig = empty_design.add_signal(name, sig_type)
            assert sig.sig_type == sig_type

    def test_raw_type_raises(self, empty_design):
        with pytest.raises(EmblocsError) as exc:
            empty_design.add_signal("r", PinType.RAW)
        assert str(exc.value) == "invalid signal type 'RAW'"

    def test_duplicate_name_raises(self, empty_design):
        empty_design.add_signal("vel", PinType.FLOAT)
        with pytest.raises(EmblocsError) as exc:
            empty_design.add_signal("vel", PinType.FLOAT)
        assert str(exc.value) == "name 'vel' is already in use"

    def test_name_conflict_with_block_def(self, empty_design, minimal_block_def):
        empty_design.add_block_def(minimal_block_def)
        with pytest.raises(EmblocsError):
            empty_design.add_signal("limit1", PinType.FLOAT)

    def test_default_value_bool(self, empty_design):
        sig = empty_design.add_signal("b", PinType.BOOL)
        assert sig.value == 0

    def test_default_value_float(self, empty_design):
        sig = empty_design.add_signal("f", PinType.FLOAT)
        assert sig.value == 0

# ---------------------------------------------------------------------------
# add_thread tests
# ---------------------------------------------------------------------------

class TestAddThread:

    def test_adds_to_threads(self, empty_design):
        empty_design.add_thread("fast", 1000000)
        assert "fast" in empty_design.threads

    def test_adds_to_namespace(self, empty_design):
        empty_design.add_thread("fast", 1000000)
        assert "fast" in empty_design.namespace

    def test_returns_thread(self, empty_design):
        result = empty_design.add_thread("fast", 1000000)
        assert isinstance(result, Thread)

    def test_returned_thread_has_correct_name(self, empty_design):
        result = empty_design.add_thread("fast", 1000000)
        assert result.name == "fast"

    def test_returned_thread_has_correct_period(self, empty_design):
        result = empty_design.add_thread("fast", 1000000)
        assert result.period_ns == 1000000

    def test_thread_initially_has_no_functions(self, empty_design):
        result = empty_design.add_thread("fast", 1000000)
        assert result.functions == []

    def test_duplicate_name_raises(self, empty_design):
        empty_design.add_thread("fast", 1000000)
        with pytest.raises(EmblocsError) as exc:
            empty_design.add_thread("fast", 2000000)
        assert str(exc.value) == "name 'fast' is already in use"

    def test_name_conflict_with_signal(self, empty_design):
        empty_design.add_signal("fast", PinType.FLOAT)
        with pytest.raises(EmblocsError):
            empty_design.add_thread("fast", 1000000)

    def test_zero_period_raises(self, empty_design):
        with pytest.raises(EmblocsError) as exc:
            empty_design.add_thread("fast", 0)
        assert str(exc.value) == "thread period must be positive, got 0"

    def test_negative_period_raises(self, empty_design):
        with pytest.raises(EmblocsError) as exc:
            empty_design.add_thread("fast", -1000000)
        assert str(exc.value) == "thread period must be positive, got -1000000"

    def test_two_threads(self, empty_design):
        empty_design.add_thread("fast", 1000000)
        empty_design.add_thread("slow", 10000000)
        assert len(empty_design.threads) == 2

# ---------------------------------------------------------------------------
# Fixtures for link/unlink tests
# ---------------------------------------------------------------------------

@pytest.fixture
def block_def_with_output():
    """A BlockDef with one output float pin."""
    out_field = FieldDef(
        name      = "out_",
        dims      = (),
        pin_type  = PinType.FLOAT,
        direction = PinDir.OUTPUT,
        c_decl    = None,
    )
    out_pin = PinDef(
        name         = "out",
        field        = out_field,
        field_indices = (),
    )
    return BlockDef(
        name                 = "source",
        abs_path             = "source.bloc",
        orig_path            = "source.bloc",
        description          = "block with output pin",
        params               = {},
        includes             = {},
        pins                 = {"out": out_pin},
        functions            = {},
        namespace            = {"out": out_pin},
        ordered_fields       = [out_field],
    )


@pytest.fixture
def block_def_with_raw():
    """A BlockDef with one raw input pin."""
    raw_field = FieldDef(
        name      = "raw_in_",
        dims      = (),
        pin_type  = PinType.RAW,
        direction = PinDir.INPUT,
        c_decl    = None,
    )
    raw_pin = PinDef(
        name         = "raw_in",
        field        = raw_field,
        field_indices = (),
    )
    return BlockDef(
        name                 = "passthrough",
        abs_path             = "passthrough.bloc",
        orig_path            = "passthrough.bloc",
        description          = "block with raw pin",
        params               = {},
        includes             = {},
        pins                 = {"raw_in": raw_pin},
        functions            = {},
        namespace            = {"raw_in": raw_pin},
        ordered_fields       = [raw_field],
    )


@pytest.fixture
def linked_design(empty_design, block_def_with_pins,
                  block_def_with_output):
    """
    A Design with:
      - 'simple' BlockDef (has input pin 'in', function 'update')
      - 'source' BlockDef (has output pin 'out')
      - instances 'src' and 's1'
      - float signal 'vel'
    """
    empty_design.add_block_def(block_def_with_pins)
    empty_design.add_block_def(block_def_with_output)
    empty_design.add_block_instance("src", "source")
    empty_design.add_block_instance("s1", "simple")
    empty_design.add_block_instance("s2", "simple")
    empty_design.add_signal("vel", PinType.FLOAT)
    empty_design.add_signal("b", PinType.BOOL)
    empty_design.add_thread("fast", 1000000)
    empty_design.add_thread("slow", 100000000)
    return empty_design


# ---------------------------------------------------------------------------
# link_by_name tests
# ---------------------------------------------------------------------------

class TestLinkPin:

    def test_link_input_pin(self, linked_design):
        linked_design.link_by_name("s1.in", "vel")
        assert linked_design.blocks["s1"].pins["in"].signal is linked_design.signals["vel"]

    def test_link_input_adds_to_readers(self, linked_design):
        linked_design.link_by_name("s1.in", "vel")
        assert linked_design.blocks["s1"].pins["in"] in linked_design.signals["vel"].readers

    def test_link_input_no_driver(self, linked_design):
        linked_design.link_by_name("s1.in", "vel")
        assert linked_design.signals["vel"].driver is None

    def test_link_output_pin(self, linked_design):
        linked_design.link_by_name("src.out", "vel")
        assert linked_design.blocks["src"].pins["out"].signal is linked_design.signals["vel"]

    def test_link_output_sets_driver(self, linked_design):
        linked_design.link_by_name("src.out", "vel")
        assert linked_design.signals["vel"].driver is linked_design.blocks["src"].pins["out"]

    def test_link_output_no_readers(self, linked_design):
        linked_design.link_by_name("src.out", "vel")
        assert linked_design.signals["vel"].readers == []

    def test_link_reversed_pin_signal(self, linked_design):
        linked_design.link_by_name("vel", "s1.in")
        assert linked_design.blocks["s1"].pins["in"].signal is linked_design.signals["vel"]

    def test_link_input_and_output(self, linked_design):
        linked_design.link_by_name("src.out", "vel")
        linked_design.link_by_name("s1.in", "vel")
        assert linked_design.signals["vel"].driver is linked_design.blocks["src"].pins["out"]
        assert linked_design.blocks["s1"].pins["in"] in linked_design.signals["vel"].readers

    def test_multiple_inputs(self, linked_design, block_def_with_pins):
        linked_design.link_by_name("s1.in", "vel")
        linked_design.link_by_name("s2.in", "vel")
        assert len(linked_design.signals["vel"].readers) == 2

    def test_raw_pin_accepts_any_type(self, empty_design, block_def_with_raw):
        empty_design.add_block_def(block_def_with_raw)
        empty_design.add_block_instance("p1", "passthrough")
        empty_design.add_signal("u", PinType.U32)
        empty_design.link_by_name("p1.raw_in", "u")
        assert empty_design.blocks["p1"].pins["raw_in"].signal is empty_design.signals["u"]

    def test_unknown_block_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.link_by_name("nonexistent.in", "vel")
        assert str(exc.value) == "block 'nonexistent' not found"

    def test_unknown_pin_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.link_by_name("s1.nonexistent", "vel")
        assert str(exc.value) == "'nonexistent' not found in block 's1'"

    def test_unknown_signal_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.link_by_name("s1.in", "nonexistent")
        assert str(exc.value) == "'nonexistent' not found in design"

    def test_already_connected_raises(self, linked_design):
        linked_design.link_by_name("s1.in", "vel")
        with pytest.raises(EmblocsError) as exc:
            linked_design.link_by_name("s1.in", "vel")
        assert str(exc.value) == "cannot link 's1.in' to 'vel': pin 's1.in' is already connected to signal 'vel'"

    def test_type_mismatch_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.link_by_name("s1.in", "b")
        assert str(exc.value) == "cannot link 's1.in' to 'b': type mismatch: pin 's1.in' is FLOAT but signal 'b' is BOOL"

    def test_second_driver_raises(self, linked_design, block_def_with_output):
        linked_design.add_block_instance("src2", "source")
        linked_design.link_by_name("src.out", "vel")
        with pytest.raises(EmblocsError) as exc:
            linked_design.link_by_name("src2.out", "vel")
        assert str(exc.value) == "cannot link 'src2.out' to 'vel': signal 'vel' already has driver 'src.out'"

class TestLinkFunction:

    def test_link_function(self, linked_design):
        linked_design.link_by_name("s1.update", "fast")
        func = linked_design.blocks["s1"].functions["update"]
        assert func.thread is linked_design.threads["fast"]

    def test_link_adds_to_thread(self, linked_design):
        linked_design.link_by_name("s1.update", "fast")
        func = linked_design.blocks["s1"].functions["update"]
        assert func in linked_design.threads["fast"].functions

    def test_link_preserves_order(self, linked_design):
        linked_design.link_by_name("s1.update", "fast")
        linked_design.link_by_name("s2.update", "fast")
        funcs = linked_design.threads["fast"].functions
        assert funcs[0] is linked_design.blocks["s1"].functions["update"]
        assert funcs[1] is linked_design.blocks["s2"].functions["update"]

    def test_link_reversed_function_thread(self, linked_design):
        linked_design.link_by_name("fast", "s1.update")
        func = linked_design.blocks["s1"].functions["update"]
        assert func.thread is linked_design.threads["fast"]

    def test_two_functions_different_threads(self, linked_design):
        linked_design.link_by_name("s1.update", "fast")
        linked_design.link_by_name("s2.update", "slow")
        assert linked_design.blocks["s1"].functions["update"].thread is linked_design.threads["fast"]
        assert linked_design.blocks["s2"].functions["update"].thread is linked_design.threads["slow"]

    def test_unknown_block_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.link_by_name("nonexistent.update", "fast")
        assert str(exc.value) == "block 'nonexistent' not found"

    def test_unknown_function_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.link_by_name("s1.nonexistent", "fast")
        assert str(exc.value) == "'nonexistent' not found in block 's1'"

    def test_unknown_thread_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.link_by_name("s1.update", "nonexistent")
        assert str(exc.value) == "'nonexistent' not found in design"

    def test_already_assigned_raises(self, linked_design):
        linked_design.link_by_name("s1.update", "fast")
        with pytest.raises(EmblocsError) as exc:
            linked_design.link_by_name("s1.update", "slow")
        assert str(exc.value) == "cannot link 's1.update' to 'slow': function 's1.update' is already assigned to thread 'fast'"

    def test_link_incompatible_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.link_by_name("s1.update", "vel")
        assert str(exc.value) == "cannot link 's1.update' to 'vel': cannot link FunctInstance to Signal"

    def test_link_unknown_second_arg_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.link_by_name("s1.in", "nonexistent")
        assert str(exc.value) == "'nonexistent' not found in design"


# ---------------------------------------------------------------------------
# unlink_by_name tests
# ---------------------------------------------------------------------------

class TestUnlinkPin:

    def test_unlink_input_pin(self, linked_design):
        linked_design.link_by_name("s1.in", "vel")
        linked_design.unlink_by_name("s1.in")
        assert linked_design.blocks["s1"].pins["in"].signal.is_dummy

    def test_unlink_input_removes_from_readers(self, linked_design):
        linked_design.link_by_name("s1.in", "vel")
        linked_design.unlink_by_name("s1.in")
        assert linked_design.blocks["s1"].pins["in"] not in linked_design.signals["vel"].readers

    def test_unlink_output_pin(self, linked_design):
        linked_design.link_by_name("src.out", "vel")
        linked_design.unlink_by_name("src.out")
        assert linked_design.blocks["src"].pins["out"].signal.is_dummy

    def test_unlink_output_clears_driver(self, linked_design):
        linked_design.link_by_name("src.out", "vel")
        linked_design.unlink_by_name("src.out")
        assert linked_design.signals["vel"].driver is None

    def test_unlink_unconnected_is_noop(self, linked_design):
        linked_design.unlink_by_name("s1.in")
        assert linked_design.blocks["s1"].pins["in"].signal.is_dummy

    def test_unlink_preserves_value(self, linked_design):
        linked_design.link_by_name("src.out", "vel")
        linked_design.signals["vel"].value = 3.14
        linked_design.unlink_by_name("src.out")
        dummy = linked_design.dummy_signals["dsig_src_out"]
        assert dummy.value == 3.14

    def test_unlink_restores_dummy(self, linked_design):
        linked_design.link_by_name("s1.in", "vel")
        linked_design.unlink_by_name("s1.in")
        assert linked_design.blocks["s1"].pins["in"].signal.is_dummy

    def test_unknown_block_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.unlink_by_name("nonexistent.in")
        assert str(exc.value) == "block 'nonexistent' not found"

    def test_unknown_pin_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.unlink_by_name("s1.nonexistent")
        assert str(exc.value) == "'nonexistent' not found in block 's1'"

class TestUnlinkFunction:

    def test_unlink_function(self, linked_design):
        linked_design.link_by_name("s1.update", "fast")
        linked_design.unlink_by_name("s1.update")
        assert linked_design.blocks["s1"].functions["update"].thread is None

    def test_unlink_removes_from_thread(self, linked_design):
        linked_design.link_by_name("s1.update", "fast")
        linked_design.unlink_by_name("s1.update")
        assert linked_design.blocks["s1"].functions["update"] not in \
               linked_design.threads["fast"].functions

    def test_unlink_unassigned_is_noop(self, linked_design):
        linked_design.unlink_by_name("s1.update")
        assert linked_design.blocks["s1"].functions["update"].thread is None

    def test_unlink_middle_of_thread(self, linked_design):
        linked_design.link_by_name("s1.update", "fast")
        linked_design.link_by_name("s2.update", "fast")
        linked_design.unlink_by_name("s1.update")
        funcs = linked_design.threads["fast"].functions
        assert len(funcs) == 1
        assert funcs[0] is linked_design.blocks["s2"].functions["update"]

    def test_unknown_block_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.unlink_by_name("nonexistent.update")
        assert str(exc.value) == "block 'nonexistent' not found"

    def test_unknown_function_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.unlink_by_name("s1.nonexistent")
        assert str(exc.value) == "'nonexistent' not found in block 's1'"

    def test_unlink_signal_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.unlink_by_name("vel")
        assert str(exc.value) == "cannot unlink 'vel': cannot unlink Signal"

    def test_unlink_block_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.unlink_by_name("s1")
        assert str(exc.value) == "cannot unlink 's1': cannot unlink BlockInstance"

# ---------------------------------------------------------------------------
# set_value_by_name tests
# ---------------------------------------------------------------------------

@pytest.fixture
def design_with_signals(empty_design):
    empty_design.add_signal("b", PinType.BOOL)
    empty_design.add_signal("u", PinType.U32)
    empty_design.add_signal("s", PinType.S32)
    empty_design.add_signal("f", PinType.FLOAT)
    return empty_design


class TestSetSignalValue:

    def test_set_bool_zero(self, design_with_signals):
        design_with_signals.set_value_by_name("b", 0)
        assert design_with_signals.signals["b"].value == 0

    def test_set_bool_one(self, design_with_signals):
        design_with_signals.set_value_by_name("b", 1)
        assert design_with_signals.signals["b"].value == 1

    def test_set_bool_nonzero_normalizes_to_one(self, design_with_signals):
        design_with_signals.set_value_by_name("b", 2)
        assert design_with_signals.signals["b"].value == 1

    def test_set_bool_true_converts_to_int(self, design_with_signals):
        design_with_signals.set_value_by_name("b", True)
        assert design_with_signals.signals["b"].value == 1
        assert isinstance(design_with_signals.signals["b"].value, int)

    def test_set_bool_invalid_raises(self, design_with_signals):
        with pytest.raises(EmblocsError) as exc:
            design_with_signals.set_value_by_name("b", 1.5)
        assert str(exc.value) == "cannot set value of 'b': value 1.5 is not valid for bool"

    def test_set_u32_zero(self, design_with_signals):
        design_with_signals.set_value_by_name("u", 0)
        assert design_with_signals.signals["u"].value == 0

    def test_set_u32_max(self, design_with_signals):
        design_with_signals.set_value_by_name("u", 0xFFFFFFFF)
        assert design_with_signals.signals["u"].value == 0xFFFFFFFF

    def test_set_u32_negative_raises(self, design_with_signals):
        with pytest.raises(EmblocsError) as exc:
            design_with_signals.set_value_by_name("u", -1)
        assert str(exc.value) == "cannot set value of 'u': value -1 is out of range for u32"

    def test_set_u32_overflow_raises(self, design_with_signals):
        with pytest.raises(EmblocsError) as exc:
            design_with_signals.set_value_by_name("u", 0x100000000)
        assert str(exc.value) == "cannot set value of 'u': value 4294967296 is out of range for u32"

    def test_set_s32_zero(self, design_with_signals):
        design_with_signals.set_value_by_name("s", 0)
        assert design_with_signals.signals["s"].value == 0

    def test_set_s32_min(self, design_with_signals):
        design_with_signals.set_value_by_name("s", -0x80000000)
        assert design_with_signals.signals["s"].value == -0x80000000

    def test_set_s32_max(self, design_with_signals):
        design_with_signals.set_value_by_name("s", 0x7FFFFFFF)
        assert design_with_signals.signals["s"].value == 0x7FFFFFFF

    def test_set_s32_overflow_raises(self, design_with_signals):
        with pytest.raises(EmblocsError) as exc:
            design_with_signals.set_value_by_name("s", 0x80000000)
        assert str(exc.value) == "cannot set value of 's': value 2147483648 is out of range for s32"

    def test_set_s32_underflow_raises(self, design_with_signals):
        with pytest.raises(EmblocsError) as exc:
            design_with_signals.set_value_by_name("s", -0x80000001)
        assert str(exc.value) == "cannot set value of 's': value -2147483649 is out of range for s32"

    def test_set_float(self, design_with_signals):
        design_with_signals.set_value_by_name("f", 1.5)
        assert design_with_signals.signals["f"].value == 1.5

    def test_set_float_from_int(self, design_with_signals):
        design_with_signals.set_value_by_name("f", 1)
        assert design_with_signals.signals["f"].value == 1.0
        assert isinstance(design_with_signals.signals["f"].value, float)

    def test_set_float_invalid_raises(self, design_with_signals):
        with pytest.raises(EmblocsError) as exc:
            design_with_signals.set_value_by_name("f", "oops")
        assert str(exc.value) == "cannot set value of 'f': value 'oops' is not valid for float"

    def test_unknown_signal_raises(self, design_with_signals):
        with pytest.raises(EmblocsError) as exc:
            design_with_signals.set_value_by_name("nonexistent", 0)
        assert str(exc.value) == "'nonexistent' not found in design"

    def test_driven_signal_raises(self, design_with_signals, block_def_with_pins):
        design_with_signals.add_block_def(block_def_with_pins)
        design_with_signals.add_block_instance("s1", "simple")
        instance = design_with_signals.blocks["s1"]
        design_with_signals.signals["f"].driver = instance.pins["in"]
        with pytest.raises(EmblocsError) as exc:
            design_with_signals.set_value_by_name("f", 1.0)
        assert str(exc.value) == "cannot set value of 'f': signal 'f' is driven by 's1.in'; cannot set value directly"

class TestSetPinValue:

    def test_set_unconnected_pin(self, linked_design):
        linked_design.set_value_by_name("s1.in", 1.5)
        dummy = linked_design.dummy_signals["dsig_s1_in"]
        assert dummy.value == 1.5

    def test_set_connected_pin_raises(self, linked_design):
        linked_design.link_by_name("s1.in", "vel")
        with pytest.raises(EmblocsError) as exc:
            linked_design.set_value_by_name("s1.in", 1.5)
        assert str(exc.value) == "cannot set value of 's1.in': pin 's1.in' is connected to signal 'vel'; cannot set value directly"

    def test_unknown_block_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.set_value_by_name("nonexistent.in", 1.5)
        assert str(exc.value) == "block 'nonexistent' not found"

    def test_unknown_pin_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.set_value_by_name("s1.nonexistent", 1.5)
        assert str(exc.value) == "'nonexistent' not found in block 's1'"

    def test_type_validation(self, linked_design):
        """set_pin_value rejects values incompatible with the pin type."""
        with pytest.raises(EmblocsError):
            linked_design.set_value_by_name("s1.in", "not_a_number")

# ---------------------------------------------------------------------------
# set_value on invalid object type
# ---------------------------------------------------------------------------

class TestSetValueInvalidType:

    def test_set_value_on_thread_raises(self, empty_design):
        thread = empty_design.add_thread("fast", 1000000)
        with pytest.raises(EmblocsError) as exc:
            empty_design.set_value(thread, 0)
        assert str(exc.value) == "cannot set value on object of type Thread"


# ---------------------------------------------------------------------------
# __str__ tests
# ---------------------------------------------------------------------------

@pytest.fixture
def no_recurse():
    emblocs.recurse = False
    yield
    emblocs.recurse = True


class TestFormatDescr:

    def test_empty_string(self):
        expected = ""
        assert emblocs._format_descr("") == expected

    def test_nonempty_string(self):
        expected = "\n  # hello world"
        assert emblocs._format_descr("hello world") == expected


class TestIndentChild:

    def test_single_line(self):
        expected = "  foo"
        assert emblocs._indent_child("foo") == expected

    def test_multiline(self):
        expected = "  foo\n  bar"
        assert emblocs._indent_child("foo\nbar") == expected


class TestParamSpecStr:

    def test_no_min_max_no_desc(self):
        p = ParamSpec(name='N', param_type='u32', default=1)
        expected = "param  N  u32  default=1"
        assert str(p) == expected

    def test_with_description(self):
        p = ParamSpec(name='N', param_type='u32', default=1,
                      description='num channels')
        expected = "param  N  u32  default=1\n  # num channels"
        assert str(p) == expected

    def test_with_min_and_max(self):
        p = ParamSpec(name='N', param_type='u32', default=1,
                      min_val=2, max_val=10)
        expected = "param  N  u32  default=1  min=2  max=10"
        assert str(p) == expected

    def test_with_max_only(self):
        p = ParamSpec(name='N', param_type='u32', default=1, max_val=10)
        expected = "param  N  u32  default=1  max=10"
        assert str(p) == expected


class TestDimSpecStr:

    def test_basic(self):
        d = DimSpec(size_expr='NUM_CHAN', index_var='i')
        expected = "dim  [i=NUM_CHAN]"
        assert str(d) == expected


class TestPinSpecStr:

    def test_scalar_no_desc(self):
        ps = PinSpec(name_template='in', field_name='in_', dedup_name='in_',
                     pin_type=PinType.FLOAT, direction=PinDir.INPUT, dims=[])
        expected = "pin  FLOAT  INPUT   'in' -> in_ (scalar)"
        assert str(ps) == expected

    def test_scalar_with_desc(self):
        ps = PinSpec(name_template='in', field_name='in_', dedup_name='in_',
                     pin_type=PinType.FLOAT, direction=PinDir.INPUT, dims=[],
                     description='the input')
        expected = "pin  FLOAT  INPUT   'in' -> in_ (scalar)\n  # the input"
        assert str(ps) == expected

    def test_array_with_condition(self):
        ps = PinSpec(name_template='ch{i:2}_out', field_name='ch00_out_',
                     dedup_name='ch00_out_', pin_type=PinType.RAW,
                     direction=PinDir.OUTPUT,
                     dims=[DimSpec('NUM_CHAN', 'i')],
                     export_condition='i!=1')
        expected = "pin  RAW    OUTPUT  'ch{i:2}_out' -> ch00_out_ ([i=NUM_CHAN])  if i!=1"
        assert str(ps) == expected


class TestVarDefStr:

    def test_basic(self):
        v = VarDef(field_name='acc', dedup_name='acc', c_decl='float acc;')
        expected = "var acc:  float acc;"
        assert str(v) == expected


class TestFunctSpecStr:

    def test_no_desc(self):
        fs = FunctSpec(name='update', dedup_name='update_')
        expected = "function  update"
        assert str(fs) == expected

    def test_with_desc(self):
        fs = FunctSpec(name='update', dedup_name='update_',
                       description='does stuff')
        expected = "function  update\n  # does stuff"
        assert str(fs) == expected


class TestStatementStr:

    def test_no_conditions(self):
        fs = FunctSpec(name='update', dedup_name='update_')
        stmt = Statement(conditions=[], statement=fs)
        expected = "function  update"
        assert str(stmt) == expected

    def test_one_condition(self):
        fs = FunctSpec(name='update', dedup_name='update_')
        stmt = Statement(conditions=['HAS_ENABLE'], statement=fs)
        expected = "(if: HAS_ENABLE): function  update"
        assert str(stmt) == expected

    def test_two_conditions(self):
        fs = FunctSpec(name='update', dedup_name='update_',
                       description='does stuff')
        stmt = Statement(conditions=['HAS_ENABLE', 'HAS_HOLD'], statement=fs)
        expected = (
            "(if: HAS_ENABLE && HAS_HOLD): function  update\n"
            "  # does stuff")
        assert str(stmt) == expected


class TestBlockSpecStr:

    def test_minimal(self):
        bs = BlockSpec(abs_path='test.bloc', name='myblock')
        expected = "BlockSpec: myblock  (test.bloc)"
        assert str(bs) == expected

    def test_with_description_param_include_statement(self):
        bs = BlockSpec(abs_path='test.bloc', name='myblock',
                       description='a block')
        bs.params.append(ParamSpec(name='N', param_type='u32', default=1))
        bs.includes.append('"myheader.h"')
        bs.statements.append(
            Statement(conditions=[],
                      statement=FunctSpec(name='update', dedup_name='update_')))
        expected = (
            'BlockSpec: myblock  (test.bloc)\n'
            '  # a block\n'
            '  param  N  u32  default=1\n'
            '  include "myheader.h"\n'
            '  function  update')
        assert str(bs) == expected

class TestFieldDefStr:

    def test_var_field(self):
        fd = FieldDef(name='acc', dims=(), pin_type=None, direction=None,
                      c_decl='float acc;')
        expected = "field  var   float acc;"
        assert str(fd) == expected

    def test_scalar_pin_field(self):
        fd = FieldDef(name='out_', dims=(), pin_type=PinType.FLOAT,
                      direction=PinDir.OUTPUT, c_decl=None)
        expected = "field  FLOAT  OUTPUT  out_"
        assert str(fd) == expected

    def test_array_pin_field(self):
        fd = FieldDef(name='ch00_out_', dims=(3,), pin_type=PinType.FLOAT,
                      direction=PinDir.OUTPUT, c_decl=None)
        expected = "field  FLOAT  OUTPUT  ch00_out_[3]"
        assert str(fd) == expected


class TestPinDefStr:

    def test_scalar_no_desc(self):
        in_field = FieldDef(name='in_', dims=(), pin_type=PinType.FLOAT,
                            direction=PinDir.INPUT, c_decl=None)
        pd = PinDef(name='in', field=in_field)
        expected = "pin  FLOAT  INPUT   in -> in_"
        assert str(pd) == expected

    def test_scalar_with_desc(self):
        in_field = FieldDef(name='in_', dims=(), pin_type=PinType.FLOAT,
                            direction=PinDir.INPUT, c_decl=None)
        pd = PinDef(name='in', field=in_field, description='the input')
        expected = (
            "pin  FLOAT  INPUT   in -> in_\n"
            "  # the input")
        assert str(pd) == expected

    def test_array_with_indices(self):
        arr_field = FieldDef(name='ch00_out_', dims=(3,), pin_type=PinType.FLOAT,
                             direction=PinDir.OUTPUT, c_decl=None)
        pd = PinDef(name='ch01_out', field=arr_field, field_indices=(1,))
        expected = "pin  FLOAT  OUTPUT  ch01_out -> ch00_out_[1]"
        assert str(pd) == expected


class TestFunctDefStr:

    def test_no_desc(self):
        fd = FunctDef(name='update')
        expected = "function  update"
        assert str(fd) == expected

    def test_with_desc(self):
        fd = FunctDef(name='update', description='runs every cycle')
        expected = (
            "function  update\n"
            "  # runs every cycle")
        assert str(fd) == expected


class TestBlockDefStr:

    def test_full(self, block_def_with_pins):
        expected = (
            "BlockDef: simple  \n"
            "  # block with pins\n"
            "  abs_path:  simple.bloc\n"
            "  orig_path: simple.bloc\n"
            "  field  FLOAT  INPUT   in_\n"
            "  pin  FLOAT  INPUT   in -> in_\n"
            "  function  update\n"
            "    # update function")
        assert str(block_def_with_pins) == expected

class TestSignalStr:

    def test_no_driver_no_readers(self, linked_design):
        expected = "signal  vel  FLOAT  value=0  driver=none"
        assert str(linked_design.signals['vel']) == expected

    def test_with_driver(self, linked_design):
        linked_design.link_by_name('src.out', 'vel')
        expected = "signal  vel  FLOAT  value=0  driver=src.out"
        assert str(linked_design.signals['vel']) == expected

    def test_with_reader(self, linked_design):
        linked_design.link_by_name('s1.in', 'vel')
        expected = (
            "signal  vel  FLOAT  value=0  driver=none\n"
            "  reader  s1.in")
        assert str(linked_design.signals['vel']) == expected


class TestThreadStr:

    def test_empty_thread(self, linked_design):
        expected = "thread  fast  (1000000 ns)"
        assert str(linked_design.threads['fast']) == expected

    def test_with_function(self, linked_design):
        linked_design.link_by_name('s1.update', 'fast')
        expected = (
            "thread  fast  (1000000 ns)\n"
            "  s1.update")
        assert str(linked_design.threads['fast']) == expected


class TestPinInstanceStr:

    def test_unconnected(self, linked_design):
        expected = "pin  s1.in -> dsig_s1_in"
        assert str(linked_design.blocks['s1'].pins['in']) == expected

    def test_connected(self, linked_design):
        linked_design.link_by_name('s1.in', 'vel')
        expected = "pin  s1.in -> vel"
        assert str(linked_design.blocks['s1'].pins['in']) == expected


class TestFunctInstanceStr:

    def test_unassigned(self, linked_design):
        expected = "function  s1.update -> unassigned"
        assert str(linked_design.blocks['s1'].functions['update']) == expected

    def test_assigned(self, linked_design):
        linked_design.link_by_name('s1.update', 'fast')
        expected = "function  s1.update -> fast"
        assert str(linked_design.blocks['s1'].functions['update']) == expected


class TestBlockInstanceStr:

    def test_basic(self, linked_design):
        expected = (
            "block  s1 (simple)\n"
            "  pin  s1.in -> dsig_s1_in\n"
            "  function  s1.update -> unassigned")
        assert str(linked_design.blocks['s1']) == expected


class TestDesignStr:

    def test_no_recurse_empty(self, no_recurse):
        d = Design(abs_path='test.blocs')
        expected = "Design: test.blocs"
        assert str(d) == expected

    def test_no_recurse_populated(self, no_recurse, linked_design):
        expected = (
            "Design: test.blocs\n"
            "  blockdef  simple\n"
            "  blockdef  source\n"
            "  block  src (source)\n"
            "  block  s1 (simple)\n"
            "  block  s2 (simple)\n"
            "  signal  vel  FLOAT\n"
            "  signal  b  BOOL\n"
            "  thread  fast  1000000 ns\n"
            "  thread  slow  100000000 ns")
        assert str(linked_design) == expected

    def test_no_recurse_with_block_spec(self, no_recurse, linked_design,
                                        minimal_block_spec):
        linked_design.add_block_spec(minimal_block_spec)
        expected = (
            "Design: test.blocs\n"
            "  blockspec  myblock\n"
            "  blockdef  simple\n"
            "  blockdef  source\n"
            "  block  src (source)\n"
            "  block  s1 (simple)\n"
            "  block  s2 (simple)\n"
            "  signal  vel  FLOAT\n"
            "  signal  b  BOOL\n"
            "  thread  fast  1000000 ns\n"
            "  thread  slow  100000000 ns")
        assert str(linked_design) == expected

    def test_recurse_populated(self, linked_design):
        # just verify that recursion happens - child content should appear
        result = str(linked_design)
        assert 'BlockDef:' in result
        assert 'block  s1' in result
        assert 'signal  vel' in result
        assert 'thread  fast' in result

class TestDesignSearchPaths:
    """Tests for Design.search_paths field"""

    def test_search_paths_initially_empty(self):
        design = Design(abs_path="test")
        assert design.search_paths == []

    def test_search_paths_can_append(self):
        design = Design(abs_path="test")
        p = Path("/some/path")
        design.search_paths.append(p)
        assert design.search_paths == [p]
        assert len(design.search_paths) == 1

    def test_search_paths_in_str(self):
        design = Design(abs_path="test")
        design.search_paths.append(Path("/some/path"))
        result = str(design)
        assert "search  /some/path" in result
