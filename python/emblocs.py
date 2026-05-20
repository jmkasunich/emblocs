# emblocs.py
# Shared object model for EMBLOCS tools.
# All tools (bloc_compiler, blocs_compiler, runtime monitor) import this module
# so they all work with the same class hierarchy.
#
# At the BlockSpec level (derived from a .bloc file), declarations are
# represented as "Spec" objects: recipes that may reference unresolved
# parameter names.  At the BlockDef level (a fully resolved variant),
# declarations are represented as "Def" objects with concrete values.
#

from __future__ import annotations
from typing import Union
from dataclasses import dataclass, field
from enum import Enum, auto
import textwrap


# ---------------------------------------------------------------------------
# Enumerations & Constants
# ---------------------------------------------------------------------------

class PinType(Enum):
    BOOL  = auto()
    U32   = auto()
    S32   = auto()
    FLOAT = auto()
    RAW   = auto()


class PinDir(Enum):
    INPUT  = auto()
    OUTPUT = auto()

U32_MAX =  0xFFFFFFFF
S32_MAX =  0x7FFFFFFF
S32_MIN = -0x80000000

# ---------------------------------------------------------------------------
# Output formatting for describe() methods
# ---------------------------------------------------------------------------

# set this True to have Design.describe() recurse into child objects,
# or False to have it only print top-level summaries
recurse = True

# set this to '\n' to have descriptions start on a new line,
# or ' ' to have them follow the declaration on the same line
descr_prefix = '\n'

def _format_descr(descr: str) -> str:
    if not descr:
        return ""
    return descr_prefix + textwrap.indent(descr, "  # ")

def _indent_child(child_descr: str) -> str:
    return textwrap.indent(child_descr, "  ")


# ---------------------------------------------------------------------------
# Exception for error handling
# Simple for now; sub-classes of errors or more complex
# message formatting can be added later if needed
# ---------------------------------------------------------------------------

class EmblocsError(Exception):
    """Base exception for all EMBLOCS object model errors."""
    pass


# ---------------------------------------------------------------------------
# BlockSpec-level classes
# These are produced by parsing a .bloc file.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParamSpec:
    """
    A variant parameter declared in a .bloc file.

    Parameters must all be declared before any other declarations in the
    body of the .bloc file.  They are stored separately from statements
    in BlockSpec because they must be supplied with concrete values before
    any statement can be resolved.

    Fields:
        name        -- parameter name, by convention UPPERCASE
        param_type  -- 'bool' or 'u32'
        default     -- default value, used when not supplied on blockdef command
        min_val     -- minimum allowed value (u32 only); None if not specified
        max_val     -- maximum allowed value (u32 only); None if not specified
        description -- /// annotation text, or empty string if none
    """
    name:        str
    param_type:  str
    default:     int
    min_val:     int = 0
    max_val:     int = U32_MAX
    description: str = ""

    def describe(self) -> str:
        desc = _format_descr(self.description)
        range_str = ""
        if self.min_val != 0:
            range_str += f"  min={self.min_val}"
        if self.max_val != U32_MAX:
            range_str += f"  max={self.max_val}"
        return(f"param  {self.name}  {self.param_type}"
               f"  default={self.default}{range_str}{desc}")


@dataclass(frozen=True)
class DimSpec:
    """
    One array dimension on a pin declaration.

    Fields:
        size_expr  -- expression string giving the array size, e.g. "NUM_CHAN",
                      "16", "(NUM_CHAN-1)".  Evaluated at resolution time.
        index_var  -- identifier chosen by the block author to name the index
                      variable for this dimension, e.g. "i", "c".  In scope
                      for the name template and trailing export_condition of
                      the enclosing PinSpec.
    """
    size_expr: str
    index_var: str

    def describe(self) -> str:
        dim_str = ("[" + f"{self.index_var}={self.size_expr}" + "]")
        return f"dim  {dim_str}"


