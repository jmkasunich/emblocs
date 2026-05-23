# emblocs_output.py
# Generate various output formats from emblocs objects.
#
# Most functions in this file take a list of strings (by convention
# called 'lines') and an object as input, then append their output
# lines to the list of strings.  The expectation is that the final
# caller will do "\n".join(lines) to create a single string for
# output or other processing.


from emblocs import (
    EmblocsError,
    Design, DesignObject,
    BlockDef, FieldDef,Signal, Thread,
    PinType,
    BlockInstance, PinInstance, FunctInstance,
    BlockSpec, ParamSpec, PinSpec, VarDef, FunctSpec,
)
from bloc_parser import parse_bloc_file
from bloc_resolver import resolve
from blocs_parser import parse_blocs_file
from parse_common import ctx

import sys
from pathlib import Path
from operator import attrgetter


TYPE_LABELS = {
    PinType.BOOL:  "bool",
    PinType.U32:   "u32",
    PinType.S32:   "s32",
    PinType.FLOAT: "float",
    PinType.RAW:   "raw",
}

def blockdef_as_blocs(lines: list[str], blockdef: BlockDef ) -> None:
    fields = []
    fields.append(f"blockdef")
    fields.append(f"{blockdef.name}")
    fields.append(f"{blockdef.orig_path}")
    for key in sorted(blockdef.params):
        fields.append(f"{key}={str(blockdef.params[key])}")
    lines.append(" ".join(fields))

def block_as_blocs(lines: list[str], block: BlockInstance ) -> None:
    fields = []
    fields.append(f"block")
    fields.append(f"{block.name}")
    fields.append(f"{block.block_def.name}")
    lines.append(" ".join(fields))
    for key in sorted(block.pins):
        pin = block.pins[key]
        if pin.signal.is_dummy and pin.signal.value != 0:
            lines.append(f"{pin.full_name} ={pin.signal.value}")

def signal_as_blocs(lines: list[str], signal: Signal ) -> None:
    fields = []
    fields.append(f"signal")
    fields.append(f"{signal.name}")
    fields.append(f"{TYPE_LABELS[signal.sig_type]}")
    fields.append(f"={str(signal.value)}")
    if signal.driver is not None:
        fields.append(f"  +{signal.driver.full_name}")
    for pin in sorted(signal.readers, key=attrgetter("full_name")):
        fields.append(f"+{pin.full_name}")
    lines.append(" ".join(fields))

def thread_as_blocs(lines: list[str], thread: Thread ) -> None:
    fields = []
    fields.append(f"thread")
    fields.append(f"{thread.name}")
    fields.append(f"{str(thread.period_ns)}")
    for funct in thread.functions:
        fields.append(f"+{funct.full_name}")
    lines.append(" ".join(fields))

def design_as_blocs(lines: list[str], design: Design) -> None:
    lines.append(f"# Design source: {design.source_path}")
    for key in sorted(design.block_defs):
        blockdef_as_blocs(lines, design.block_defs[key])
    for key in sorted(design.blocks):
        block_as_blocs(lines, design.blocks[key])
    for key in sorted(design.signals):
        signal_as_blocs(lines, design.signals[key])
    for key in sorted(design.threads):
        thread_as_blocs(lines, design.threads[key])


PIN_C_TYPES = {
    PinType.BOOL:  "pin_bool_t",
    PinType.U32:   "pin_u32_t",
    PinType.S32:   "pin_s32_t",
    PinType.FLOAT: "pin_float_t",
    PinType.RAW:   "pin_raw_t",
}

def paramspec_as_template_h(lines: list[str], param: ParamSpec) -> None:
    lines.append(f"#ifndef {param.name}")
    lines.append(f"#define {param.name} ({param.default})")
    lines.append(f"#endif")

def pinspec_as_instance_member(lines: list[str], pinspec: PinSpec) -> None:
    c_type = PIN_C_TYPES[pinspec.pin_type]
    if pinspec.dims:
        dim_sizes = "".join(f"[{d.size_expr}]" for d in pinspec.dims)
        lines.append(f"    {c_type} *{pinspec.field_name}{dim_sizes};")
    else:
        lines.append(f"    {c_type} *{pinspec.field_name};")

