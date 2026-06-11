#!/usr/bin/env python3
# blocs_compiler.py
# Given foo.blocs, create complete system foo.c, foo.h and foo.cmake,
# as well as *.c and *.c for each blockdef in the .blocs file
#
# Usage: blocs_compiler.py file.blocs build_dir/ [-c path/to/emblocs.json]

from __future__ import annotations
from pathlib import Path
import sys
import json

from parse_common import ctx, OMIT, short_path
from blocs_parser import parse_blocs_file, set_get_block_spec
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


def find_config(start: Path) -> Path | None:
    """Search upward from start directory for emblocs.json."""
    current = start
    while True:
        candidate = current / "emblocs.json"
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            return None
        current = parent


def load_config(config_path: Path) -> dict:
    """Load and validate emblocs.json, returning the config dict."""
    ctx.push(source=config_path.as_posix())
    config = {}
    try:
        raw = json.loads(config_path.read_text())
    except json.JSONDecodeError as e:
        ctx.error(f"JSON parse error: {e.msg}", lineno=e.lineno, column=e.colno)
        ctx.summarize()
        ctx.pop()
        return config
    # extract and validate bloc_search_paths
    paths = raw.get("bloc_search_paths", [])
    if not isinstance(paths, list):
        ctx.error(f"'bloc_search_paths' must be a JSON array")
    else:
        valid_paths = ["."]  # always start with dir containing the .blocs file
        for i, entry in enumerate(paths):
            if not isinstance(entry, str):
                ctx.error(f"'bloc_search_paths' entry {i} must be a string")
                continue
            valid_paths.append(entry)
        if valid_paths:
            config["bloc_search_paths"] = valid_paths
        else:
            ctx.info(f"no bloc_search_paths found in config")
    ctx.summarize()
    ctx.pop()
    return config


_bloc_paths: list[Path] = []

def get_blockspec(name: str, design: Design) -> BlockSpec | None:
    '''
    Callback for blockdef command in blocs_parser.py.
    Verifies that the named .bloc file exists in the _bloc_paths
    search path and that the corresponding .h and .c files exist
    and are newer than the .bloc file, then calls parse_bloc_file
    to create a valid BlockSpec.
    Returns the BlockSpec, or None on error
    '''
    # is BlockSpec already in the Design?
    if name in design.block_specs:
        # yes, use it
        return design.block_specs[name]
    # no, validate .bloc file
    bloc_path = find_bloc_file(name)
    if bloc_path is None:
        ctx.error(f"'{name}.bloc' not found on block search path")
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
        ctx.info(f"run bloc_compiler.py on {bloc_path.name} and/or edit {c_path.name} to bring block up to date")
        return None
    # parse the bloc
    spec = parse_bloc_file(bloc_path.as_posix)
    if spec is None:
        ctx.error(f"failed to parse {short_path(bloc_path)!r}")
        return None
    # add BlockSpec to design for possible re-use
    design.add_block_spec(spec)
    return spec

def build_bloc_search_paths(blocs_dir: Path, raw_paths: list[str]) -> list[Path]:
    """
    Build and validate the .bloc file search path list.
    raw_paths entries may use $EMBLOCS prefix or be relative to blocs_dir.
    Returns list of resolved, validated Path objects.
    """
    EMBLOCS_ROOT = Path(__file__).parent.parent
    result = []
    for raw in raw_paths:
        if raw.startswith("$EMBLOCS"):
            resolved = (EMBLOCS_ROOT / raw[len("$EMBLOCS"):].lstrip("/")).resolve()
        else:
            p = Path(raw)
            if p.is_absolute():
                resolved = p.resolve()
            else:
                resolved = (blocs_dir / p).resolve()
        if not resolved.is_dir():
            ctx.error(f"bloc search path not found: {resolved}", lineno=OMIT, column=OMIT)
            continue
        result.append(resolved)
    return result

def find_bloc_file(name: str) -> Path | None:
    """
    Search _bloc_paths for a .bloc file matching the given block name.
    Returns the path of the first match, or None if not found.
    """
    filename = f"{name}.bloc"
    for directory in _bloc_paths:
        candidate = directory / filename
        if candidate.is_file():
            return candidate
    return None

