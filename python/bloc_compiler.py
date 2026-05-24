#!/usr/bin/env python3
# bloc_compiler.py
# Tool 1: generate template .h and .c files from a .bloc block template file.
#
# Usage: bloc_compiler.py path/to/block.bloc
#
# Always writes <block>.h alongside the .bloc file, but only if the content
# has changed.  Writes <block>.c only if it does not already exist.

from pathlib import Path
import sys

from bloc_parser import parse_bloc_file
from emblocs_output import (
    write_file_if_changed,
    blockspec_as_h_template,
    blockspec_as_c_template,
)


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} path/to/block.bloc", file=sys.stderr)
        sys.exit(1)

    bloc_path = Path(sys.argv[1])
    if not bloc_path.exists():
        print(f"error: {bloc_path} not found", file=sys.stderr)
        sys.exit(1)
    if bloc_path.suffix != ".bloc":
        print(f"error: {bloc_path} is not a .bloc file", file=sys.stderr)
        sys.exit(1)

    block_spec = parse_bloc_file(str(bloc_path))
    if block_spec is None:
        print("Parsing failed due to errors.", file=sys.stderr)
        sys.exit(1)

    # generate and write <block>.h
    h_path = bloc_path.with_suffix(".h")
    h_lines = []
    blockspec_as_h_template(h_lines, block_spec)
    if write_file_if_changed(h_path, h_lines):
        print(f"wrote {h_path}")
    else:
        print(f"no change: {h_path}")

    # generate and write <block>.c only if it does not already exist
    c_path = bloc_path.with_suffix(".c")
    if c_path.exists():
        print(f"exists, not overwriting: {c_path}")
    else:
        c_lines = []
        blockspec_as_c_template(c_lines, block_spec)
        c_path.write_text("\n".join(c_lines))
        print(f"wrote {c_path}")


if __name__ == "__main__":
    main()