def vardef_as_instance_member(lines: list[str], vardef: VarDef) -> None:
    lines.append(f"    {VarDef.c_decl}")

def pinspec_as_macro(lines: list[str], pinspec: PinSpec) -> None:
    macro_name = pinspec.field_name.upper()
    if pinspec.dims:
        lines.append(f"#define {macro_name}  (self->{pinspec.field_name})")
    else:
        lines.append(f"#define {macro_name}  (*self->{pinspec.field_name})")

def update_conditions(lines: list[str], active_conditions: list[str], new_conditions: list[str]) -> None:
    # find where the two lists first diverge
    common = 0
    while (common < len(active_conditions) and
           common < len(new_conditions) and
           active_conditions[common] == new_conditions[common]):
        common += 1
    # close all levels beyond the common prefix
    for _ in range(len(active_conditions) - common):
        lines.append(f"#endif")
        active_conditions.pop()
    # open any new levels
    for cond in new_conditions[common:]:
        lines.append(f"#if ({cond})")
        active_conditions.append(cond)

def blockspec_as_template_h(lines: list[str], blockspec: BlockSpec) -> None:
    block_name = blockspec.name
    guard = block_name.upper() + "_H"
    # header comment
    lines.append(f"// Auto-generated by the EMBLOCS block compiler.")
    lines.append(f"// Do not edit this file.")
    lines.append(f"// Source: {Path(blockspec.abs_path).name}")
    lines.append(f"")
    # include guard
    lines.append(f"#ifndef {guard}")
    lines.append(f"#define {guard}")
    lines.append(f"")
    # fixed include
    lines.append(f'#include "emblocs_comp.h"')
    lines.append(f"")
    # default parameter defines
    if blockspec.params:
        lines.append(f"// set default parameter values if not supplied")
        for param in blockspec.params:
            paramspec_as_template_h(lines, param)
        lines.append(f"")
    # mangling macros
    lines.append(f"#define BL_CONCAT(a, b)  a##b")
    lines.append(f"#define BL_MANGLE(name)  BL_CONCAT(BL_BLOCK_NAME, _##name)")
    lines.append(f"")
    # instance struct
    lines.append(f"// define instance structure")
    lines.append(f"typedef struct {{")
    active_conditions = []
    for stmt in blockspec.statements:
        s = stmt.statement
        # manage #if blocks
        update_conditions(lines, active_conditions, stmt.conditions)
        # emit the field
        if isinstance(s, PinSpec):
            pinspec_as_instance_member(lines, s)
        elif isinstance(s, VarDef):
            vardef_as_instance_member(lines, s)
    # close any remaining open #if blocks
    update_conditions(lines, active_conditions, [])
    lines.append(f"}} BL_MANGLE(t);")
    lines.append(f"")
    # convenience macros
    active_conditions = []
    for stmt in blockspec.statements:
        s = stmt.statement
        if isinstance(s, PinSpec):
            # manage #if blocks
            update_conditions(lines, active_conditions, stmt.conditions)
            # emit macro
            pinspec_as_macro(lines, s)
    # close any remaining open #if blocks
    update_conditions(lines, active_conditions, [])
    lines.append(f"")
    # close include guard
    lines.append(f"#endif // {guard}")


def pinspec_as_inventory_comment(lines: list[str], pinspec: PinSpec) -> None:
    macro_name = pinspec.field_name.upper()
    if pinspec.dims:
        dim_sizes = "".join(f"[{d.size_expr}]" for d in pinspec.dims)
        lines.append(f"    //   {macro_name}{dim_sizes}")
    else:
        lines.append(f"    //   {macro_name}")

