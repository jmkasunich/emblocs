# parse_common.py
# Shared infrastructure for EMBLOCS parsers.
# Provides Severity, ErrorContext, and report() used for
# error reporting.
# Also provides Token (named tuple) and tokenize_line()
# for breaking source lines into Tokens tagged with
# line and column.

from __future__ import annotations

import sys
from collections import namedtuple
from dataclasses import dataclass, field
from enum import Enum, auto
import re


# ---------------------------------------------------------------------------
# Sentinel for explicitly omitting a field from error output
# ---------------------------------------------------------------------------

class _Omit:
    """
    Sentinel value meaning "explicitly omit this field from error output".
    Use the module-level OMIT constant rather than instantiating this class.
    """
    def __repr__(self) -> str:
        return "OMIT"

OMIT = _Omit()


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

Token = namedtuple("Token", ["text", "line", "column"])


# ---------------------------------------------------------------------------
# Severity
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


# ---------------------------------------------------------------------------
# Error context
# ---------------------------------------------------------------------------

@dataclass
class ErrorContext:
    """
    Tracks the current source location and error counts for a parse operation.

    Fields:
        source  -- source identifier (file path, "interactive", etc.), or None
        line    -- current default line number, or None
        column  -- current default column number, or None
        error_count   -- number of errors reported in this context
        warning_count -- number of warnings reported in this context
        info_count    -- number of info messages reported in this context
    """
    source:        str | None = None
    line:          int | None = None
    column:        int | None = None
    error_count:   int        = 0
    warning_count: int        = 0
    info_count:    int        = 0

    def summarize(self) -> None:
        """Print a summary of error/warning/info counts to stderr."""
        source_str = self.source if self.source else "<unknown>"
        print(f"{source_str}: {self.error_count} error(s), "
              f"{self.warning_count} warning(s), "
              f"{self.info_count} info(s)",
              file=sys.stderr)

    def no_errors(self) -> bool:
        """Return True if no errors were reported in this context."""
        return self.error_count == 0

    def clean(self) -> bool:
        """Return True if no errors or warnings were reported in this context."""
        return self.error_count == 0 and self.warning_count == 0

# Context stack -- push when entering a new file, pop when leaving
_context_stack: list[ErrorContext] = []

def push_context(source: str | None = None,
                 line: int | None = None,
                 column: int | None = None) -> ErrorContext:
    """Push a new ErrorContext onto the stack and return it."""
    ctx = ErrorContext(source=source, line=line, column=column)
    _context_stack.append(ctx)
    return ctx

def pop_context() -> ErrorContext:
    """Pop and return the current ErrorContext."""
    return _context_stack.pop()

def current_context() -> ErrorContext:
    """Return the current ErrorContext without removing it."""
    if not _context_stack:
        raise RuntimeError("report() called with no active ErrorContext; "
                           "call push_context() first")
    return _context_stack[-1]


# ---------------------------------------------------------------------------
# Error reporting
# ---------------------------------------------------------------------------

def report(severity: Severity,
           message:  str,
           source:   str | _Omit | None = None,
           lineno:   int | _Omit | None = None,
           column:   int | _Omit | None = None,
           token:    Token | None       = None) -> None:
    """
    Print a diagnostic message and update the current context's counters.

    Location resolution priority for each field:
        source: explicit arg > current_context().source  (OMIT to suppress)
        lineno: token.line  > explicit arg > current_context().line  (OMIT to suppress)
        column: token.column > explicit arg > current_context().column (OMIT to suppress)

    FATAL severity prints the message and calls sys.exit(1).
    All others return normally.
    """
    ctx = current_context()

    # resolve source
    if source is OMIT:
        resolved_source = None
    elif source is not None:
        if not isinstance(source, str):
            raise TypeError(f"source must be str, None, or OMIT, "
                            f"got {type(source)!r}")
        resolved_source = source
    else:
        resolved_source = ctx.source

    # resolve lineno
    if lineno is OMIT:
        resolved_lineno = None
    elif token is not None:
        resolved_lineno = token.line
    elif lineno is not None:
        if not isinstance(lineno, int):
            raise TypeError(f"lineno must be int, None, or OMIT, "
                            f"got {type(lineno)!r}")
        resolved_lineno = lineno
    else:
        resolved_lineno = ctx.line

    # resolve column
    if column is OMIT:
        resolved_column = None
    elif token is not None:
        resolved_column = token.column
    elif column is not None:
        if not isinstance(column, int):
            raise TypeError(f"column must be int, None, or OMIT, "
                            f"got {type(column)!r}")
        resolved_column = column
    else:
        resolved_column = ctx.column

    # build location prefix
    location = ""
    if resolved_source is not None:
        location = resolved_source
        if resolved_lineno is not None:
            location += f":{resolved_lineno}"
            if resolved_column is not None:
                location += f":{resolved_column}"
        location += ": "

    label = _SEVERITY_LABEL[severity]
    print(f"{location}{label}: {message}", file=sys.stderr)

    # update counters
    if severity == Severity.ERROR:
        ctx.error_count += 1
    elif severity == Severity.WARNING:
        ctx.warning_count += 1
    elif severity == Severity.INFO:
        ctx.info_count += 1

    if severity == Severity.FATAL:
        sys.exit(1)


# ---------------------------------------------------------------------------
# Tokenizer
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
