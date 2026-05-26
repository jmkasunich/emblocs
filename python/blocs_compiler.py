#!/usr/bin/env python3
# blocs_compiler.py
# Given foo.blocs, create complete system foo.c, foo.h and foo.cmake,
# as well as *.c and *.c for each blockdef in the .blocs file
#
# Usage: blocs_compiler.py file.blocs build_dir/ [-c path/to/emblocs.json]

from pathlib import Path
import sys
import json

from parse_common import ctx, OMIT, short_path
from blocs_parser import parse_blocs_file, set_tags
from emblocs import Design, BlockDef
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
    # extract and validate tags
    tags = raw.get("tags", {})
    if not isinstance(tags, dict):
        ctx.error(f"'tags' must be a JSON object")
    else:
        config_dir = config_path.parent
        resolved_tags = {}
        for name, value in tags.items():
            if not isinstance(value, str):
                ctx.error(f"tag {name!r} value must be a string")
                continue
            tag_path = Path(value)
            if not tag_path.is_absolute():
                tag_path = (config_dir / tag_path).resolve()
            resolved_tags[name] = tag_path.as_posix()
        if resolved_tags:
            config["tags"] = resolved_tags
        else:
            ctx.info(f"no tags found in config")
    ctx.summarize()
    ctx.pop()
    return config


def main():
    ctx.push(source="variant_compiler.py")
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
    # load config and set tags
    if config_path is not None:
        config = load_config(config_path)
        if "tags" in config:
            set_tags(config["tags"])
    # create an empty design
    design = Design(abs_path=blocs_path.as_posix())
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
