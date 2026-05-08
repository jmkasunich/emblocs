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

from dataclasses import dataclass, field
from enum import Enum, auto


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
        range_str = ""
        if self.min_val is not None:
            range_str += f"  min={self.min_val}"
        if self.max_val is not None:
            range_str += f"  max={self.max_val}"
        desc = f"  # {self.description}" if self.description else ""
        return (f"param  {self.name}  {self.param_type}"
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
        desc = f"  # {self.description}" if self.description else ""
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
        c_decl     -- the full C declaration string, e.g. "float accumulated"
                      (semicolon not included; stored without it)
    """
    field_name: str
    dedup_name: str
    c_decl:     str

    def describe(self) -> str:
        return f"var  {self.c_decl};"


@dataclass(frozen=True)
class FunctDef:
    """
    A function exported by the block.

    FunctDef is fully defined at parse time; there is no unresolved content.
    Function names are always plain identifiers, never templates.

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
        desc = f"  # {self.description}" if self.description else ""
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
        statement  -- the statement object: PinSpec, VarDef, or FunctDef
    """
    conditions: list[str]
    statement:  PinSpec | VarDef | FunctDef


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
                        PinSpec, VarDef, and FunctDef objects intermixed
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
        lines.append(f"BlockSpec: {self.name}  ({self.source_path})")
        if self.description:
            for dline in self.description.splitlines():
                lines.append(f"  description: {dline}")
        for p in self.params:
            lines.append(f"  {p.describe()}")
        for s in self.statements:
            cond_str = ""
            if s.conditions:
                cond_str = "(if: " + " && ".join(s.conditions) + "): "
            lines.append(f"  {cond_str}{s.statement.describe()}")
        return "\n".join(lines)
