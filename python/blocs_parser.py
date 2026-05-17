# blocs_parser.py
# Parser for .blocs system definition files.
# Reads a .blocs file and returns a Design object.

import sys
from collections import namedtuple
from pathlib import Path

from emblocs import (
    EmblocsError,
    BlockSpec,
    Design,
    BlockDef, Signal, Thread,
    PinType,
)
from bloc_parser import parse_bloc_file
from bloc_resolver import resolve
from parse_common import ( Token, tokenize_line,
                           Severity, report, OMIT,
                           current_context, push_context, pop_context,
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

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def resolve_bloc_path(path: str) -> str | None:
    """
    Resolve a .bloc file path as written in a blockdef command.

    Relative paths are interpreted relative to the directory containing
    the .blocs file currently being parsed (from current_context().source).
    Absolute paths are used as-is.

    Returns the resolved path as a POSIX string, or None if the file
    does not exist.

    Future enhancement: search path support could be added here by
    checking additional directories if the relative resolution fails.
    """
    blocs_dir = Path(current_context().source).parent
    resolved = (blocs_dir / path).resolve()
    if not resolved.exists():
        return None
    return resolved.as_posix()


# ---------------------------------------------------------------------------
# Bloc spec cache
# ---------------------------------------------------------------------------

_bloc_spec_cache: dict[str, BlockSpec] = {}


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_blockdef(tokens: list[Token], design: Design) -> None:
    """
    Handle the 'blockdef' command.
    Syntax: blockdef <name> <path> [PARAM=value...]
    """
    keyword = tokens[0]
    if len(tokens) < 3:
        report(Severity.ERROR,
               "'blockdef' requires a name and a path",
               column=OMIT)
        return
    name_tok = tokens[1]
    path_tok = tokens[2]
    if not name_tok.text.isidentifier():
        report(Severity.ERROR,
               f"invalid blockdef name {name_tok.text!r}",
               token=name_tok)
        return
    # resolve path to .bloc file
    resolved_path = resolve_bloc_path(path_tok.text)
    if resolved_path is None:
        report(Severity.ERROR,
               f"bloc file not found: {path_tok.text!r}",
               token=path_tok)
        return
    # get BlockSpec from cache or create it by parsing the .bloc file
    if resolved_path not in _bloc_spec_cache:
        spec = parse_bloc_file(resolved_path)
        if spec is None:
            report(Severity.ERROR,
                   f"failed to parse {path_tok.text!r}",
                   token=path_tok)
            return
        _bloc_spec_cache[resolved_path] = spec
    spec = _bloc_spec_cache[resolved_path]
    # parse PARAM=value tokens
    supplied_params = {}
    spec_param_names = {p.name for p in spec.params}
    for tok in tokens[3:]:
        param_name, sep, value_str = tok.text.partition("=")
        if sep == "":
            report(Severity.ERROR,
                   f"expected PARAM=value, got {tok.text!r}",
                   token=tok)
            return
        if not param_name.isidentifier():
            report(Severity.ERROR,
                   f"invalid parameter name {param_name!r}",
                   token=tok)
            return
        if param_name not in spec_param_names:
            report(Severity.WARNING,
                   f"unmatched parameter {param_name!r} will be ignored",
                   token=tok)
        try:
            supplied_params[param_name] = int(value_str, 0)
        except ValueError:
            report(Severity.ERROR,
                   f"invalid value {value_str!r} "
                   f"for {param_name!r}; expected an integer",
                   token=tok)
            return
    # warn about params not supplied
    for param in spec.params:
        if param.name not in supplied_params:
            report(Severity.INFO,
                   f"parameter {param.name!r} not supplied, "
                   f"using default value {param.default}",
                   column=OMIT)
    # resolve BlockSpec to BlockDef
    push_context(source=current_context().source,
                 line=keyword.line,
                 column=keyword.column)
    block_def = resolve(spec, name_tok.text, supplied_params)
    pop_context()
    if block_def is None:
        report(Severity.ERROR,
               f"failed to resolve {path_tok.text!r} as {name_tok.text!r}",
               column=OMIT)
        return
    # add to design
    try:
        design.add_block_def(block_def)
    except EmblocsError as e:
        report(Severity.ERROR, str(e), token=name_tok)


def cmd_block(tokens: list[Token], design: Design) -> None:
    """
    Handle the 'block' command.
    Syntax: block <instance-name> <blockdef-name>
    No subcommands are defined for block instances.
    """
    keyword = tokens[0]
    if len(tokens) < 3:
        report(Severity.ERROR,
               "'block' requires an instance name and a blockdef name",
               column=OMIT)
        return
    name_tok = tokens[1]
    def_tok = tokens[2]
    if not name_tok.text.isidentifier():
        report(Severity.ERROR,
               f"invalid block instance name {name_tok.text!r}",
               token=name_tok)
        return
    if not def_tok.text.isidentifier():
        report(Severity.ERROR,
               f"invalid blockdef name {def_tok.text!r}",
               token=def_tok)
        return
    if len(tokens) > 3:
        report(Severity.ERROR,
               f"unexpected token {tokens[3].text!r} after blockdef name",
               token=tokens[3])
        return
    # create the instance
    try:
        design.add_block_instance(name_tok.text, def_tok.text)
    except EmblocsError as e:
        report(Severity.ERROR, str(e), column=OMIT)

# ---------------------------------------------------------------------------
# dispatcher
# ---------------------------------------------------------------------------

def parse_command(tokens: list[Token], design: Design) -> None:
    """
    Dispatch a complete command to the appropriate handler.
    The first token determines the command type.
    """
    current_context().line = tokens[0].line
    keyword = tokens[0]
    if keyword.text == "blockdef":
        cmd_blockdef(tokens, design)
    elif keyword.text == "block":
        cmd_block(tokens, design)
    else:
        report(Severity.ERROR,
               f"unrecognized command: {keyword.text!r}",
               token=keyword)


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

def parse_blocs(lines: list[str],
                design: Design | None = None) -> Design | None:
    """
    Parse a list of source lines and return a populated Design object.
    Expects an active ErrorContext (pushed by read_source_xxx()).
    Returns None if any errors were reported.
    """
    if design is None:
        design = Design(source_path=current_context().source)

    for tokens in lex_lines(lines):
        parse_command(tokens, design)

    return design if current_context().no_errors() else None


def parse_blocs_file(path: str,
                     design: Design | None = None) -> Design | None:
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
    design = parse_blocs(lines, design)
    ctx = pop_context()
    ctx.summarize()
    return design


def parse_blocs_string(text: str, source: str = "<string>",
                       design: Design | None = None) -> Design | None:
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
    design = parse_blocs(lines, design)
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
