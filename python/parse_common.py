# parse_common.py
# Shared infrastructure for EMBLOCS parsers.
# Provides ctx, ErrorContet, Severity and OMIT used for error reporting.
# Also provides Token (named tuple) and tokenize_line()
# for breaking source lines into Tokens tagged with line and column.

from __future__ import annotations

import sys
from collections import namedtuple
from dataclasses import dataclass, field
from enum import Enum, auto
import re
from pathlib import Path

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

class _Severity(Enum):
    FATAL   = auto()
    ERROR   = auto()
    WARNING = auto()
    INFO    = auto()

_SEVERITY_LABEL = {
    _Severity.FATAL:   "fatal error",
    _Severity.ERROR:   "error",
    _Severity.WARNING: "warning",
    _Severity.INFO:    "info",
}


# ---------------------------------------------------------------------------
# ErrorContext
# ---------------------------------------------------------------------------

class ErrorContext:
    """
    Manages a stack of source locations and error counts for nested
    parse operations.  Each push() creates a new frame for a file or
    string being parsed; pop() discards it.

    Typical usage:
        ctx.push(source="myfile.blocs")
        ...parse...
        ctx.summarize()
        ctx.pop()
    """

    @dataclass
    class _Frame:
        source:        str = "<unknown>"
        line:          int = 0
        column:        int = 0
        error_count:   int = 0
        warning_count: int = 0
        info_count:    int = 0

    def __init__(self) -> None:
        self._stack: list[ErrorContext._Frame] = []


    @property
    def source(self) -> str:
        """Return the source identifier of the current frame."""
        return self._top().source

    @property
    def line(self) -> int:
        return self._top().line

    @property
    def column(self) -> int:
        return self._top().column

    @property
    def error_count(self) -> int:
        return self._top().error_count

    @property
    def warning_count(self) -> int:
        return self._top().warning_count

    @property
    def info_count(self) -> int:
        return self._top().info_count

    # ------------------------------------------------------------------
    # Stack management
    # ------------------------------------------------------------------

    def push(self, *, source: str | None = None,
                      line: int | None = None,
                      column: int | None = None) -> None:
        """
        Push a new frame onto the context stack.
        source defaults to "<unknown>", line and column default to 0.
        """
        self._stack.append(ErrorContext._Frame(
            source = source  if source  is not None else "<unknown>",
            line   = line    if line    is not None else 0,
            column = column  if column  is not None else 0,
        ))

    def pop(self) -> None:
        """Pop and discard the current frame."""
        if not self._stack:
            raise RuntimeError("pop() called on empty context stack")
        self._stack.pop()

    def _top(self) -> _Frame:
        """Return the current top frame without removing it."""
        if not self._stack:
            raise RuntimeError("context stack is empty; call push() first")
        return self._stack[-1]

    def clear(self) -> None:
        """Clear the entire context stack. For use in tests only."""
        self._stack.clear()

    # ------------------------------------------------------------------
    # Location management
    # ------------------------------------------------------------------

    def set(self, *, token: Token = None,
                     source: str | None = None,
                     line: int | None = None,
                     column: int | None = None) -> None:
        """
        Update the current frame's line and/or column.
        If token is provided, both line and column are taken from it.
        Otherwise line and column are updated independently if not None.
        None means "leave current value unchanged".
        The current frame's source can also be updated, but you probably
        should call push() to start a new file/string context.
        """
        frame = self._top()
        if source is not None:
            frame.source = source
        if token is not None:
            frame.line   = token.line
            frame.column = token.column
        else:
            if line is not None:
                frame.line = line
            if column is not None:
                frame.column = column

    # ------------------------------------------------------------------
    # Status queries (call before pop() if result is needed)
    # ------------------------------------------------------------------

    def no_errors(self) -> bool:
        """Return True if no errors have been reported in the current frame."""
        return self._top().error_count == 0

    def is_clean(self) -> bool:
        """Return True if no errors or warnings in the current frame."""
        frame = self._top()
        return frame.error_count == 0 and frame.warning_count == 0

    def summarize(self) -> None:
        """Print error/warning/info counts for the current frame to stderr."""
        frame = self._top()
        print(f"{frame.source}: {frame.error_count} error(s), "
              f"{frame.warning_count} warning(s), "
              f"{frame.info_count} info(s)",
              file=sys.stderr)


    # ------------------------------------------------------------------
    # Private helper for error reporting
    # ------------------------------------------------------------------

    def _report(self, severity: _Severity,
               message:  str, *,
               source:   str | _Omit | None = None,
               lineno:   int | _Omit | None = None,
               column:   int | _Omit | None = None,
               token:    Token | None       = None) -> None:
        """
        Print a diagnostic message and update the current frame's counters.

        Location resolution priority for each field:
            source: explicit arg > current frame source  (OMIT to suppress)
            lineno: token.line  > explicit arg > current frame line  (OMIT to suppress)
            column: token.column > explicit arg > current frame column (OMIT to suppress)

        FATAL severity prints the message and calls sys.exit(1).
        """
        frame = self._top()
        # resolve source
        if source is OMIT:
            resolved_source = None
        elif source is not None:
            resolved_source = source
        else:
            resolved_source = frame.source
        # resolve lineno
        if lineno is OMIT:
            resolved_lineno = None
        elif token is not None:
            resolved_lineno = token.line
        elif lineno is not None:
            resolved_lineno = lineno
        else:
            resolved_lineno = frame.line
        # resolve column
        if column is OMIT:
            resolved_column = None
        elif token is not None:
            resolved_column = token.column
        elif column is not None:
            resolved_column = column
        else:
            resolved_column = frame.column
        # build location prefix
        location = ""
        if resolved_source is not None:
            location = resolved_source
            if resolved_lineno is not None:
                location += f":{resolved_lineno}"
                if resolved_column is not None:
                    location += f":{resolved_column}"
            location += ": "
        # print and update counts
        label = _SEVERITY_LABEL[severity]
        print(f"{location}{label}: {message}", file=sys.stderr)
        if severity == _Severity.ERROR:
            frame.error_count += 1
        elif severity == _Severity.WARNING:
            frame.warning_count += 1
        elif severity == _Severity.INFO:
            frame.info_count += 1
        if severity == _Severity.FATAL:
            sys.exit(1)


    # ------------------------------------------------------------------
    # Public reporting methods
    # ------------------------------------------------------------------

    def error(self, message:  str, *,
                    source:   str | _Omit | None = None,
                    lineno:   int | _Omit | None = None,
                    column:   int | _Omit | None = None,
                    token:    Token | None       = None) -> None:
        self._report(_Severity.ERROR, message, source = source,
                      lineno = lineno, column = column, token = token)

    def warning(self, message:  str, *,
                    source:   str | _Omit | None = None,
                    lineno:   int | _Omit | None = None,
                    column:   int | _Omit | None = None,
                    token:    Token | None       = None) -> None:
        self._report(_Severity.WARNING, message, source = source,
                      lineno = lineno, column = column, token = token)

    def info(self, message:  str, *,
                    source:   str | _Omit | None = None,
                    lineno:   int | _Omit | None = None,
                    column:   int | _Omit | None = None,
                    token:    Token | None       = None) -> None:
        self._report(_Severity.INFO, message, source = source,
                      lineno = lineno, column = column, token = token)

    def fatal(self, message:  str, *,
                    source:   str | _Omit | None = None,
                    lineno:   int | _Omit | None = None,
                    column:   int | _Omit | None = None,
                    token:    Token | None       = None) -> None:
        self._report(_Severity.FATAL, message, source = source,
                      lineno = lineno, column = column, token = token)


