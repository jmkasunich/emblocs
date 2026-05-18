# blocs_parser.py
# Parser for .blocs system definition files.
# Reads a .blocs file and returns a Design object.

import sys
from collections import namedtuple
from pathlib import Path
from expressions import evaluate, ExpressionError

from emblocs import (
    EmblocsError,
    BlockSpec,
    Design,
    BlockDef, Signal, Thread,
    PinType,
    BlockInstance, PinInstance, FunctInstance,
    U32_MAX, S32_MIN, S32_MAX,
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
# helper for parsing values and expressions
# ---------------------------------------------------------------------------

def get_value(tok: Token, value_type: PinType) -> int | float | None:
    """
    Parse and validate a value/expression token against the given EMBLOCS type.

    Calls the expression evaluator to support literal constants and
    arithmetic expressions (e.g. 48*200, 25.4/4) as single tokens.
    An empty variable dict is passed, so named variables are not supported.

    Returns the parsed value as int or float, or None if parsing fails.
    Reports an error into the current context on failure.
    """
    if value_type == PinType.RAW:
        report(Severity.ERROR,
               "internal error: get_value() called with RAW type",
               token=tok)
        return None
    if value_type == PinType.BOOL:
        if tok.text == "true":
            return 1
        if tok.text == "false":
            return 0
        try:
            result = evaluate(tok.text, {}, int)
        except ExpressionError as e:
            report(Severity.ERROR,
                   f"invalid bool value {tok.text!r}: {e}",
                   token=tok)
            return None
        return int(result)
    elif value_type == PinType.U32:
        try:
            result = evaluate(tok.text, {}, int)
        except ExpressionError as e:
            report(Severity.ERROR,
                   f"invalid u32 value {tok.text!r}: {e}",
                   token=tok)
            return None
        if result < 0 or result > U32_MAX:
            report(Severity.ERROR,
                   f"u32 value {tok.text!r} is out of range [0, {U32_MAX}]",
                   token=tok)
            return None
        return int(result)
    elif value_type == PinType.S32:
        try:
            result = evaluate(tok.text, {}, int)
        except ExpressionError as e:
            report(Severity.ERROR,
                   f"invalid s32 value {tok.text!r}: {e}",
                   token=tok)
            return None
        if result < S32_MIN or result > S32_MAX:
            report(Severity.ERROR,
                   f"s32 value {tok.text!r} is out of range [{S32_MIN}, {S32_MAX}]",
                   token=tok)
            return None
        return int(result)
    elif value_type == PinType.FLOAT:
        try:
            result = evaluate(tok.text, {}, float)
        except ExpressionError as e:
            report(Severity.ERROR,
                   f"invalid float value {tok.text!r}: {e}",
                   token=tok)
            return None
        try:
            import struct
            struct.pack('f', result)
        except struct.error:
            report(Severity.ERROR,
                   f"float value {tok.text!r} is out of range for a 32-bit float",
                   token=tok)
            return None
        return float(result)

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

def cmd_blockdef(tokens: list[Token], design: Design) -> tuple[BlockDef | None, int]:
    """
    Handle the 'blockdef' command.
    Syntax: blockdef <name> <path> [PARAM=value...]
    """
    if len(tokens) < 3:
        report(Severity.ERROR,
               "'blockdef' requires a name and a path",
               column=OMIT)
        return None, 0
    name_tok = tokens[1]
    path_tok = tokens[2]
    if not name_tok.text.isidentifier():
        report(Severity.ERROR,
               f"invalid blockdef name {name_tok.text!r}",
               token=name_tok)
        return None, 0
    # resolve path to .bloc file
    resolved_path = resolve_bloc_path(path_tok.text)
    if resolved_path is None:
        report(Severity.ERROR,
               f"bloc file not found: {path_tok.text!r}",
               token=path_tok)
        return None, 0
    # get BlockSpec from cache or create it by parsing the .bloc file
    if resolved_path not in _bloc_spec_cache:
        spec = parse_bloc_file(resolved_path)
        if spec is None:
            report(Severity.ERROR,
                   f"failed to parse {path_tok.text!r}",
                   token=path_tok)
            return None, 0
        _bloc_spec_cache[resolved_path] = spec
    spec = _bloc_spec_cache[resolved_path]
    # parse PARAM=value tokens
    supplied_params = {}
    spec_param_names = {p.name for p in spec.params}
    n_tokens = 3
    for tok in tokens[3:]:
        param_name, sep, value_str = tok.text.partition("=")
        if sep == "":
            break
        n_tokens += 1
        if not param_name.isidentifier():
            report(Severity.ERROR,
                   f"invalid parameter name {param_name!r}",
                   token=tok)
            return None, 0
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
            return None, 0
    # warn about params not supplied
    for param in spec.params:
        if param.name not in supplied_params:
            report(Severity.INFO,
                   f"parameter {param.name!r} not supplied, "
                   f"using default value {param.default}",
                   column=OMIT)
    # resolve BlockSpec to BlockDef - set context for resolve() errors
    current_context().line = name_tok.line
    current_context().column = name_tok.column
    block_def = resolve(spec, name_tok.text, supplied_params)
    if block_def is None:
        report(Severity.ERROR,
               f"failed to resolve {path_tok.text!r} as {name_tok.text!r}",
               column=OMIT)
        return None, 0
    # add to design
    try:
        blockdef = design.add_block_def(block_def)
    except EmblocsError as e:
        report(Severity.ERROR, str(e), token=name_tok)
        return None, 0
    return blockdef, n_tokens

def cmd_block(tokens: list[Token], design: Design) -> tuple[BlockInstance | None, int]:
    """
    Handle the 'block' command.
    Syntax: block <instance-name> <blockdef-name>
    No subcommands are defined for block instances.
    """
    if len(tokens) < 3:
        report(Severity.ERROR,
               "'block' requires an instance name and a blockdef name",
               column=OMIT)
        return None, 0
    name_tok = tokens[1]
    def_tok = tokens[2]
    if not name_tok.text.isidentifier():
        report(Severity.ERROR,
               f"invalid block instance name {name_tok.text!r}",
               token=name_tok)
        return None, 0
    if not def_tok.text.isidentifier():
        report(Severity.ERROR,
               f"invalid blockdef name {def_tok.text!r}",
               token=def_tok)
        return None, 0
    # create the instance
    try:
        block = design.add_block_instance(name_tok.text, def_tok.text)
    except EmblocsError as e:
        report(Severity.ERROR, str(e), column=OMIT)
        return None, 0
    return block, 3

def subcmd_signal(token: Token, signal: Signal, design: Design) -> None:
    """
    Handle a single-token subcommand that follows a 'signal' command.
    Currently no subcommands are defined, so this just reports an error.
    """
    report(Severity.ERROR,
           f"un-implemented subcommand {token.text!r} on signal {signal.name!r}",
           token=token)

def subcmd_pin(token: Token, pin : PinInstance, design: Design) -> None:
    """
    Handle a single-token subcommand that applies to a Pin target.
    Currently no subcommands are defined, so this just reports an error.
    """
    report(Severity.ERROR,
           f"un-implemented subcommand {token.text!r} on pin {pin.pin_def.name!r}",
           token=token)

def cmd_signal(tokens: list[Token], design: Design) -> tuple[Signal | None:, int]:
    """
    Handle the 'signal' command.
    Syntax: signal <signal-name> <type>
    A signal creation command can be followed by zero or more
    single-token subcommands that act on the new signal.
    """
    if len(tokens) < 3:
        report(Severity.ERROR,
               "'signal' requires a signal name and a type",
               column=OMIT)
        return None, 0
    name_tok = tokens[1]
    type_tok = tokens[2]
    if not name_tok.text.isidentifier():
        report(Severity.ERROR,
               f"invalid signal name {name_tok.text!r}",
               token=name_tok)
        return None, 0
    if type_tok.text not in SIGNAL_TYPES:
        report(Severity.ERROR,
               f"invalid signal type {type_tok.text!r}",
               token=type_tok)
        return None, 0
    sig_type = SIGNAL_TYPES[type_tok.text]
    # create the signal
    try:
        sig = design.add_signal(name_tok.text, sig_type)
    except EmblocsError as e:
        report(Severity.ERROR, str(e), column=OMIT)
        return None, 0
    return sig, 3
 
def subcmd_thread(token: Token, thread : Thread, design: Design) -> None:
    """
    Handle a single-token subcommand that follows a 'thread' command.
    Currently no subcommands are defined, so this just reports an error.
    """
    report(Severity.ERROR,
           f"un-implemented subcommand {token.text!r} on thread {thread.name!r}",
           token=token)

def subcmd_funct(token: Token, funct : FunctInstance, design: Design) -> None:
    """
    Handle a single-token subcommand that applies to a Function target.
    Currently no subcommands are defined, so this just reports an error.
    """
    report(Severity.ERROR,
           f"un-implemented subcommand {token.text!r} on function {funct.funct_def.name!r}",
           token=token)

def cmd_thread(tokens: list[Token], design: Design) -> tuple[Thread | None, int]:
    """
    Handle the 'thread' command.
    Syntax: thread <thread-name> <periodns>
    A thread creation command can be followed by zero or more
    single-token subcommands that act on the new thread.
    """
    if len(tokens) < 3:
        report(Severity.ERROR,
               "'thread' requires a thread name and a period",
               column=OMIT)
        return None, 0
    name_tok = tokens[1]
    period_tok = tokens[2]
    if not name_tok.text.isidentifier():
        report(Severity.ERROR,
               f"invalid thread name {name_tok.text!r}",
               token=name_tok)
        return None, 0
    period_ns = get_value(period_tok, PinType.U32)
    if period_ns is None:
        return None, 0
    # create the thread
    try:
        thread = design.add_thread(name_tok.text, period_ns)
    except EmblocsError as e:
        report(Severity.ERROR, str(e), column=OMIT)
        return None, 0
    return thread, 3

# ---------------------------------------------------------------------------
# dispatcher
# ---------------------------------------------------------------------------

def parse_command(tokens: list[Token], design: Design) -> None:
    """
    Dispatch a complete command to the appropriate handler.

    Commands fall into two categories:
    - Creation commands (blockdef, block, signal, thread): create a new
      object and return it as the target for any following subcommands.
    - Modification commands (qualified or plain identifier): look up an
      existing object as the target for following subcommands.

    After the target is established, any remaining tokens are dispatched
    one at a time to the appropriate subcommand handler.
    """
    current_context().line = tokens[0].line
    keyword = tokens[0]
    creation_dispatch = {
        "blockdef": cmd_blockdef,
        "block":    cmd_block,
        "signal":   cmd_signal,
        "thread":   cmd_thread,
    }
    subcmd_dispatch = {
        Signal:        subcmd_signal,
        Thread:        subcmd_thread,
        PinInstance:   subcmd_pin,
        FunctInstance: subcmd_funct,
    }
    handler = creation_dispatch.get(keyword.text)
    if handler is not None:
        # create the target object
        target, n_tokens = handler(tokens, design)
        if target is None:
            # handler alredy reported an error
            return
        subcommand_tokens = tokens[n_tokens:]
    else:
        # not a creation command - look up the target object for subcommands
        name, sep, sub_name = tokens[0].text.partition(".")
        if sep:
            # qualified name: block.pin or block.func
            if name not in design.blocks:
                report(Severity.ERROR,
                       f"unknown block instance {name!r}",
                       token=tokens[0])
                return
            block = design.blocks[name]
            target = block.namespace.get(sub_name)
            if target is None:
                report(Severity.ERROR,
                       f"unknown pin or function {sub_name!r} "
                       f"in block {name!r}",
                       token=tokens[0])
                return
        else:
            # plain identifier: target is Design level object
            target = design.namespace.get(tokens[0].text)
            if target is None:
                report(Severity.ERROR,
                       f"unrecognized command or unknown object "
                       f"{tokens[0].text!r}",
                       token=tokens[0])
                return
        subcommand_tokens = tokens[1:]
    # now dispatch subcommands if any
    if subcommand_tokens:
        handler = subcmd_dispatch.get(type(target))
        if handler is None:
            report(Severity.ERROR,
                f"{type(target).__name__} has no subcommands, "
                f"got {subcommand_tokens[0].text!r}",
                token=subcommand_tokens[0])
            return
        # dispatch each remaining token as a subcommand
        for tok in subcommand_tokens:
            handler(tok, target, design)


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
