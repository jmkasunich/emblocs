# blocs_parser.py
# Parser for .blocs system definition files.
# Reads a .blocs file and returns a Design object.

import os
import re
import sys
from enum import Enum, auto
from collections import namedtuple

from emblocs import (
    Design,
    BlockDef, BlockInstance, PinInstance, FunctInstance,
    Signal, Thread,
    PinType,
)
from bloc_parser import parse_bloc
from bloc_resolver import resolve
from parse_common import ( Token, tokenize_line,
                           Severity, report, OMIT,
                           push_context, pop_context )


# ---------------------------------------------------------------------------
# Type tables
# ---------------------------------------------------------------------------

SIGNAL_TYPES = {
    "bool":  PinType.BOOL,
    "u32":   PinType.U32,
    "s32":   PinType.S32,
    "float": PinType.FLOAT,
}


def parse_command(tokens: list[Token], design: Design) -> None:
    """
    Temporary debug stub: print tokens for each logical line.
    Will be replaced with actual command parsing.
    """
    print(f"COMMAND: {[t.text for t in tokens]}")

# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def parse_blocs(path: str) -> Design | None:
    """
    Parse a .blocs file and return a populated Design object.
    Returns None if any errors were reported.
    """
    push_context(source=path)
    design = Design(source_path=path)

    def on_command(tokens: list[Token]) -> None:
        parse_command(tokens, design)

    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        report(Severity.FATAL,
               "file is not valid UTF-8; re-save as UTF-8 and try again")
    except FileNotFoundError:
        report(Severity.FATAL, "file not found")

    logical_tokens:  list[Token] = []
    in_continuation: bool        = False

    for lineno, raw_line in enumerate(lines, start=1):
        if not raw_line.isascii():
            report(Severity.ERROR,
                   "non-ASCII character on this line; "
                   ".blocs files must be ASCII",
                   lineno=lineno)
            continue

        # strip comment: everything from # onward
        content, _sep, _comment = raw_line.partition("#")

        # strip trailing whitespace including newline
        content = content.rstrip()

        # check for line continuation
        if content.endswith("\\"):
            new_tokens = tokenize_line(content[:-1], lineno)
            logical_tokens.extend(new_tokens)
            if new_tokens:
                in_continuation = True
            # if no tokens, don't set in_continuation;
            # a blank continuation line is silently ignored
        else:
            logical_tokens.extend(tokenize_line(content, lineno))
            if logical_tokens:
                on_command(logical_tokens)
            logical_tokens  = []
            in_continuation = False

    # end of file
    if in_continuation:
        report(Severity.ERROR,
               "unexpected end of file after line continuation")
    elif logical_tokens:
        # file ended without final newline; flush remaining tokens
        on_command(logical_tokens)

    ctx = pop_context()
    ctx.summarize()
    return design if ctx.no_errors() else None

# ---------------------------------------------------------------------------
# Test driver
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <file.blocs>", file=sys.stderr)
        sys.exit(1)

    design = parse_blocs(sys.argv[1])
    if design is not None:
        print(design.describe())
    else:
        print("Parsing failed due to errors.", file=sys.stderr)