def functspec_as_stub(lines: list[str], functspec: FunctSpec, blockspec: BlockSpec) -> None:
    lines.append(f"void BL_MANGLE({functspec.name})(void *instance_data, uint32_t periodns) {{")
    lines.append(f"    BL_MANGLE(t) *self = (BL_MANGLE(t) *)instance_data;")
    lines.append(f"    (void)periodns;  // delete this line if periodns is used")
    lines.append(f"")
    lines.append(f"    // TODO: implement {functspec.name}")
    lines.append(f"    // Pins available:")
    active_conditions = []
    for stmt in blockspec.statements:
        s = stmt.statement
        if isinstance(s, PinSpec):
            update_conditions(lines, active_conditions, stmt.conditions)
            pinspec_as_inventory_comment(lines, s)
    update_conditions(lines, active_conditions, [])
    lines.append(f"}}")

C_SENTINEL = "// EMBLOCS:  DO NOT REMOVE OR EDIT ABOVE THIS LINE"

def blockspec_as_template_c(lines: list[str], blockspec: BlockSpec) -> None:
    block_name = blockspec.name
    # header comment
    lines.append(f"// Generated once by the EMBLOCS block compiler.")
    lines.append(f"// Edit freely - this file will not be overwritten.")
    lines.append(f"// Source: {Path(blockspec.abs_path).name}")
    lines.append(f"")
    # include
    lines.append(f'#include "{block_name}.h"')
    lines.append(f"")
    lines.append(C_SENTINEL)
    lines.append(f"")
    # one stub per function, in declaration order, respecting conditions
    active_conditions = []
    for stmt in blockspec.statements:
        s = stmt.statement
        if isinstance(s, FunctSpec):
            update_conditions(lines, active_conditions, stmt.conditions)
            functspec_as_stub(lines, s, blockspec)
            lines.append(f"")
    update_conditions(lines, active_conditions, [])


def fielddef_as_instance_member(lines: list[str], field: FieldDef) -> None:
    if field.c_decl is not None:
        lines.append(f"    {field.c_decl}")
    else:
        c_type = PIN_C_TYPES[field.pin_type]
        dim_str = "".join(f"[{d}]" for d in field.dims)
        lines.append(f"    {c_type} *{field.name}{dim_str};")

def fielddef_as_macro(lines: list[str], field: FieldDef) -> None:
    macro_name = field.name.upper()
    if field.dims:
        lines.append(f"#define {macro_name}  (self->{field.name})")
    else:
        lines.append(f"#define {macro_name}  (*self->{field.name})")

def blockdef_as_variant_h(lines: list[str], blockdef: BlockDef) -> None:
    block_name = blockdef.name
    guard = block_name.upper() + "_H"
    # header comment
    lines.append(f"// Auto-generated by the EMBLOCS block compiler. Do not edit.")
    lines.append(f"// Source: {blockdef.orig_path}")
    lines.append(f"// Variant: {block_name}")
    lines.append(f"//   params: " + ", ".join(f"{k}={v}" for k, v in blockdef.params.items()))
    lines.append(f"")
    # include guard
    lines.append(f"#ifndef {guard}")
    lines.append(f"#define {guard}")
    lines.append(f"")
    # fixed include
    lines.append(f'#include "emblocs_comp.h"')
    lines.append(f"")
    # instance struct — no #if blocks, no BL_ symbols, all concrete
    lines.append(f"typedef struct {{")
    for field in blockdef.ordered_fields:
        fielddef_as_instance_member(lines, field)
    lines.append(f"}} {block_name}_t;")
    lines.append(f"")
    # convenience macros
    for field in blockdef.ordered_fields:
        if field.pin_type is not None:
            fielddef_as_macro(lines, field)
    lines.append(f"")
    # close include guard
    lines.append(f"#endif // {guard}")

