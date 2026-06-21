#!/usr/bin/env python3
# blocs_compiler.py
# Given foo.blocs, create complete system foo.c, foo.h and foo.cmake,
# as well as *.c and *.c for each blockdef in the .blocs file
#
# Usage: blocs_compiler.py file.blocs build_dir/ [-c path/to/emblocs.json]

from __future__ import annotations
from pathlib import Path
import os
import sys
import argparse

from parse_common import ctx, OMIT, short_path
from blocs_parser import parse_blocs_file, set_get_block_spec, set_expand_path
from bloc_parser import parse_bloc_file
from emblocs import Design, BlockSpec
from emblocs_output import (
    write_file_if_changed,
    blockdef_as_h_variant,
    blockdef_as_c_variant,
    design_as_cmake,
    design_as_c_system,
    design_as_h_system,
)

EMBLOCS_ROOT: Path = Path(__file__).parent.parent
blocs_dir: Path = Path('.')

def get_blockspec(name: str, design: Design) -> BlockSpec | None:
    '''
    Callback for blockdef command in blocs_parser.py.
    Searches design.search_paths for the named .bloc file, verifies that
    the corresponding .h and .c files exist and are newer than the .bloc
    file, then calls parse_bloc_file to create a valid BlockSpec.
    Returns the BlockSpec, or None on error.
    '''
    # is BlockSpec already in the Design?
    if name in design.block_specs:
        # yes, use it
        return design.block_specs[name]
    # no, search for .bloc file in design.search_paths
    if not design.search_paths:
        ctx.error(f"block search path is empty; missing 'search' command(s)?",
                  lineno=OMIT, column=OMIT)
        return None
    filename = f"{name}.bloc"
    bloc_path = None
    for directory in design.search_paths:
        candidate = directory / filename
        if candidate.is_file():
            bloc_path = candidate
            break
    if bloc_path is None:
        ctx.error(f"'{name}.bloc' not found on search path")
        path_list = "\n    ".join(p.as_posix() for p in design.search_paths)
        ctx.info(f"block search path is:\n    {path_list}")
        return None
    bloc_time = bloc_path.stat().st_mtime
    # capture error count so we can check/report several errors at once
    error_count = ctx.error_count
    h_path = bloc_path.with_suffix(".h")
    if not h_path.is_file():
        ctx.error(f"block header not found: {h_path.name!r};")
    else:
        h_time = h_path.stat().st_mtime
        if h_time < bloc_time:
            ctx.error(f"{h_path.name!r} is older than {bloc_path.name!r}")
    c_path = bloc_path.with_suffix(".c")
    if not c_path.is_file():
        ctx.error(f"block source not found: {c_path.name!r}")
    else:
        c_time = c_path.stat().st_mtime
        if c_time < bloc_time:
            ctx.error(f"{c_path.name!r} is older than {bloc_path.name!r}")
    # check against captured error count
    if ctx.error_count > error_count:
        ctx.info(f"run bloc_compiler.py on {bloc_path.name} and/or"
                 f" edit {c_path.name} to bring block up to date")
        return None
    # parse the bloc
    spec = parse_bloc_file(bloc_path.as_posix())
    if spec is None:
        ctx.error(f"failed to parse {short_path(bloc_path)!r}")
        return None
    # add BlockSpec to design for possible re-use
    design.add_block_spec(spec)
    return spec

def expand_path(raw: str) -> Path | None:
    """
    Expand a raw search path string to a resolved absolute Path.
    Uses module-level blocs_dir and EMBLOCS_ROOT for resolution.
    Supports:
      . and relative paths  — resolved relative to blocs_dir
      absolute paths        — used as-is
      $EMBLOCS/...          — resolved relative to EMBLOCS_ROOT
      $VAR/...              — resolved relative to environment variable VAR
    Returns None if a referenced environment variable is not set.
    """
    normalized = raw.replace("\\", "/")
    if normalized.startswith("$"):
        var_part, sep, rest = normalized.partition("/")
        var_name = var_part[1:]  # strip the $
        if var_name == "EMBLOCS":
            base = EMBLOCS_ROOT
        else:
            val = os.environ.get(var_name)
            if val is None:
                ctx.error(f"environment variable ${var_name} is not set",
                          lineno=OMIT, column=OMIT)
                return None
            base = Path(val)
        return (base / rest).resolve() if sep else base.resolve()
    return (blocs_dir / normalized).resolve()

