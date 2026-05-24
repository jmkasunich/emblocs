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
    PinType.BOOL:  "bl_pin_bit_t",
    PinType.U32:   "bl_pin_u32_t",
    PinType.S32:   "bl_pin_s32_t",
    PinType.FLOAT: "bl_pin_float_t",
    PinType.RAW:   "bl_pin_raw_t",
}

SIG_C_TYPES = {
    PinType.BOOL:  "bl_bit_t",
    PinType.U32:   "bl_u32_t",
    PinType.S32:   "bl_s32_t",
    PinType.FLOAT: "bl_float_t",
}

def _make_index_vars(n: int) -> tuple[str, ...]:
    """Generate index variable names i, j, k, ... for n dimensions."""
    return tuple(chr(ord('i') + k) for k in range(n))

def paramspec_as_h_template(lines: list[str], param: ParamSpec) -> None:
    lines.append(f"#ifndef {param.name}")
    lines.append(f"#define {param.name} ({param.default})")
    lines.append(f"#endif")

def pinspec_as_instance_member(lines: list[str], pinspec: PinSpec) -> None:
    c_type = PIN_C_TYPES[pinspec.pin_type]
    if pinspec.dims:
        dim_sizes = "".join(f"[{d.size_expr}]" for d in pinspec.dims)
        lines.append(f"    {c_type} {pinspec.field_name}{dim_sizes};")
    else:
        lines.append(f"    {c_type} {pinspec.field_name};")

def vardef_as_instance_member(lines: list[str], vardef: VarDef) -> None:
    lines.append(f"    {vardef.c_decl}")

def pinspec_as_macro(lines: list[str], pinspec: PinSpec) -> None:
    macro_name = pinspec.field_name.upper()
    lines.append(f"#define p{macro_name}  (self->{pinspec.field_name})")
    if not pinspec.dims:
        lines.append(f"#define {macro_name}  (*self->{pinspec.field_name})")
    else:
        vars = _make_index_vars(len(pinspec.dims))
        args = ", ".join(vars)
        indices = "".join(f"[{v}]" for v in vars)
        lines.append(f"#define {macro_name}({args})  (*(self->{pinspec.field_name}{indices}))")

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

def bl_mangle_as_macro(lines: list[str]) -> None:
    lines.append(f"#define BL_CONCAT(a, b)   a##b")
    lines.append(f"#define BL_CONCAT2(a, b)  BL_CONCAT(a,b)")
    lines.append(f"#define BL_MANGLE(name)   BL_CONCAT2(BL_BLOCK_NAME, _##name)")
    lines.append(f"")

def blockspec_as_h_template(lines: list[str], blockspec: BlockSpec) -> None:
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
            paramspec_as_h_template(lines, param)
        lines.append(f"")
    # mangling macros
    bl_mangle_as_macro(lines);
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
    if not pinspec.dims:
        lines.append(f"    //   {macro_name} or *p{macro_name}")
    else:
        vars = _make_index_vars(len(pinspec.dims))
        args = ", ".join(vars)
        indices = "".join(f"[{v}]" for v in vars)
        ranges = ", ".join(f"{v}=0..{d.size_expr}" for v, d in zip(vars, pinspec.dims))
        lines.append(f"    //   {macro_name}({args})  or  *p{macro_name}{indices}  for {ranges}")

def functspec_as_stub(lines: list[str], functspec: FunctSpec, blockspec: BlockSpec) -> None:
    lines.append(f"void BL_MANGLE({functspec.name})(void *instance_data, uint32_t periodns) {{")
    lines.append(f"    BL_MANGLE(t) *self = (BL_MANGLE(t) *)instance_data;")
    lines.append(f"    (void)periodns;  // delete this line if periodns is used")
    lines.append(f"")
    lines.append(f"    // TODO: implement {functspec.name}")
    lines.append(f"    // Pin macros available:")
    active_conditions = []
    for stmt in blockspec.statements:
        s = stmt.statement
        if isinstance(s, PinSpec):
            update_conditions(lines, active_conditions, stmt.conditions)
            pinspec_as_inventory_comment(lines, s)
    update_conditions(lines, active_conditions, [])
    lines.append(f"}}")

C_SENTINEL = "// EMBLOCS:  DO NOT REMOVE OR EDIT ABOVE THIS LINE"

def blockspec_as_c_template(lines: list[str], blockspec: BlockSpec) -> None:
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
        lines.append(f"    {c_type} {field.name}{dim_str};")

def fielddef_as_macro(lines: list[str], field: FieldDef) -> None:
    macro_name = field.name.upper()
    lines.append(f"#define p{macro_name}  (self->{field.name})")
    if not field.dims:
        lines.append(f"#define {macro_name}  (*self->{field.name})")
    else:
        vars = _make_index_vars(len(field.dims))
        args = ", ".join(vars)
        indices = "".join(f"[{v}]" for v in vars)
        lines.append(f"#define {macro_name}({args})  (*(self->{field.name}{indices}))")

