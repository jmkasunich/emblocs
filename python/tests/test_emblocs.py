# tests/test_emblocs.py
# Tests for the EMBLOCS object model (emblocs.py)
# Focuses on Design methods: add_block_def, add_block_instance,
# add_signal, add_thread, and link/unlink operations.

import pytest
from emblocs import (
    Design, BlockDef, BlockInstance, Signal, Thread,
    PinDef, FunctDef, VarDef,
    PinType, PinDir,
    EmblocsError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_design():
    return Design(source_path="test.blocs")


@pytest.fixture
def minimal_block_def():
    """A BlockDef with no pins, vars, or functions."""
    return BlockDef(
        name                 = "limit1",
        source_path          = "limit1.bloc",
        description          = "test block",
        params               = {},
        pins                 = {},
        functions            = {},
        namespace            = {},
        ordered_declarations = [],
    )


@pytest.fixture
def another_block_def():
    """A second BlockDef for testing namespace conflicts."""
    return BlockDef(
        name                 = "mux",
        source_path          = "mux.bloc",
        description          = "another test block",
        params               = {},
        pins                 = {},
        functions            = {},
        namespace            = {},
        ordered_declarations = [],
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
        empty_design.namespace.add("limit1")
        with pytest.raises(EmblocsError):
            empty_design.add_block_def(minimal_block_def)

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
    in_pin = PinDef(
        name         = "in",
        field_name   = "in_",
        pin_type     = PinType.FLOAT,
        direction    = PinDir.INPUT,
    )
    update_func = FunctDef(
        name        = "update",
        description = "update function",
    )
    return BlockDef(
        name                 = "simple",
        source_path          = "simple.bloc",
        description          = "block with pins",
        params               = {},
        pins                 = {"in": in_pin},
        functions            = {"update": update_func},
        namespace            = {"in": in_pin, "update": update_func},
        ordered_declarations = [in_pin, update_func],
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
        assert "__s1__in" in design_with_simple.dummy_signals

    def test_dummy_signal_correct_type(self, design_with_simple):
        design_with_simple.add_block_instance("s1", "simple")
        dummy = design_with_simple.dummy_signals["__s1__in"]
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
# set_signal_value tests
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
        design_with_signals.set_signal_value("b", 0)
        assert design_with_signals.signals["b"].value == 0

    def test_set_bool_one(self, design_with_signals):
        design_with_signals.set_signal_value("b", 1)
        assert design_with_signals.signals["b"].value == 1

    def test_set_bool_true_converts_to_int(self, design_with_signals):
        design_with_signals.set_signal_value("b", True)
        assert design_with_signals.signals["b"].value == 1
        assert isinstance(design_with_signals.signals["b"].value, int)

    def test_set_bool_invalid_raises(self, design_with_signals):
        with pytest.raises(EmblocsError) as exc:
            design_with_signals.set_signal_value("b", 2)
        assert str(exc.value) == "value 2 is not valid for bool signal 'b'"

    def test_set_u32_zero(self, design_with_signals):
        design_with_signals.set_signal_value("u", 0)
        assert design_with_signals.signals["u"].value == 0

    def test_set_u32_max(self, design_with_signals):
        design_with_signals.set_signal_value("u", 0xFFFFFFFF)
        assert design_with_signals.signals["u"].value == 0xFFFFFFFF

    def test_set_u32_negative_raises(self, design_with_signals):
        with pytest.raises(EmblocsError) as exc:
            design_with_signals.set_signal_value("u", -1)
        assert str(exc.value) == "value -1 is out of range for u32 signal 'u'"

    def test_set_u32_overflow_raises(self, design_with_signals):
        with pytest.raises(EmblocsError) as exc:
            design_with_signals.set_signal_value("u", 0x100000000)
        assert str(exc.value) == "value 4294967296 is out of range for u32 signal 'u'"

    def test_set_s32_zero(self, design_with_signals):
        design_with_signals.set_signal_value("s", 0)
        assert design_with_signals.signals["s"].value == 0

    def test_set_s32_min(self, design_with_signals):
        design_with_signals.set_signal_value("s", -0x80000000)
        assert design_with_signals.signals["s"].value == -0x80000000

    def test_set_s32_max(self, design_with_signals):
        design_with_signals.set_signal_value("s", 0x7FFFFFFF)
        assert design_with_signals.signals["s"].value == 0x7FFFFFFF

    def test_set_s32_overflow_raises(self, design_with_signals):
        with pytest.raises(EmblocsError) as exc:
            design_with_signals.set_signal_value("s", 0x80000000)
        assert str(exc.value) == "value 2147483648 is out of range for s32 signal 's'"

    def test_set_s32_underflow_raises(self, design_with_signals):
        with pytest.raises(EmblocsError) as exc:
            design_with_signals.set_signal_value("s", -0x80000001)
        assert str(exc.value) == "value -2147483649 is out of range for s32 signal 's'"

    def test_set_float(self, design_with_signals):
        design_with_signals.set_signal_value("f", 1.5)
        assert design_with_signals.signals["f"].value == 1.5

    def test_set_float_from_int(self, design_with_signals):
        design_with_signals.set_signal_value("f", 1)
        assert design_with_signals.signals["f"].value == 1.0
        assert isinstance(design_with_signals.signals["f"].value, float)

    def test_set_float_invalid_raises(self, design_with_signals):
        with pytest.raises(EmblocsError) as exc:
            design_with_signals.set_signal_value("f", "oops")
        assert str(exc.value) == "value 'oops' is not valid for float signal 'f'"

    def test_unknown_signal_raises(self, design_with_signals):
        with pytest.raises(EmblocsError) as exc:
            design_with_signals.set_signal_value("nonexistent", 0)
        assert str(exc.value) == "unknown signal 'nonexistent'"

    def test_driven_signal_raises(self, design_with_signals, block_def_with_pins):
        design_with_signals.add_block_def(block_def_with_pins)
        design_with_signals.add_block_instance("s1", "simple")
        instance = design_with_signals.blocks["s1"]
        design_with_signals.signals["f"].driver = instance.pins["in"]
        with pytest.raises(EmblocsError) as exc:
            design_with_signals.set_signal_value("f", 1.0)
        assert str(exc.value) == "signal 'f' is driven by 's1.in'; cannot set value directly"

# ---------------------------------------------------------------------------
# Fixtures for link/unlink tests
# ---------------------------------------------------------------------------

@pytest.fixture
def block_def_with_output():
    """A BlockDef with one output float pin."""
    out_pin = PinDef(
        name         = "out",
        field_name   = "out_",
        pin_type     = PinType.FLOAT,
        direction    = PinDir.OUTPUT,
    )
    return BlockDef(
        name                 = "source",
        source_path          = "source.bloc",
        description          = "block with output pin",
        params               = {},
        pins                 = {"out": out_pin},
        functions            = {},
        namespace            = {"out": out_pin},
        ordered_declarations = [out_pin],
    )


@pytest.fixture
def block_def_with_raw():
    """A BlockDef with one raw input pin."""
    raw_pin = PinDef(
        name         = "raw_in",
        field_name   = "raw_in_",
        pin_type     = PinType.RAW,
        direction    = PinDir.INPUT,
    )
    return BlockDef(
        name                 = "passthrough",
        source_path          = "passthrough.bloc",
        description          = "block with raw pin",
        params               = {},
        pins                 = {"raw_in": raw_pin},
        functions            = {},
        namespace            = {"raw_in": raw_pin},
        ordered_declarations = [raw_pin],
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
    empty_design.add_signal("vel", PinType.FLOAT)
    return empty_design


# ---------------------------------------------------------------------------
# link_pin tests
# ---------------------------------------------------------------------------

class TestLinkPin:

    def test_link_input_pin(self, linked_design):
        linked_design.link_pin("s1", "in", "vel")
        assert linked_design.blocks["s1"].pins["in"].signal is linked_design.signals["vel"]

    def test_link_input_adds_to_readers(self, linked_design):
        linked_design.link_pin("s1", "in", "vel")
        assert linked_design.blocks["s1"].pins["in"] in linked_design.signals["vel"].readers

    def test_link_input_no_driver(self, linked_design):
        linked_design.link_pin("s1", "in", "vel")
        assert linked_design.signals["vel"].driver is None

    def test_link_output_pin(self, linked_design):
        linked_design.link_pin("src", "out", "vel")
        assert linked_design.blocks["src"].pins["out"].signal is linked_design.signals["vel"]

    def test_link_output_sets_driver(self, linked_design):
        linked_design.link_pin("src", "out", "vel")
        assert linked_design.signals["vel"].driver is linked_design.blocks["src"].pins["out"]

    def test_link_output_no_readers(self, linked_design):
        linked_design.link_pin("src", "out", "vel")
        assert linked_design.signals["vel"].readers == []

    def test_link_input_and_output(self, linked_design):
        linked_design.link_pin("src", "out", "vel")
        linked_design.link_pin("s1", "in", "vel")
        assert linked_design.signals["vel"].driver is linked_design.blocks["src"].pins["out"]
        assert linked_design.blocks["s1"].pins["in"] in linked_design.signals["vel"].readers

    def test_multiple_inputs(self, linked_design, block_def_with_pins):
        linked_design.add_block_instance("s2", "simple")
        linked_design.link_pin("s1", "in", "vel")
        linked_design.link_pin("s2", "in", "vel")
        assert len(linked_design.signals["vel"].readers) == 2

    def test_raw_pin_accepts_any_type(self, empty_design, block_def_with_raw):
        empty_design.add_block_def(block_def_with_raw)
        empty_design.add_block_instance("p1", "passthrough")
        empty_design.add_signal("u", PinType.U32)
        empty_design.link_pin("p1", "raw_in", "u")
        assert empty_design.blocks["p1"].pins["raw_in"].signal is empty_design.signals["u"]

    def test_unknown_block_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.link_pin("nonexistent", "in", "vel")
        assert str(exc.value) == "unknown block 'nonexistent'"

    def test_unknown_pin_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.link_pin("s1", "nonexistent", "vel")
        assert str(exc.value) == "unknown pin 's1.nonexistent'"

    def test_unknown_signal_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.link_pin("s1", "in", "nonexistent")
        assert str(exc.value) == "unknown signal 'nonexistent'"

    def test_already_connected_raises(self, linked_design):
        linked_design.link_pin("s1", "in", "vel")
        with pytest.raises(EmblocsError) as exc:
            linked_design.link_pin("s1", "in", "vel")
        assert str(exc.value) == "pin 's1.in' is already connected to signal 'vel'"

    def test_type_mismatch_raises(self, linked_design):
        linked_design.add_signal("b", PinType.BOOL)
        with pytest.raises(EmblocsError) as exc:
            linked_design.link_pin("s1", "in", "b")
        assert str(exc.value) == "type mismatch: pin 's1.in' is FLOAT but signal 'b' is BOOL"

    def test_second_driver_raises(self, linked_design, block_def_with_output):
        linked_design.add_block_instance("src2", "source")
        linked_design.link_pin("src", "out", "vel")
        with pytest.raises(EmblocsError) as exc:
            linked_design.link_pin("src2", "out", "vel")
        assert str(exc.value) == "signal 'vel' already has a driver: 'src.out'"


# ---------------------------------------------------------------------------
# unlink_pin tests
# ---------------------------------------------------------------------------

class TestUnlinkPin:

    def test_unlink_input_pin(self, linked_design):
        linked_design.link_pin("s1", "in", "vel")
        linked_design.unlink_pin("s1", "in")
        assert linked_design.blocks["s1"].pins["in"].signal.is_dummy

    def test_unlink_input_removes_from_readers(self, linked_design):
        linked_design.link_pin("s1", "in", "vel")
        linked_design.unlink_pin("s1", "in")
        assert linked_design.blocks["s1"].pins["in"] not in linked_design.signals["vel"].readers

    def test_unlink_output_pin(self, linked_design):
        linked_design.link_pin("src", "out", "vel")
        linked_design.unlink_pin("src", "out")
        assert linked_design.blocks["src"].pins["out"].signal.is_dummy

    def test_unlink_output_clears_driver(self, linked_design):
        linked_design.link_pin("src", "out", "vel")
        linked_design.unlink_pin("src", "out")
        assert linked_design.signals["vel"].driver is None

    def test_unlink_unconnected_is_noop(self, linked_design):
        linked_design.unlink_pin("s1", "in")
        assert linked_design.blocks["s1"].pins["in"].signal.is_dummy

    def test_unlink_preserves_value(self, linked_design):
        linked_design.link_pin("src", "out", "vel")
        linked_design.signals["vel"].value = 3.14
        linked_design.unlink_pin("src", "out")
        dummy = linked_design.dummy_signals["__src__out"]
        assert dummy.value == 3.14

    def test_unlink_restores_dummy(self, linked_design):
        linked_design.link_pin("s1", "in", "vel")
        linked_design.unlink_pin("s1", "in")
        assert linked_design.blocks["s1"].pins["in"].signal.is_dummy

    def test_unknown_block_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.unlink_pin("nonexistent", "in")
        assert str(exc.value) == "unknown block 'nonexistent'"

    def test_unknown_pin_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.unlink_pin("s1", "nonexistent")
        assert str(exc.value) == "unknown pin 's1.nonexistent'"


# ---------------------------------------------------------------------------
# set_pin_value tests
# ---------------------------------------------------------------------------

class TestSetPinValue:

    def test_set_unconnected_pin(self, linked_design):
        linked_design.set_pin_value("s1", "in", 1.5)
        dummy = linked_design.dummy_signals["__s1__in"]
        assert dummy.value == 1.5

    def test_set_connected_pin_raises(self, linked_design):
        linked_design.link_pin("s1", "in", "vel")
        with pytest.raises(EmblocsError) as exc:
            linked_design.set_pin_value("s1", "in", 1.5)
        assert str(exc.value) == "pin 's1.in' is connected to signal 'vel'; cannot set value directly"

    def test_unknown_block_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.set_pin_value("nonexistent", "in", 1.5)
        assert str(exc.value) == "unknown block 'nonexistent'"

    def test_unknown_pin_raises(self, linked_design):
        with pytest.raises(EmblocsError) as exc:
            linked_design.set_pin_value("s1", "nonexistent", 1.5)
        assert str(exc.value) == "unknown pin 's1.nonexistent'"

    def test_type_validation(self, linked_design):
        """set_pin_value rejects values incompatible with the pin type."""
        with pytest.raises(EmblocsError):
            linked_design.set_pin_value("s1", "in", "not_a_number")


# ---------------------------------------------------------------------------
# Fixtures for link_function / unlink_function tests
# ---------------------------------------------------------------------------

@pytest.fixture
def function_design(empty_design, block_def_with_pins):
    """
    A Design with:
      - 'simple' BlockDef (has function 'update')
      - instances 's1' and 's2'
      - threads 'fast' (1kHz) and 'slow' (10Hz)
    """
    empty_design.add_block_def(block_def_with_pins)
    empty_design.add_block_instance("s1", "simple")
    empty_design.add_block_instance("s2", "simple")
    empty_design.add_thread("fast", 1000000)
    empty_design.add_thread("slow", 100000000)
    return empty_design


# ---------------------------------------------------------------------------
# link_function tests
# ---------------------------------------------------------------------------

class TestLinkFunction:

    def test_link_function(self, function_design):
        function_design.link_function("s1", "update", "fast")
        func = function_design.blocks["s1"].functions["update"]
        assert func.thread is function_design.threads["fast"]

    def test_link_adds_to_thread(self, function_design):
        function_design.link_function("s1", "update", "fast")
        func = function_design.blocks["s1"].functions["update"]
        assert func in function_design.threads["fast"].functions

    def test_link_preserves_order(self, function_design):
        function_design.link_function("s1", "update", "fast")
        function_design.link_function("s2", "update", "fast")
        funcs = function_design.threads["fast"].functions
        assert funcs[0] is function_design.blocks["s1"].functions["update"]
        assert funcs[1] is function_design.blocks["s2"].functions["update"]

    def test_two_functions_different_threads(self, function_design):
        function_design.link_function("s1", "update", "fast")
        function_design.link_function("s2", "update", "slow")
        assert function_design.blocks["s1"].functions["update"].thread is function_design.threads["fast"]
        assert function_design.blocks["s2"].functions["update"].thread is function_design.threads["slow"]

    def test_unknown_block_raises(self, function_design):
        with pytest.raises(EmblocsError) as exc:
            function_design.link_function("nonexistent", "update", "fast")
        assert str(exc.value) == "unknown block 'nonexistent'"

    def test_unknown_function_raises(self, function_design):
        with pytest.raises(EmblocsError) as exc:
            function_design.link_function("s1", "nonexistent", "fast")
        assert str(exc.value) == "unknown function 's1.nonexistent'"

    def test_unknown_thread_raises(self, function_design):
        with pytest.raises(EmblocsError) as exc:
            function_design.link_function("s1", "update", "nonexistent")
        assert str(exc.value) == "unknown thread 'nonexistent'"

    def test_already_assigned_raises(self, function_design):
        function_design.link_function("s1", "update", "fast")
        with pytest.raises(EmblocsError) as exc:
            function_design.link_function("s1", "update", "slow")
        assert str(exc.value) == "function 's1.update' is already assigned to thread 'fast'"


# ---------------------------------------------------------------------------
# unlink_function tests
# ---------------------------------------------------------------------------

class TestUnlinkFunction:

    def test_unlink_function(self, function_design):
        function_design.link_function("s1", "update", "fast")
        function_design.unlink_function("s1", "update")
        assert function_design.blocks["s1"].functions["update"].thread is None

    def test_unlink_removes_from_thread(self, function_design):
        function_design.link_function("s1", "update", "fast")
        function_design.unlink_function("s1", "update")
        assert function_design.blocks["s1"].functions["update"] not in \
               function_design.threads["fast"].functions

    def test_unlink_unassigned_is_noop(self, function_design):
        function_design.unlink_function("s1", "update")
        assert function_design.blocks["s1"].functions["update"].thread is None

    def test_unlink_middle_of_thread(self, function_design):
        function_design.link_function("s1", "update", "fast")
        function_design.link_function("s2", "update", "fast")
        function_design.unlink_function("s1", "update")
        funcs = function_design.threads["fast"].functions
        assert len(funcs) == 1
        assert funcs[0] is function_design.blocks["s2"].functions["update"]

    def test_unknown_block_raises(self, function_design):
        with pytest.raises(EmblocsError) as exc:
            function_design.unlink_function("nonexistent", "update")
        assert str(exc.value) == "unknown block 'nonexistent'"

    def test_unknown_function_raises(self, function_design):
        with pytest.raises(EmblocsError) as exc:
            function_design.unlink_function("s1", "nonexistent")
        assert str(exc.value) == "unknown function 's1.nonexistent'"
