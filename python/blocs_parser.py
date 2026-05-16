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
                           current_context, pop_context,
                           read_source_file, read_source_string
                            )


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
    print(f"LINE: {[t.text for t in tokens]}")

# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------

def lex_lines(lines: list[str]) -> list[list[Token]]:
    """
    Lex a list of physical lines into logical lines.
    Handles comment stripping (#), line continuation (backslash), and
    tokenization.
    ASCII validation is assumed to have been done by read_source_xxx().

    Returns a list of logical lines, each a non-empty list of Token objects.
    Reports errors into the current context.
    """
    logical_lines:   list[list[Token]] = []
    logical_tokens:  list[Token]       = []
    in_continuation: bool              = False

    for lineno, raw_line in enumerate(lines, start=1):
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
        else:
            logical_tokens.extend(tokenize_line(content, lineno))
            if logical_tokens:
                logical_lines.append(logical_tokens)
            logical_tokens  = []
            in_continuation = False

    # end of input
    if in_continuation:
        report(Severity.ERROR,
               "unexpected end of file after line continuation",
               lineno=lineno, column=OMIT)
    elif logical_tokens:
        # file ended without final newline
        logical_lines.append(logical_tokens)

    return logical_lines


# ---------------------------------------------------------------------------
# Top-level entry points
# ---------------------------------------------------------------------------

def parse_blocs(lines: list[str]) -> Design | None:
    """
    Parse a list of source lines and return a populated Design object.
    Expects an active ErrorContext (pushed by read_source_xxx()).
    Returns None if any errors were reported.
    """
    design = Design(source_path=current_context().source)

    for tokens in lex_lines(lines):
        parse_command(tokens, design)

    return design if current_context().no_errors() else None


def parse_blocs_file(path: str) -> Design | None:
    """
    Parse a .blocs file and return a populated Design object.
    Convenience wrapper around read_source_file() and parse_blocs().
    Returns None if the file could not be read or parsing failed.
    """
    lines = read_source_file(path)
    if lines is None:
        ctx = pop_context()
        ctx.summarize()
        return None
    design = parse_blocs(lines)
    ctx = pop_context()
    ctx.summarize()
    return design


def parse_blocs_string(text: str, source: str = "<string>") -> Design | None:
    """
    Parse a .blocs string and return a populated Design object.
    Convenience wrapper around read_source_string() and parse_blocs().
    Returns None if the string contains encoding errors or parsing failed.
    """
    lines = read_source_string(text, source=source)
    if lines is None:
        ctx = pop_context()
        ctx.summarize()
        return None
    design = parse_blocs(lines)
    ctx = pop_context()
    ctx.summarize()
    return design


# ---------------------------------------------------------------------------
# Test driver
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <file.blocs>", file=sys.stderr)
        sys.exit(1)

    design = parse_blocs_file(sys.argv[1])
    if design is not None:
        print(design.describe())
    else:
        print("Parsing failed due to errors.", file=sys.stderr)
        sys.exit(1)