def blockdef_as_h_variant(lines: list[str], blockdef: BlockDef) -> None:
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

def blockdef_as_c_variant_preamble(lines: list[str], blockdef: BlockDef) -> None:
    block_name = blockdef.name
    # header comment — same format as variant.h
    lines.append(f"// Auto-generated by the EMBLOCS block compiler. Do not edit.")
    lines.append(f"// Source: {blockdef.orig_path}")
    lines.append(f"// Variant: {block_name}")
    lines.append(f"//   params: " + ", ".join(f"{k}={v}" for k, v in blockdef.params.items()))
    lines.append(f"")
    # BL_ macros for name mangling
    lines.append(f"#define BL_BLOCK_NAME {block_name}")
    bl_mangle_as_macro(lines);
    # concrete parameter values
    if blockdef.params:
        for name, value in blockdef.params.items():
            lines.append(f"#define {name} ({value})")
        lines.append(f"")
    # variant header include
    lines.append(f'#include "{block_name}.h"')

def blockdef_as_c_variant(lines: list[str], blockdef: BlockDef) -> None:
    ''' lines should be the lines of the <block>.c file '''
    for i, line in enumerate(lines):
        if line.rstrip() == C_SENTINEL:
            del lines[0:i+1]
            preamble = []
            blockdef_as_c_variant_preamble(preamble, blockdef)
            preamble.append(f'#line {i+2} "{Path(blockdef.abs_path).with_suffix(".c").as_posix()}"')
            lines[0:0] = preamble
            return
    raise EmblocsError(f"sentinel line not found in {Path(blockdef.abs_path).with_suffix(".c")}")

def design_as_cmake(lines: list[str], design: Design) -> None:
    stem = Path(design.source_path).stem
    lines.append(f"# Auto-generated from {stem}.blocs - Do not edit.")
    lines.append(f"")
    for name in design.block_defs:
        lines.append(f"add_library({name} OBJECT ${{CMAKE_BINARY_DIR}}/{name}.c)")
    lines.append(f"add_library({stem} OBJECT ${{CMAKE_BINARY_DIR}}/{stem}.c)")


def signal_as_c_system(lines: list[str], signal: Signal) -> None:
    c_type = SIG_C_TYPES[signal.sig_type]
    lines.append(f"{c_type} sig_{signal.name} = {signal.value};")


def pin_as_c_system_dummy(lines: list[str], pin: PinInstance) -> None:
    c_type = SIG_C_TYPES[pin.signal.sig_type]
    lines.append(f"static {c_type} {pin.dummy_name} = {pin.signal.value};")


def pin_as_c_system_initializer(lines: list[str], pin: PinInstance) -> None:
    if pin.signal.is_dummy:
        target = f"&{pin.dummy_name}"
    else:
        target = f"&sig_{pin.signal.name}"
    field_name = pin.pin_def.field.name
    if not pin.pin_def.field_indices:
        lines.append(f"    .{field_name} = {target},")
    else:
        # array pin — will be handled by block_as_c_system
        pass


def block_as_c_system(lines: list[str], block: BlockInstance) -> None:
    lines.append(f"")
    # dummy signals for unconnected pins
    for pin in block.pins.values():
        if pin.signal.is_dummy:
            pin_as_c_system_dummy(lines, pin)
    # instance struct initializer
    lines.append(f"{block.block_def.name}_t blk_{block.name} = {{")
    # group pins by field for array handling
    fields: dict[str, list[PinInstance]] = {}
    for pin in block.pins.values():
        fname = pin.pin_def.field.name
        if fname not in fields:
            fields[fname] = []
        fields[fname].append(pin)
    # emit initializers in ordered_fields order
    for field in block.block_def.ordered_fields:
        if field.pin_type is None:
            continue  # var field, not initialized here
        pins = fields.get(field.name, [])
        if not field.dims:
            # scalar pin
            if pins:
                pin = pins[0]
                target = f"&{pin.dummy_name}" if pin.signal.is_dummy else f"&sig_{pin.signal.name}"
                lines.append(f"    .{field.name} = {target},")
        else:
            # array pin — emit nested initializer
            lines.append(f"    .{field.name} = {{")
            _emit_array_initializer(lines, field, pins)
            lines.append(f"    }},")
    lines.append(f"}};")


def _emit_array_initializer(lines: list[str], field: FieldDef,
                             pins: list[PinInstance]) -> None:
    # build lookup from field_indices tuple to pin
    pin_map = {pin.pin_def.field_indices: pin for pin in pins}
    if len(field.dims) == 1:
        for i in range(field.dims[0]):
            pin = pin_map.get((i,))
            target = _pin_target(pin)
            lines.append(f"        {target},")
    elif len(field.dims) == 2:
        for i in range(field.dims[0]):
            lines.append(f"        {{")
            for j in range(field.dims[1]):
                pin = pin_map.get((i, j))
                target = _pin_target(pin)
                lines.append(f"            {target},")
            lines.append(f"        }},")


