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
# This file currently defines the BlockSpec-level classes only.
# BlockDef and PinDef are deferred until the resolution step is implemented.

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
import textwrap


# ---------------------------------------------------------------------------
# Enumerations
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
    min_val:     int | None
    max_val:     int | None
    description: str = ""

    def describe(self) -> str:
        desc = _format_descr(self.description)
        range_str = ""
        if self.min_val is not None:
            range_str += f"  min={self.min_val}"
        if self.max_val is not None:
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

    The emblocs_name is the template as written by the block author, with
    {expr:width} format specifiers intact.  The field_name is derived from
    the template by replacing each {expr:width} with 'width' zeros and
    appending '_', giving the C struct member name.  The dedup_name is the
    same as field_name and is used for namespace collision detection at
    parse time.

    Fields:
        emblocs_name     -- EMBLOCS-visible name template as written, e.g.
                            "in", "ch{i:2}_out", "pin_{i:2}_in{j:1}".
                            For scalar pins with no {..}, this is just the pin name.
        field_name       -- C struct member name, derived from emblocs_name by
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
    emblocs_name:     str
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
                f"'{self.emblocs_name}' -> {self.field_name} ({dims_str})"
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
        emblocs_name -- EMBLOCS-visible pin name (e.g. "ch00_out")
        field_name   -- C struct field name (e.g. "ch00_out_")
        field_indices -- for array pins, the list of concrete indices for this slot
        pin_type     -- PinType enum value
        direction    -- PinDir enum value
        description  -- /// annotation text, or empty string if none
    """
    emblocs_name: str
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
                f"{self.emblocs_name} -> {field_str}{desc}")


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
    name:    str
    sig_type: PinType
    value:   int | float = 0
    driver:  object      = None   # PinInstance | None; object avoids forward ref
    readers: list        = field(default_factory=list)

    def describe(self) -> str:
        driver_str = self.driver.pin_def.emblocs_name if self.driver else "none"
        lines = [f"signal  {self.name}  {self.sig_type.name}  "
                 f"value={self.value}  driver={driver_str}"]
        for r in self.readers:
            lines.append(f"  reader  {r.pin_def.emblocs_name}")
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

    def describe(self) -> str:
        sig = self.signal.name if self.signal else "dummy"
        return f"pin  {self.pin_def.emblocs_name} -> {sig}"


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
    thread:    object | None = None   # Thread | None; object avoids forward ref

    def describe(self) -> str:
        thr = self.thread.name if self.thread else "unassigned"
        return f"function  {self.funct_def.name} -> {thr}"


@dataclass
class BlockInstance:
    """
    A named instance of a BlockDef in a Design.

    Fields:
        name      -- instance name, unique within the Design namespace
        block_def -- the BlockDef this instance is based on
        pins      -- dict of PinInstance keyed by emblocs pin name
        functions -- dict of FunctInstance keyed by function name
    """
    name:      str
    block_def: BlockDef
    pins:      dict[str, PinInstance]   = field(default_factory=dict)
    functions: dict[str, FunctInstance] = field(default_factory=dict)

    def describe(self) -> str:
        lines = [f"block  {self.name} ({self.block_def.name})"]
        for pin in self.pins.values():
            lines.append(_indent_child(pin.describe()))
        for func in self.functions.values():
            lines.append(_indent_child(func.describe()))
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
        namespace   -- set of all names for O(1) uniqueness enforcement
    """
    source_path: str
    block_defs:  dict[str, BlockDef]      = field(default_factory=dict)
    blocks:      dict[str, BlockInstance] = field(default_factory=dict)
    signals:     dict[str, Signal]        = field(default_factory=dict)
    threads:     dict[str, Thread]        = field(default_factory=dict)
    namespace:   set[str]                 = field(default_factory=set)

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