def main():
    ctx.push(source="blocs_compiler.py")
    # parse arguments
    if len(sys.argv) < 3:
        print(f"usage: {sys.argv[0]} file.blocs build_dir/ [-c path/to/emblocs.json]",
              file=sys.stderr)
        sys.exit(1)
    blocs_path = Path(sys.argv[1]).resolve()
    build_dir  = Path(sys.argv[2]).resolve()
    if not blocs_path.is_file():
        ctx.fatal(f"file not found: {blocs_path}", lineno=OMIT, column=OMIT)
    if not build_dir.is_dir():
        ctx.fatal(f"build directory not found: {build_dir}", lineno=OMIT, column=OMIT)
    # find/load config
    config_path = None
    if "-c" in sys.argv:
        i = sys.argv.index("-c")
        if i + 1 >= len(sys.argv):
            ctx.error(f"-c requires a path argument", lineno=OMIT, column=OMIT)
        else:
            config_path = Path(sys.argv[i + 1]).resolve()
            if not config_path.exists():
                ctx.error(f"config file not found: {config_path}", lineno=OMIT, column=OMIT)
                config_path = None
    else:
        config_path = find_config(blocs_path.parent)
        if config_path is not None:
            ctx.info(f"using config file {config_path.as_posix()}", lineno=OMIT, column=OMIT)
        else:
            ctx.warning(f"no emblocs.json found; using defaults", lineno=OMIT, column=OMIT)
    # load config and set .bloc file search paths
    blocs_dir = blocs_path.parent
    global _bloc_paths
    _bloc_paths = build_bloc_search_paths(blocs_dir, ["."])
    if config_path is not None:
        config = load_config(config_path)
        if "bloc_search_paths" in config:
            _bloc_paths = build_bloc_search_paths(blocs_dir, config["bloc_search_paths"])
    # create an empty design
    design = Design(abs_path=blocs_path.as_posix())
    # register callback for blockdef commands
    set_get_block_spec(get_blockspec)
    # parse the .blocs file
    result = parse_blocs_file(blocs_path.as_posix(), design)
    if result is False:
        ctx.fatal(f"parsing failed: {blocs_path}", lineno=OMIT, column=OMIT)
    # generate variant files
    for name, block_def in design.block_defs.items():
        # check that <block>.c exists
        block_c = Path(block_def.abs_path).with_suffix(".c")
        if not block_c.exists():
            bloc_path = Path(block_def.abs_path)
            ctx.error(f"{block_c.name} not found alongside {bloc_path.name}; "
                      f"run 'bloc_compiler.py {bloc_path.as_posix()}' to generate it, "
                      f"then edit to implement block functions",
                      lineno=OMIT, column=OMIT)
            continue
        # generate <variant>.h
        h_lines = []
        blockdef_as_h_variant(h_lines, block_def)
        h_path = build_dir / f"{name}.h"
        if write_file_if_changed(h_path, h_lines):
            ctx.info(f"wrote {short_path(h_path)}", lineno=OMIT, column=OMIT)
        else:
            ctx.info(f"no change: {short_path(h_path)}", lineno=OMIT, column=OMIT)
        # generate <variant>.c
        c_lines = block_c.read_text().splitlines()
        blockdef_as_c_variant(c_lines, block_def)
        c_path = build_dir / f"{name}.c"
        if write_file_if_changed(c_path, c_lines):
            ctx.info(f"wrote {short_path(c_path)}", lineno=OMIT, column=OMIT)
        else:
            ctx.info(f"no change: {short_path(c_path)}", lineno=OMIT, column=OMIT)

    # generate system header
    h_lines = []
    design_as_h_system(h_lines, design)
    h_path = build_dir / f"{blocs_path.stem}.h"
    if write_file_if_changed(h_path, h_lines):
        ctx.info(f"wrote {short_path(h_path)}", lineno=OMIT, column=OMIT)
    else:
        ctx.info(f"no change: {short_path(h_path)}", lineno=OMIT, column=OMIT)

    # generate system C file
    c_lines = []
    design_as_c_system(c_lines, design)
    c_path = build_dir / f"{blocs_path.stem}.c"
    if write_file_if_changed(c_path, c_lines):
        ctx.info(f"wrote {short_path(c_path)}", lineno=OMIT, column=OMIT)
    else:
        ctx.info(f"no change: {short_path(c_path)}", lineno=OMIT, column=OMIT)

    # generate system.cmake
    cmake_lines = []
    design_as_cmake(cmake_lines, design)
    cmake_path = build_dir / f"{blocs_path.stem}.cmake"
    if write_file_if_changed(cmake_path, cmake_lines):
        ctx.info(f"wrote {short_path(cmake_path)}", lineno=OMIT, column=OMIT)
    else:
        ctx.info(f"no change: {short_path(cmake_path)}", lineno=OMIT, column=OMIT)
    ctx.summarize()
    ctx.pop()


if __name__ == "__main__":
    main()