@dataclass(frozen=True)
class PinSpec:
    """
    A recipe for one or more pins, as declared in a .bloc file.

    A scalar pin (dims == []) produces one PinDef when resolved.
    An array pin produces one PinDef per exported slot when resolved.
    Slots for which export_condition evaluates to false receive no PinDef
    and are initialized to NULL in system.c.

    The name_template is the template as written by the block author, with
    {expr:width} format specifiers intact.  The field_name is derived from
    the template by replacing each {expr:width} with 'width' zeros and
    appending '_', giving the C struct member name.  The dedup_name is the
    same as field_name and is used for namespace collision detection at
    parse time.

    Fields:
        name_template    -- EMBLOCS-visible name template as written, e.g.
                            "in", "ch{i:2}_out", "pin_{i:2}_in{j:1}".
                            For scalar pins with no {..}, this is just the pin name.
        field_name       -- C struct member name, derived from name_template by
                            replacing each {expr:width} with width zeros and
                            appending '_'.  e.g. "in_", "ch00_out_", "pin_00_in0_"
        dedup_name       -- same as field_name; used for namespace collision
                            detection in BlockSpec.namespace
        pin_type         -- PinType enum value
        direction        -- PinDir enum value
        dims             -- ordered list of DimSpec objects.
                            []             => scalar pin
                            [DimSpec]      => 1D array
                            [DimSpec, DimSpec] => 2D array (maximum supported)
        export_condition -- trailing 'if' expression string, or None if all
                            slots are exported unconditionally.  Evaluated
                            per slot at resolution time with index variables
                            in scope.
        description      -- /// annotation text, or empty string if none
    """
    name_template:    str
    field_name:       str
    dedup_name:       str
    pin_type:         PinType
    direction:        PinDir
    dims:             list[DimSpec]
    export_condition: str | None = None
    description:      str        = ""

    def describe(self) -> str:
        dims_str = ("scalar" if self.dims == []
                    else "[" + "][".join(
                        f"{d.index_var}={d.size_expr}"
                        for d in self.dims
                    ) + "]")
        cond_str = f"  if {self.export_condition}" if self.export_condition else ""
        desc = _format_descr(self.description)
        return (f"pin  {self.pin_type.name:<6} {self.direction.name:<7} "
                f"'{self.name_template}' -> {self.field_name} ({dims_str})"
                f"{cond_str}{desc}")


@dataclass(frozen=True)
class VarDef:
    """
    A private variable declaration in the instance struct.

    The C declaration is stored verbatim as the block compiler does not
    parse or validate it.  VarDef is fully defined at parse time; there
    is no unresolved content.

    The field_name is extracted from the C declaration by the parser and
    used as-is for both the C struct member name and namespace collision
    detection.  Unlike pins, no trailing '_' is appended — var names are
    private to the block implementation and the block author is responsible
    for avoiding collisions with SDK macros or other predefined names.

    Fields:
        field_name -- C struct member name extracted from the declaration,
                      e.g. "accumulated" from "float accumulated"
        dedup_name -- same as field_name; used for namespace collision
                      detection in BlockSpec.namespace
        c_decl     -- the full C declaration string, e.g. "float accumulated;"
    """
    field_name: str
    dedup_name: str
    c_decl:     str

    def describe(self) -> str:
        return f"var  {self.c_decl}"


@dataclass(frozen=True)
class FunctSpec:
    """
    A function available in the block.

    Function names are always plain identifiers, never templates.  However,
    they may be contained in an #if block and thus have conditions that
    govern whether they are exported.

    The dedup_name is the function name with '_' appended, consistent with
    the derivation used for PinSpec and VarDef, ensuring functions, pins,
    and vars all share one namespace.

    Fields:
        name        -- EMBLOCS-visible function name (e.g. "update", "read")
        dedup_name  -- name + '_', used for namespace collision detection
        description -- /// annotation text, or empty string if none
    """
    name:        str
    dedup_name:  str
    description: str = ""

    def describe(self) -> str:
        desc = _format_descr(self.description)
        return f"function  {self.name}{desc}"