def _pin_target(pin: PinInstance | None) -> str:
    if pin is None:
        return "NULL"
    if pin.signal.is_dummy:
        return f"&{pin.dummy_name}"
    return f"&sig_{pin.signal.name}"


def thread_as_c_system(lines: list[str], thread: Thread) -> None:
    lines.append(f"")
    lines.append(f"void {thread.name}(uint32_t periodns) {{")
    for func in thread.functions:
        lines.append(f"    {func.block.block_def.name}_{func.funct_def.name}(&blk_{func.block.name}, periodns);")
    lines.append(f"}}")


def design_as_c_system(lines: list[str], design: Design) -> None:
    # header comment
    lines.append(f"// Auto-generated from {Path(design.source_path).name} - Do not edit.")
    lines.append(f"")
    lines.append(f'#include "emblocs_common.h"')
    lines.append(f'#include "{Path(design.source_path).stem}.h"')
    lines.append(f"")
    # includes — one per blockdef
    for name in design.block_defs:
        lines.append(f'#include "{name}.h"')
    lines.append(f"")
    # real signals
    if design.signals:
        lines.append(f"// signals")
        for signal in design.signals.values():
            signal_as_c_system(lines, signal)
        lines.append(f"")
    # block instances with their dummy signals
    lines.append(f"// block instances")
    for block in design.blocks.values():
        block_as_c_system(lines, block)
    lines.append(f"")
    # thread functions
    if design.threads:
        lines.append(f"// threads")
        for thread in design.threads.values():
            thread_as_c_system(lines, thread)

def design_as_h_system(lines: list[str], design: Design) -> None:
    stem = Path(design.source_path).stem
    guard = stem.upper() + "_H"
    # header comment
    lines.append(f"// Auto-generated from {Path(design.source_path).name} - Do not edit.")
    lines.append(f"")
    # include guard
    lines.append(f"#ifndef {guard}")
    lines.append(f"#define {guard}")
    lines.append(f"")
    lines.append(f"#include <stdint.h>")
    lines.append(f"")
    # thread function prototypes
    if design.threads:
        for thread in design.threads.values():
            lines.append(f"void {thread.name}(uint32_t periodns);")
        lines.append(f"")
    # close include guard
    lines.append(f"#endif // {guard}")


def write_file_if_changed(path: Path, lines: list[str]) -> bool:
    """Write lines to path only if content has changed.
    Returns True if the file was written, False if unchanged."""
    new_content = "\n".join(lines) + "\n"
    if path.exists():
        existing = path.read_text().replace("\r\n", "\n")
        if new_content == existing:
            return False
    path.write_text(new_content, newline="\n")
    return True

# ---------------------------------------------------------------------------
# Test driver
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "-b":
        design = parse_blocs_file(sys.argv[2])
        if design is not None:
            print("\n-----------------------------------------------------\n")
            print(design.describe())
            print("\n-----------------------------------------------------\n")
            lines = []
            design_as_blocs(lines, design)
            print("\n".join(lines))
            print("\n-----------------------------------------------------\n")
        else:
            print("Parsing failed due to errors.", file=sys.stderr)

    elif len(sys.argv) >= 3 and sys.argv[1] == "-s":
        design = parse_blocs_file(sys.argv[2])
        if design is not None:
            print("\n-----------------------------------------------------\n")
            print(design.describe())
            print("\n-----------------------------------------------------\n")
            header = []
            design_as_h_system(header, design)
            print("\n".join(header))
            print("\n-----------------------------------------------------\n")
            source = []
            design_as_c_system(source, design)
            print("\n".join(source))
            print("\n-----------------------------------------------------\n")
        else:
            print("Parsing failed due to errors.", file=sys.stderr)

    elif len(sys.argv) >= 3 and sys.argv[1] == "-t":
        block_spec = parse_bloc_file(sys.argv[2])
        if block_spec is not None:
            print("\n-----------------------------------------------------\n")
            print(block_spec.describe())
            print("\n-----------------------------------------------------\n")
            header=[]
            blockspec_as_h_template(header, block_spec)
            print("\n".join(header))
            print("\n-----------------------------------------------------\n")
            source=[]
            blockspec_as_c_template(source, block_spec)
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
                blockdef_as_h_variant(header, block_def)
                print("\n".join(header))
                print("\n-----------------------------------------------------\n")
                source=[]
                blockdef_as_c_variant_preamble(source, block_def)
                print("\n".join(source))
                print("\n-----------------------------------------------------\n")
        else:
            print("Parsing failed due to errors.", file=sys.stderr)

    else:
        print(f"usage: {sys.argv[0]} -b file.blocs", file=sys.stderr)
        print(f"       {sys.argv[0]} -t file.bloc", file=sys.stderr)
        print(f"       {sys.argv[0]} -v file.bloc blockdef_name [parameter=value]", file=sys.stderr)
        sys.exit(1)
