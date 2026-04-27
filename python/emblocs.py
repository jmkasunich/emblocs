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
class PinSpec:
    """
    A recipe for one or more pins, as declared in a .bloc file.

    A scalar pin produces one PinDef when resolved.
    An array pin produces one PinDef per array element when resolved.

    Fields:
        field_name   -- C struct member name (e.g. "in", "out", "input_pins")
        emblocs_name -- EMBLOCS-visible name template (e.g. "in", "ch{NCHANNELS:2}_out")
                        For scalar pins with no template, this equals field_name.
        pin_type     -- PinType enum value
        direction    -- PinDir enum value
        dims         -- List of dimension expressions as strings.
                        []                     => scalar pin
                        ["NCHANNELS"]          => 1D array, size = value of NCHANNELS param
                        ["NINPUTS","NCHANNELS"] => 2D array
                        None                   => append array; size determined by counting
        description  -- /// annotation text, or empty string if none
    """
    field_name:   str
    emblocs_name: str
    pin_type:     PinType
    direction:    PinDir
    dims:         list | None    # None = append array; [] = scalar; [str,...] = fixed array
    description:  str = ""

    def describe(self) -> str:
        dims_str = ("append"  if self.dims is None
                    else "scalar" if self.dims == []
                    else "[" + "][".join(self.dims) + "]")
        desc = f"  # {self.description}" if self.description else ""
        return (f"pin  {self.pin_type.name:<6} {self.direction.name:<7} "
                f"{self.field_name} ({dims_str})  -> '{self.emblocs_name}'{desc}")


@dataclass(frozen=True)
class VarDef:
    """
    A private variable declaration in the instance struct.

    The C declaration is stored verbatim as the block compiler does not
    parse or validate it.  Order relative to PinSpecs is preserved in
    BlockSpec.struct_members.

    Fields:
        field_name -- the first identifier in the C declaration, extracted
                      by the parser for reference; the full declaration is
                      in c_decl.
        c_decl     -- the full C declaration string, e.g. "float error_integral"
                      (semicolon not included; stored without it)
    """
    field_name: str
    c_decl:     str

    def describe(self) -> str:
        return f"var  {self.c_decl};"


@dataclass(frozen=True)
class FunctDef:
    """
    A function exported by the block.

    Fields:
        name        -- EMBLOCS-visible function name (e.g. "update", "read")
        description -- /// annotation text, or empty string if none
    """
    name:        str
    description: str = ""

    def describe(self) -> str:
        desc = f"  # {self.description}" if self.description else ""
        return f"function  {self.name}{desc}"


@dataclass
class BlockSpec:
    """
    The complete description of a block as derived from a .bloc file.
    Contains unresolved declarations (PinSpecs) that may reference parameter
    names.  Resolving a BlockSpec against concrete parameter values produces
    a BlockDef (defined elsewhere, once resolution is implemented).

    Fields:
        source_path    -- path to the .bloc file this was parsed from
        name           -- block name from the 'block' declaration
        description    -- /// text from the 'block' declaration
        struct_members -- ordered list of PinSpec and VarDef objects,
                          preserving the declaration order from the .bloc file
                          (which determines C struct field order)
        functions      -- ordered list of FunctDef objects
        params         -- ordered list of ParamSpec objects (empty for now;
                          ParamSpec is not yet defined)
    """
    source_path:    str
    name:           str            = ""
    description:    str            = ""
    struct_members: list           = field(default_factory=list)
    functions:      list[FunctDef] = field(default_factory=list)
    params:         list           = field(default_factory=list)

    def describe(self) -> str:
        """Return a human-readable multi-line description for debugging."""
        lines = []
        lines.append(f"BlockSpec: {self.name}  ({self.source_path})")
        if self.description:
            for dline in self.description.splitlines():
                lines.append(f"  description: {dline}")
        for m in self.struct_members:
            lines.append(f"  {m.describe()}")
        for f_ in self.functions:
            lines.append(f"  {f_.describe()}")
        return "\n".join(lines)