@dataclass(frozen=True)
class Statement:
    """
    A statement from the body of a .bloc file, paired with the list of
    #if conditions that were active when the statement was parsed.

    At resolution time, all expressions in 'conditions' are evaluated
    against the parameter values.  If any evaluates to false (zero), the
    statement is skipped entirely.  If all are true, the statement is
    processed to generate resolved output.

    Fields:
        conditions -- list of #if expression strings, in the order they
                      appeared on the #if stack at the point of this
                      declaration.  Empty list means unconditionally active.
        statement  -- the statement object: PinSpec, VarDef, or FunctSpec
    """
    conditions: list[str]
    statement:  PinSpec | VarDef | FunctSpec

    def describe(self) -> str:
        if self.conditions:
            cond_str = "(if: " + " && ".join(self.conditions) + "): "
        else:
            cond_str = ""
        return cond_str + self.statement.describe()


@dataclass
class BlockSpec:
    """
    The complete description of a block as derived from a .bloc file.
    Contains unresolved declarations that may reference parameter names.
    Resolving a BlockSpec against concrete parameter values produces a
    BlockDef (defined elsewhere, once resolution is implemented).

    Fields:
        source_path  -- path to the .bloc file this was parsed from
        name         -- block name from the 'block' declaration
        description  -- /// text from the 'block' declaration
        params       -- ordered list of ParamSpec objects; all parameters
                        must be declared before any statements in the source
                        file and must be supplied with concrete values before
                        resolution can proceed
        defaults     -- dict of {param_name: default_value} for all params;
                        populated when the first body statement is encountered,
                        used to validate expressions at parse time
        statements   -- ordered list of Statement objects preserving
                        declaration order from the .bloc file; contains
                        PinSpec, VarDef, and FunctSpec objects intermixed
        namespace    -- set of dedup_names for all statements added so far;
                        used for O(1) collision detection at parse time
    """
    source_path: str
    name:        str               = ""
    description: str               = ""
    params:      list[ParamSpec]   = field(default_factory=list)
    defaults:    dict[str, int]    = field(default_factory=dict)
    statements:  list[Statement]   = field(default_factory=list)
    namespace:   set[str]          = field(default_factory=set)

    def describe(self) -> str:
        """Return a human-readable multi-line description for debugging."""
        lines = []
        desc = _format_descr(self.description)
        lines.append(f"BlockSpec: {self.name}  ({self.source_path}){desc}")
        for p in self.params:
            lines.append(_indent_child(p.describe()))
        for s in self.statements:
            lines.append(_indent_child(s.describe()))
        return "\n".join(lines)

# ---------------------------------------------------------------------------
# BlockDef-level classes
# These are produced by resolving a BlockSpec against concrete parameter
# values.  All expressions are evaluated, all conditionals resolved, and
# all array dimensions are concrete integers.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PinDef:
    """
    A fully resolved pin definition, child of a BlockDef.

    Fields:
        name         -- EMBLOCS-visible pin name (e.g. "ch00_out")
        field_name   -- C struct field name (e.g. "ch00_out_")
        field_indices -- for array pins, the list of concrete indices for this slot
        pin_type     -- PinType enum value
        direction    -- PinDir enum value
        description  -- /// annotation text, or empty string if none
    """
    name:         str
    field_name:   str
    pin_type:     PinType
    direction:    PinDir
    field_indices: tuple[int, ...] = ()
    description:  str = ""

    def describe(self) -> str:
        desc = _format_descr(self.description)
        if self.field_indices:
            indices = "".join(f"[{i}]" for i in self.field_indices)
            field_str = f"{self.field_name}{indices}"
        else:
            field_str = self.field_name
        return (f"pin  {self.pin_type.name:<6} {self.direction.name:<7} "
                f"{self.name} -> {field_str}{desc}")


