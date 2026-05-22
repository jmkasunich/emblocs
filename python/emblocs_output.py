# blocs_output.py
# Generate .blocs system definition file from a Design object.

#import sys
#from collections import namedtuple
#from pathlib import Path
#from expressions import evaluate, ExpressionError

from emblocs import (
    EmblocsError,
    Design, DesignObject,
    BlockDef, Signal, Thread,
    PinType,
    BlockInstance, PinInstance, FunctInstance,
)
from operator import attrgetter


TYPE_LABELS = {
    PinType.BOOL:  "bool",
    PinType.U32:   "u32",
    PinType.S32:   "s32",
    PinType.FLOAT: "float",
    PinType.RAW:   "raw",
}

def canonical_blockdef(lines: list[str], blockdef: BlockDef ) -> None:
    fields = []
    fields.append(f"blockdef")
    fields.append(f"{blockdef.name}")
    fields.append(f"{blockdef.source_path}")
    for key in sorted(blockdef.params):
        fields.append(f"{key}={str(blockdef.params[key])}")
    lines.append(" ".join(fields))

def canonical_block(lines: list[str], block: BlockInstance ) -> None:
    fields = []
    fields.append(f"block")
    fields.append(f"{block.name}")
    fields.append(f"{block.block_def.name}")
    lines.append(" ".join(fields))
    for key in sorted(block.pins):
        pin = block.pins[key]
        if pin.signal.is_dummy and pin.signal.value != 0:
            lines.append(f"{pin.full_name} ={pin.signal.value}")

def canonical_signal(lines: list[str], signal: Signal ) -> None:
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

def canonical_thread(lines: list[str], thread: Thread ) -> None:
    fields = []
    fields.append(f"thread")
    fields.append(f"{thread.name}")
    fields.append(f"{str(thread.period_ns)}")
    for funct in thread.functions:
        fields.append(f"+{funct.full_name}")
    lines.append(" ".join(fields))

def canonical_blocs(design: Design) -> list[str]:
    lines = []
    lines.append(f"# Design source: {design.source_path}")
    for key in sorted(design.block_defs):
        canonical_blockdef(lines, design.block_defs[key])
    for key in sorted(design.blocks):
        canonical_block(lines, design.blocks[key])
    for key in sorted(design.signals):
        canonical_signal(lines, design.signals[key])
    for key in sorted(design.threads):
        canonical_thread(lines, design.threads[key])
    return lines




# ---------------------------------------------------------------------------
# Test driver
# ---------------------------------------------------------------------------

from blocs_parser import parse_blocs_file
import sys

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <file.blocs>", file=sys.stderr)
        sys.exit(1)

    design = parse_blocs_file(sys.argv[1])
    if design is not None:
        print(design.describe())
        lines = canonical_blocs(design)
        print("\n".join(lines))
    else:
        print("Parsing failed due to errors.", file=sys.stderr)
