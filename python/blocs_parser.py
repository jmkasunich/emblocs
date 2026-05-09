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


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

Token = namedtuple("Token", ["text", "line", "column"])


# ---------------------------------------------------------------------------
# Error reporting
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Diagnostic reporting
# ---------------------------------------------------------------------------

class Severity(Enum):
    FATAL   = auto()
    ERROR   = auto()
    WARNING = auto()
    INFO    = auto()

_SEVERITY_LABEL = {
    Severity.FATAL:   "fatal error",
    Severity.ERROR:   "error",
    Severity.WARNING: "warning",
    Severity.INFO:    "info",
}
_path:          str = ""
_error_count:   int = 0
_warning_count: int = 0
_info_count:    int = 0

def report(severity, message: str,
           lineno: int = None, column: int = None,
           token: Token = None) -> None:
    """
    Print a diagnostic message and update counters.
    Mirrors the report() function in bloc_parser.py.
    """
    global _error_count, _warning_count, _info_count

    if token is not None:
        lineno = token.line
        column = token.column

    if lineno is not None and column is not None:
        location = f"{_path}:{lineno}:{column}: "
    elif lineno is not None:
        location = f"{_path}:{lineno}: "
    else:
        location = f"{_path}: "

    print(f"{location}{_SEVERITY_LABEL[severity]}: {message}", file=sys.stderr)

    if severity == Severity.ERROR:
        _error_count += 1
    elif severity == Severity.WARNING:
        _warning_count += 1
    elif severity == Severity.INFO:
        _info_count += 1
    elif severity == Severity.FATAL:
        sys.exit(1)


# ---------------------------------------------------------------------------
# Type tables
# ---------------------------------------------------------------------------

SIGNAL_TYPES = {
    "bool":  PinType.BOOL,
    "u32":   PinType.U32,
    "s32":   PinType.S32,
    "float": PinType.FLOAT,
}

# ---------------------------------------------------------------------------
# Lexer helpers
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"\S+")


def tokenize_line(line: str, line_num: int) -> list[Token]:
    """
    Tokenize a single line into whitespace-separated Token objects.

    Parameters:
        line     -- the source line to tokenize (comments already stripped)
        line_num -- 1-based line number

    Returns a list of Token objects with 1-based column numbers.
    """
    return [
        Token(
            text   = m.group(),
            line   = line_num,
            column = m.start() + 1,
        )
        for m in _TOKEN_RE.finditer(line)
    ]


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def parse_blocs(path: str) -> Design | None:
    """
    Parse a .blocs file and return a populated Design object.
    Returns None if any errors were reported.
    """
    global _path, _error_count, _warning_count, _info_count
    _path          = path
    _error_count   = 0
    _warning_count = 0
    _info_count    = 0

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

    print(f"{_path}: {_error_count} error(s), "
          f"{_warning_count} warning(s), {_info_count} info(s)",
          file=sys.stderr)

    if _error_count > 0:
        return None
    return design

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