@dataclass(frozen=True)
class FunctDef:
    """
    A fully resolved function definition, child of a BlockDef.

    Fields:
        name        -- EMBLOCS-visible function name (e.g. "update")
        description -- /// annotation text, or empty string if none
    """
    name:        str
    description: str = ""

    def describe(self) -> str:
        desc = _format_descr(self.description)
        return f"function  {self.name}{desc}"

BlockDefChild = PinDef | FunctDef

@dataclass(frozen=True)
class BlockDef:
    """
    A fully resolved block definition, produced by resolving a BlockSpec
    against concrete parameter values.  All conditional declarations have
    been evaluated; only the pins, vars, and functions active for these
    parameter values are present.

    Fields:
        name        -- variant name (e.g. "pid_controller")
        source_path -- path to the source .bloc file
        description -- block description text
        pins        -- dict of PinDef keyed by emblocs pin name
        functions   -- dict of FunctDef keyed by function name
        namespace   -- dict mapping all pin and function names to their
                       PinDef or FunctDef objects; populated at resolution
                       time, catches pin/function name collisions
        params      -- dict of param name -> concrete integer value
        ordered_declarations -- complete ordered list of PinDef, VarDef,
                               and FunctDef objects, preserving declaration
                               order from the .bloc file.  Used for C struct
                               generation and for function/pin ordering
                               analysis.
    """
    name:        str
    source_path: str
    description: str
    pins:        dict[str, PinDef]
    functions:   dict[str, FunctDef]
    namespace:   dict[str, BlockDefChild]
    params:      dict[str, int]
    ordered_declarations: list[PinDef | VarDef | FunctDef]

    def describe(self) -> str:
        lines = []
        desc = _format_descr(self.description)
        lines.append(f"BlockDef: {self.name}  ({self.source_path}){desc}")
        for p, v in self.params.items():
            lines.append(_indent_child(f"param  {p} = {v}"))
        for decl in self.ordered_declarations:
            lines.append(_indent_child(decl.describe()))
        return "\n".join(lines)

# ---------------------------------------------------------------------------
# Design-level classes
# These are produced by parsing a .blocs file.  A Design is a complete,
# concrete system: named block instances with resolved parameter values,
# signals connecting pins, and threads scheduling functions.
# ---------------------------------------------------------------------------

@dataclass
class Signal:
    """
    A named signal connecting pins in a Design.

    Fields:
        name     -- signal name, unique within the Design namespace
        sig_type -- PinType enum value (bool, u32, s32, float)
        value    -- current/initial value
        driver   -- PinInstance driving this signal, or None
        readers  -- list of PinInstances reading this signal
    """
    name:     str
    sig_type: PinType
    value:    int | float = 0
    driver:   PinInstance | None = None
    readers:  list[PinInstance]  = field(default_factory=list)
    is_dummy: bool = False

    def describe(self) -> str:
        driver_str = self.driver.pin_def.name if self.driver else "none"
        lines = [f"signal  {self.name}  {self.sig_type.name}  "
                 f"value={self.value}  driver={driver_str}"]
        for r in self.readers:
            lines.append(f"  reader  {r.pin_def.name}")
        return "\n".join(lines)


@dataclass
class Thread:
    """
    A named periodic execution context in a Design.

    Fields:
        name      -- thread name, unique within the Design namespace
        period_ns -- execution period in nanoseconds
        functions -- ordered list of FunctInstance objects
    """
    name:      str
    period_ns: int
    functions: list[FunctInstance] = field(default_factory=list)

    def describe(self) -> str:
        lines = [f"thread  {self.name}  ({self.period_ns} ns)"]
        for func in self.functions:
            lines.append(f"  {func.funct_def.name}")
        return "\n".join(lines)