# ---------------------------------------------------------------------------
# Module-level instance
# ---------------------------------------------------------------------------

ctx = ErrorContext()

# ---------------------------------------------------------------------------
# paths in error messages idealy aren't long
# ---------------------------------------------------------------------------

def short_path(path: str | Path) -> str:
    """Return path relative to cwd if possible, otherwise absolute POSIX path."""
    try:
        return Path(path).resolve().relative_to(Path.cwd()).as_posix()
    except ValueError:
        return Path(path).as_posix()

# ---------------------------------------------------------------------------
# Parser input processing
# ---------------------------------------------------------------------------

MAX_ENCODING_ERRORS = 20

def _check_ascii(lines: list[str]) -> bool:
    """
    Check all lines for non-ASCII characters.
    Reports errors into the current context.
    Returns True if all lines are ASCII clean, False otherwise.
    If more than MAX_ENCODING_ERRORS errors are found, stops
    checking and reports False to avoid message flooding.
    """
    encoding_errors = 0
    for lineno, line in enumerate(lines, start=1):
        if not line.isascii():
            ctx.error("non-ASCII character", lineno=lineno, column=OMIT)
            encoding_errors += 1
            if encoding_errors >= MAX_ENCODING_ERRORS:
                ctx.error( f"too many encoding errors ({MAX_ENCODING_ERRORS}); "
                           f"file may be in the wrong encoding")
                return False
    return encoding_errors == 0


def read_source_file(path: str) -> list[str] | None:
    """
    Open and read a source file into a list of lines.
    Pushes an ErrorContext for path onto the context stack.
    Caller is responsible for calling pop_context() when done.

    Returns the list of lines, or None if the file could
    not be read or contains encoding errors.
    """
    ctx.push(source=short_path(path))
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        ctx.error("file is not valid UTF-8; re-save as UTF-8 and try again",
                   lineno=OMIT, column=OMIT)
        return None
    except FileNotFoundError:
        ctx.error("file not found", lineno=OMIT, column=OMIT)
        return None

    return lines if _check_ascii(lines) else None


def read_source_string(text: str,
                       source: str = "<string>") -> list[str] | None:
    """
    Split a string into lines and validate for ASCII content.
    Pushes an ErrorContext with source label onto the context stack.
    Caller is responsible for calling pop_context() when done.

    The source parameter allows a more descriptive label than the
    default "<string>" when the origin of the text is known.

    Returns the list of lines, or None if encoding errors were found.
    """
    ctx.push(source=source)
    lines = text.splitlines(keepends=True)
    return lines if _check_ascii(lines) else None

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