def blockdef_as_variant_c_preamble(lines: list[str], blockdef: BlockDef) -> None:
    block_name = blockdef.name
    # header comment — same format as variant.h
    lines.append(f"// Auto-generated by the EMBLOCS block compiler. Do not edit.")
    lines.append(f"// Source: {blockdef.orig_path}")
    lines.append(f"// Variant: {block_name}")
    lines.append(f"//   params: " + ", ".join(f"{k}={v}" for k, v in blockdef.params.items()))
    lines.append(f"")
    # BL_ macros for name mangling
    lines.append(f"#define BL_BLOCK_NAME {block_name}")
    lines.append(f"#define BL_CONCAT(a, b)  a##b")
    lines.append(f"#define BL_MANGLE(name)  BL_CONCAT(BL_BLOCK_NAME, _##name)")
    lines.append(f"")
    # concrete parameter values
    if blockdef.params:
        for name, value in blockdef.params.items():
            lines.append(f"#define {name} ({value})")
        lines.append(f"")
    # variant header include
    lines.append(f'#include "{block_name}.h"')

def blockdef_as_variant_c(lines: list[str], blockdef: BlockDef) -> None:
    ''' lines should be the lines of the <block>.c file '''
    for i, line in enumerate(lines):
        if line.rstrip() == C_SENTINEL:
            del lines[0:i+1]
            preamble = []
            blockdef_as_variant_c_preamble(preamble, blockdef)
            preamble.append(f'#line {i+2} "{Path(blockdef.abs_path).with_suffix(".c")}"')
            lines[0:0] = preamble
            return
    raise EmblocsError(f"sentinel line not found in {Path(blockdef.abs_path).with_suffix(".c")}")

def write_file_if_changed(path: Path, lines: list[str]) -> bool:
    """Write lines to path only if content has changed.
    Returns True if the file was written, False if unchanged."""
    new_content = "\n".join(lines)
    existing = path.read_text() if path.exists() else None
    if new_content != existing:
        path.write_text(new_content)
        return True
    return False

# ---------------------------------------------------------------------------
# Test driver
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "-b":
        design = parse_blocs_file(sys.argv[2])
        if design is not None:
            print(design.describe())
            lines = []
            design_as_blocs(lines, design)
            print("\n".join(lines))
        else:
            print("Parsing failed due to errors.", file=sys.stderr)

    elif len(sys.argv) >= 3 and sys.argv[1] == "-t":
        block_spec = parse_bloc_file(sys.argv[2])
        if block_spec is not None:
            #print("\n-----------------------------------------------------\n")
            #print(block_spec.describe())
            print("\n-----------------------------------------------------\n")
            header=[]
            blockspec_as_template_h(header, block_spec)
            print("\n".join(header))
            print("\n-----------------------------------------------------\n")
            source=[]
            blockspec_as_template_c(source, block_spec)
            print("\n".join(source))
            print("\n-----------------------------------------------------\n")
        else:
            print("Parsing failed due to errors.", file=sys.stderr)

    elif len(sys.argv) >= 4 and sys.argv[1] == "-v":
        params = {}
        for arg in sys.argv[4:]:
            if "=" not in arg:
                print(f"error: expected NAME=VALUE, got {arg!r}", file=sys.stderr)
                sys.exit(1)
            k, _, v = arg.partition("=")
            params[k] = int(v)
        block_spec = parse_bloc_file(sys.argv[2])
        if block_spec is not None:
            ctx.push(source="test")
            block_def = resolve(block_spec, sys.argv[3], sys.argv[2], params)
            if block_def is not None:
                print("\n-----------------------------------------------------\n")
                print(block_def.describe())
                print("\n-----------------------------------------------------\n")
                header = []
                blockdef_as_variant_h(header, block_def)
                print("\n".join(header))
                print("\n-----------------------------------------------------\n")
                source=[]
                blockdef_as_variant_c_preamble(source, block_def)
                print("\n".join(source))
                print("\n-----------------------------------------------------\n")
        else:
            print("Parsing failed due to errors.", file=sys.stderr)

    else:
        print(f"usage: {sys.argv[0]} -b file.blocs", file=sys.stderr)
        print(f"       {sys.argv[0]} -t file.bloc", file=sys.stderr)
        print(f"       {sys.argv[0]} -v file.bloc blockdef_name [parameter=value]", file=sys.stderr)
        sys.exit(1)