@dataclass
class PinInstance:
    """
    A pin on a specific block instance.
    Exists only as a member of BlockInstance.pins.

    Fields:
        pin_def -- PinDef metadata (type, direction, names)
        signal  -- connected Signal, or None if unconnected (dummy signal)
    """
    pin_def: PinDef
    signal:  Signal | None = None
    block:   BlockInstance | None = None

    def describe(self) -> str:
        sig = self.signal.name if self.signal else "dummy"
        return f"pin  {self.block.name!r}.{self.pin_def.name} -> {sig}"


@dataclass
class FunctInstance:
    """
    A function on a specific block instance.
    Exists only as a member of BlockInstance.functions.

    Fields:
        funct_def -- FunctDef metadata (name, description)
        thread    -- Thread this function is assigned to, or None
    """
    funct_def: FunctDef
    thread:    Thread | None = None
    block:     BlockInstance | None = None

    def describe(self) -> str:
        thr = self.thread.name if self.thread else "unassigned"
        return f"function  {self.block.name!r}.{self.funct_def.name} -> {thr}"

BlockInstChild = PinInstance | FunctInstance

@dataclass
class BlockInstance:
    """
    A named instance of a BlockDef in a Design.

    Fields:
        name      -- instance name, unique within the Design namespace
        block_def -- the BlockDef this instance is based on
        pins      -- dict of PinInstance keyed by emblocs pin name
        functions -- dict of FunctInstance keyed by function name
        namespace -- dict mapping all pin and function names to their
                     PinInstance or FunctInstance objects for O(1) lookup
    """
    name:      str
    block_def: BlockDef
    pins:      dict[str, PinInstance]   = field(default_factory=dict)
    functions: dict[str, FunctInstance] = field(default_factory=dict)
    namespace: dict[str, BlockInstChild] = field(default_factory=dict)

    def describe(self) -> str:
        lines = [f"block  {self.name} ({self.block_def.name})"]
        for pin in self.pins.values():
            lines.append(_indent_child(pin.describe()))
        for func in self.functions.values():
            lines.append(_indent_child(func.describe()))
        return "\n".join(lines)

    def find_child_by_name(self, name: str) -> BlockInstChild:
        """ takes name of pin or function and returns matching object """
        child = self.namespace.get(name)
        if child == None:
            raise EmblocsError(f"{name!r} not found in block {self.name!r}")
        return child


DesignChild = BlockDef | BlockInstance | Thread | Signal
DesignObject = DesignChild | BlockInstChild