def generate_variants(design: Design, build_dir: Path) -> None:
    # generate variant files
    for name, block_def in design.block_defs.items():
        # generate <variant>.h
        h_lines = []
        blockdef_as_h_variant(h_lines, block_def)
        h_path = build_dir / f"{name}.h"
        if write_file_if_changed(h_path, h_lines):
            ctx.info(f"wrote {short_path(h_path)}", lineno=OMIT, column=OMIT)
        else:
            ctx.info(f"no change: {short_path(h_path)}", lineno=OMIT, column=OMIT)
        # generate <variant>.c
        block_c = Path(block_def.abs_path).with_suffix(".c")
        c_lines = block_c.read_text().splitlines()
        blockdef_as_c_variant(c_lines, block_def)
        c_path = build_dir / f"{name}.c"
        if write_file_if_changed(c_path, c_lines):
            ctx.info(f"wrote {short_path(c_path)}", lineno=OMIT, column=OMIT)
        else:
            ctx.info(f"no change: {short_path(c_path)}", lineno=OMIT, column=OMIT)

def generate_system_files(design: Design, build_dir: Path) -> None:

    stem = Path(design.abs_path).stem
    # generate system header
    h_lines = []
    design_as_h_system(h_lines, design)
    h_path = build_dir / f"{stem}.h"
    if write_file_if_changed(h_path, h_lines):
        ctx.info(f"wrote {short_path(h_path)}", lineno=OMIT, column=OMIT)
    else:
        ctx.info(f"no change: {short_path(h_path)}", lineno=OMIT, column=OMIT)

    # generate system C file
    c_lines = []
    design_as_c_system(c_lines, design)
    c_path = build_dir / f"{stem}.c"
    if write_file_if_changed(c_path, c_lines):
        ctx.info(f"wrote {short_path(c_path)}", lineno=OMIT, column=OMIT)
    else:
        ctx.info(f"no change: {short_path(c_path)}", lineno=OMIT, column=OMIT)

    # generate system.cmake
    cmake_lines = []
    design_as_cmake(cmake_lines, design)
    cmake_path = build_dir / f"{stem}.cmake"
    if write_file_if_changed(cmake_path, cmake_lines):
        ctx.info(f"wrote {short_path(cmake_path)}", lineno=OMIT, column=OMIT)
    else:
        ctx.info(f"no change: {short_path(cmake_path)}", lineno=OMIT, column=OMIT)

def main(args=None):
    ctx.push(source="blocs_compiler.py")
    # parse arguments
    parser = argparse.ArgumentParser(description="EMBLOCS system compiler")
    parser.add_argument('blocs_file', type=Path, help=".blocs system definition file")
    parser.add_argument('build_dir', type=Path, help="build output directory")
    parsed_args = parser.parse_args(args)
    blocs_path = parsed_args.blocs_file.resolve()
    build_dir = parsed_args.build_dir.resolve()
    # validate arguments
    if not blocs_path.is_file():
        ctx.error(f"file not found: {blocs_path.as_posix()!r}",
                  lineno=OMIT, column=OMIT)
    elif not build_dir.is_dir():
        ctx.error(f"build directory not found: {build_dir.as_posix()!r}",
                  lineno=OMIT, column=OMIT)
    else:
        global blocs_dir
        blocs_dir = blocs_path.parent
        # create an empty design
        design = Design(abs_path=blocs_path.as_posix())
        # register callbacks
        set_get_block_spec(get_blockspec)
        set_expand_path(expand_path)
        # parse the .blocs file
        result = parse_blocs_file(blocs_path.as_posix(), design)
        if result is False:
            ctx.error(f"parsing failed: {blocs_path.as_posix()!r}", lineno=OMIT, column=OMIT)
        else:
            # generate output
            generate_variants(design, build_dir)
            generate_system_files(design, build_dir)
    ctx.summarize()
    no_errors = ctx.no_errors()
    ctx.pop()
    return 0 if no_errors else 1

if __name__ == "__main__":
    sys.exit(main())