@dataclass
class Design:
    """
    A complete, concrete system design produced by parsing a .blocs file.

    All four top-level dicts share one flat namespace enforced by the
    namespace set -- a block definition, block instance, signal, and thread
    cannot share a name.

    Fields:
        source_path -- path to the .blocs file this was parsed from
        block_defs  -- dict of BlockDef keyed by variant name
        blocks      -- dict of BlockInstance keyed by instance name
        signals     -- dict of Signal keyed by signal name
        threads     -- dict of Thread keyed by thread name
        namespace   -- dict of all BlockDef, BlockInstance, Signal and Thread
                       objects in the design, O(1) search and uniqueness checks
    """
    source_path:   str
    block_defs:    dict[str, BlockDef]      = field(default_factory=dict)
    blocks:        dict[str, BlockInstance] = field(default_factory=dict)
    signals:       dict[str, Signal]        = field(default_factory=dict)
    dummy_signals: dict[str, Signal]        = field(default_factory=dict)
    threads:       dict[str, Thread]        = field(default_factory=dict)
    namespace:     dict[str, DesignChild]   = field(default_factory=dict)

    def describe(self) -> str:
        lines = [f"Design: {self.source_path}"]
        if recurse:
            for bd in self.block_defs.values():
                lines.append(_indent_child(bd.describe()))
            for bi in self.blocks.values():
                lines.append(_indent_child(bi.describe()))
            for sig in self.signals.values():
                lines.append(_indent_child(sig.describe()))
            for thr in self.threads.values():
                lines.append(_indent_child(thr.describe()))
        else:
            for bd in self.block_defs.values():
                lines.append(_indent_child(f"blockdef  {bd.name}"))
            for bi in self.blocks.values():
                lines.append(_indent_child(f"block  {bi.name} ({bi.block_def.name})"))
            for sig in self.signals.values():
                lines.append(_indent_child(f"signal  {sig.name}  {sig.sig_type.name}"))
            for thr in self.threads.values():
                lines.append(_indent_child(f"thread  {thr.name}  {thr.period_ns} ns"))
        return "\n".join(lines)

    def find_child_by_name(self, name: str) -> DesignChild:
        """ takes name of blockdef, block instance, signal, or thread
            and returns matching object or None """
        child = self.namespace.get(name)
        if child is None:
            raise EmblocsError(f"{name!r} not found in design {self.source_path!r}")
        return child

    def find_object_by_name(self, name: str) -> DesignObject:
        """ takes name of blockdef, block instance, signal, thread,
            block.pin, or block.function and returns matching object or None """
        n1, sep, n2 = name.partition(".")
        if sep == "":
            return self.find_child_by_name(name)
        else:
            block = self.blocks.get(n1)
            if block is None:
                raise EmblocsError(f"block {n1!r} not found")
            return block.find_child_by_name(n2)

    def add_block_def(self, block_def: BlockDef) -> BlockDef:
        """
        Add a fully resolved BlockDef to the Design.
        Raises EmblocsError if the name is already in use.
        """
        # validate
        if block_def.name in self.namespace:
            raise EmblocsError(f"name {block_def.name!r} is already in use")
        # add to design
        self.block_defs[block_def.name] = block_def
        self.namespace[block_def.name] = block_def
        return block_def

    def add_block_instance(self, instance_name: str, block_def_name: str) -> BlockInstance:
        """
        Create a named instance of a previously defined BlockDef.
        Raises EmblocsError if instance_name is already in use,
        or if block_def_name is not a known BlockDef.
        """
        #validate
        if instance_name in self.namespace:
            raise EmblocsError(f"name {instance_name!r} is already in use")
        if block_def_name not in self.block_defs:
            raise EmblocsError(f"unknown block definition {block_def_name!r}")
        # generate component parts
        block_def = self.block_defs[block_def_name]
        pins = {}
        functions = {}
        namespace = {}
        for name, pd in block_def.pins.items():
            pin = PinInstance(pin_def=pd)
            pins[name] = pin
            namespace[name] = pin
        for name, fd in block_def.functions.items():
            funct = FunctInstance(funct_def=fd)
            functions[name] = funct
            namespace[name] = funct
        # generate instance
        instance = BlockInstance(
            name      = instance_name,
            block_def = block_def,
            pins      = pins,
            functions = functions,
            namespace  = namespace,
        )
        # set back-references and create dummy signals for each pin
        for pin_name, pin in instance.pins.items():
            pin.block = instance
            dummy_name = f"__{instance_name}__{pin_name}"
            dummy = Signal(
                name     = dummy_name,
                sig_type = pin.pin_def.pin_type if pin.pin_def.pin_type != PinType.RAW
                        else PinType.U32,
                is_dummy = True,
            )
            self.dummy_signals[dummy_name] = dummy
            pin.signal = dummy
        # set back references for functions
        for func in instance.functions.values():
            func.block = instance
        # add to design
        self.blocks[instance_name] = instance
        self.namespace[instance_name] = instance
        return instance

    def add_signal(self, name: str, sig_type: PinType) -> Signal:
        """
        Create a named signal of the given type and add it to the Design.
        Raises EmblocsError if the name is already in use or type is invalid.
        """
        # validate
        if name in self.namespace:
            raise EmblocsError(f"name {name!r} is already in use")
        if sig_type not in (PinType.BOOL, PinType.U32, PinType.S32, PinType.FLOAT):
            raise EmblocsError(f"invalid signal type {sig_type.name!r}")
        # generate signal and add to design
        signal = Signal(name=name, sig_type=sig_type)
        self.signals[name] = signal
        self.namespace[name] = signal
        return signal

    def add_thread(self, name: str, period_ns: int) -> Thread:
        """
        Create a named thread with the given period and add it to the Design.
        Raises EmblocsError if the name is already in use or period is invalid.
        """
        # validate
        if name in self.namespace:
            raise EmblocsError(f"name {name!r} is already in use")
        if period_ns <= 0:
            raise EmblocsError(f"thread period must be positive, got {period_ns}")
        # generate thread and add to design
        thread = Thread(name=name, period_ns=period_ns)
        self.threads[name] = thread
        self.namespace[name] = thread
        return thread

    def _validate_and_set_value(self, signal: Signal, value: int | float) -> None:
        """
        Validate value against signal type and set it.
        Raises EmblocsError if value is incompatible with signal type.
        """
        # validate value against signal type
        if signal.sig_type == PinType.BOOL:
            if value not in (0, 1, True, False):
                raise EmblocsError(
                    f"value {value!r} is not valid for bool signal {signal.name!r}")
            value = int(value)
        elif signal.sig_type == PinType.U32:
            if not isinstance(value, int) or value < 0 or value > U32_MAX:
                raise EmblocsError(
                    f"value {value!r} is out of range for u32 signal {signal.name!r}")
        elif signal.sig_type == PinType.S32:
            if not isinstance(value, int) or value < S32_MIN or value > S32_MAX:
                raise EmblocsError(
                    f"value {value!r} is out of range for s32 signal {signal.name!r}")
        elif signal.sig_type == PinType.FLOAT:
            if not isinstance(value, (int, float)):
                raise EmblocsError(
                    f"value {value!r} is not valid for float signal {signal.name!r}")
            value = float(value)
        # set value
        signal.value = value


    def set_signal_value(self, name: str, value: int | float) -> None:
        """
        Set the stored value of a signal.
        Raises EmblocsError if the signal does not exist, if the signal
        has an output pin driver (value is driven, not stored), or if
        the value is incompatible with the signal type.
        """
        # validate existance and settability
        if name not in self.signals:
            raise EmblocsError(f"unknown signal {name!r}")
        signal = self.signals[name]
        if signal.driver is not None:
            raise EmblocsError(f"signal {name!r} is driven by "
                            f"'{signal.driver.block.name}.{signal.driver.pin_def.name}'; "
                            f"cannot set value directly")
        # call shared helper to finish the job
        self._validate_and_set_value(signal, value)

    def set_pin_value(self, block_name: str, pin_name: str, value) -> None:
        """
        Set the value of an unconnected pin's dummy signal.
        Raises EmblocsError if the pin is connected to a named signal,
        or if block or pin name is unknown.
        """
        # validate existance and settability
        if block_name not in self.blocks:
            raise EmblocsError(f"unknown block {block_name!r}")
        instance = self.blocks[block_name]
        if pin_name not in instance.pins:
            raise EmblocsError(f"unknown pin '{block_name}.{pin_name}'")
        pin = instance.pins[pin_name]
        if not pin.signal.is_dummy:
            raise EmblocsError(f"pin '{block_name}.{pin_name}' is connected to "
                            f"signal {pin.signal.name!r}; cannot set value directly")
        # call shared helper to finish the job
        self._validate_and_set_value(pin.signal, value)

    def link_pin(self, block_name: str, pin_name: str, sig_name: str) -> None:
        """
        Connect a pin to a signal.
        Raises EmblocsError if:
        - block, pin, or signal name is unknown
        - pin is already connected
        - signal type is incompatible with pin type
        - pin is an output and signal already has a driver
        """
        # validate names and existence
        if block_name not in self.blocks:
            raise EmblocsError(f"unknown block {block_name!r}")
        instance = self.blocks[block_name]
        if pin_name not in instance.pins:
            raise EmblocsError(f"unknown pin '{block_name}.{pin_name}'")
        if sig_name not in self.signals:
            raise EmblocsError(f"unknown signal {sig_name!r}")
        # validate pin not already linked
        pin = instance.pins[pin_name]
        signal = self.signals[sig_name]
        if not pin.signal.is_dummy:
            raise EmblocsError(f"pin '{block_name}.{pin_name}' is already connected"
                               f" to signal {pin.signal.name!r}")
        # validate type: raw pins connect to any signal type
        if pin.pin_def.pin_type != PinType.RAW:
            if pin.pin_def.pin_type != signal.sig_type:
                raise EmblocsError(
                    f"type mismatch: pin '{block_name}.{pin_name}' is "
                    f"{pin.pin_def.pin_type.name} but signal {sig_name!r} is "
                    f"{signal.sig_type.name}")
        # check for driver conflicts, then connect
        if pin.pin_def.direction == PinDir.OUTPUT:
            if signal.driver is not None:
                raise EmblocsError(
                    f"signal {sig_name!r} already has a driver: "
                    f"'{signal.driver.block.name}.{signal.driver.pin_def.name}'")
            signal.driver = pin
        else:
            signal.readers.append(pin)
        pin.signal = signal

    def unlink_pin(self, block_name: str, pin_name: str) -> None:
        """
        Disconnect a pin from its signal.
        If the pin is not connected, this is a no-op.
        Raises EmblocsError if block or pin name is unknown.
        """
        # validate names and existence
        if block_name not in self.blocks:
            raise EmblocsError(f"unknown block {block_name!r}")
        instance = self.blocks[block_name]
        if pin_name not in instance.pins:
            raise EmblocsError(f"unknown pin '{block_name}.{pin_name}'")
        pin = instance.pins[pin_name]
        # if not linked, no-op
        if pin.signal.is_dummy:
            return
        # disconnect pin from signal
        signal = pin.signal
        dummy = self.dummy_signals[f"__{block_name}__{pin_name}"]
        dummy.value = signal.value
        if pin.pin_def.direction == PinDir.OUTPUT:
            signal.driver = None
        else:
            signal.readers.remove(pin)
        pin.signal = dummy

    def link_function(self, block_name: str, func_name: str, thread_name: str) -> None:
        """
        Assign a block function to a thread, appending it to the thread's
        execution list.
        Raises EmblocsError if:
        - block, function, or thread name is unknown
        - function is already assigned to a thread
        """
        # validate names and existence
        if block_name not in self.blocks:
            raise EmblocsError(f"unknown block {block_name!r}")
        instance = self.blocks[block_name]
        if func_name not in instance.functions:
            raise EmblocsError(f"unknown function '{block_name}.{func_name}'")
        if thread_name not in self.threads:
            raise EmblocsError(f"unknown thread {thread_name!r}")
        # validate not already linked
        func = instance.functions[func_name]
        if func.thread is not None:
            raise EmblocsError(
                f"function '{block_name}.{func_name}' is already assigned to "
                f"thread {func.thread.name!r}")
        # link function to thread
        thread = self.threads[thread_name]
        func.thread = thread
        thread.functions.append(func)


    def unlink_function(self, block_name: str, func_name: str) -> None:
        """
        Remove a block function from its thread.
        If the function is not assigned to any thread, this is a no-op.
        Raises EmblocsError if block or function name is unknown.
        """
        # validate names and existence
        if block_name not in self.blocks:
            raise EmblocsError(f"unknown block {block_name!r}")
        instance = self.blocks[block_name]
        if func_name not in instance.functions:
            raise EmblocsError(f"unknown function '{block_name}.{func_name}'")
        func = instance.functions[func_name]
        # if not linked, no-op
        if func.thread is None:
            return
        # disconnect function from thread
        func.thread.functions.remove(func)
        func.thread = None
