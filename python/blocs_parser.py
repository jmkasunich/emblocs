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
from parse_common import (
    ctx, Severity, OMIT,
    Token, tokenize_line,
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

def get_value(text: str, value_type: PinType) -> int | float | None:
    """
    Parse and validate a value/expression token against the given EMBLOCS type.

    Calls the expression evaluator to support literal constants and
    arithmetic expressions (e.g. 48*200, 25.4/4) as single tokens.
    An empty variable dict is passed, so named variables are not supported.

    Returns the parsed value as int or float, or None if parsing fails.
    Reports an error using the current context on failure.
    """
    if value_type == PinType.RAW:
        ctx.report(Severity.ERROR,
               "internal error: get_value() called with RAW type")
        return None
    if value_type == PinType.BOOL:
        if text == "true":
            return 1
        if text == "false":
            return 0
        try:
            result = evaluate(text, {}, 'int')
        except ExpressionError as e:
            ctx.report(Severity.ERROR,
                   f"invalid bool value {text!r}: {e}")
            return None
        return int(result)
    elif value_type == PinType.U32:
        try:
            result = evaluate(text, {}, 'int')
        except ExpressionError as e:
            ctx.report(Severity.ERROR,
                   f"invalid u32 value {text!r}: {e}")
            return None
        if result < 0 or result > U32_MAX:
            ctx.report(Severity.ERROR,
                   f"u32 value {text!r} is out of range [0, {U32_MAX}]")
            return None
        return int(result)
    elif value_type == PinType.S32:
        try:
            result = evaluate(text, {}, 'int')
        except ExpressionError as e:
            ctx.report(Severity.ERROR,
                   f"invalid s32 value {text!r}: {e}")
            return None
        if result < S32_MIN or result > S32_MAX:
            ctx.report(Severity.ERROR,
                   f"s32 value {text!r} is out of range [{S32_MIN}, {S32_MAX}]")
            return None
        return int(result)
    elif value_type == PinType.FLOAT:
        try:
            result = evaluate(text, {}, 'float')
        except ExpressionError as e:
            ctx.report(Severity.ERROR,
                   f"invalid float value {text!r}: {e}")
            return None
        try:
            import struct
            struct.pack('f', result)
        except struct.error:
            ctx.report(Severity.ERROR,
                   f"float value {text!r} is out of range for a 32-bit float")
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
    blocs_dir = Path(ctx.source).parent
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
        ctx.report(Severity.ERROR,
               "'blockdef' requires a name and a path",
               column=OMIT)
        return None, 0
    name_tok = tokens[1]
    path_tok = tokens[2]
    if not name_tok.text.isidentifier():
        ctx.report(Severity.ERROR,
               f"invalid blockdef name {name_tok.text!r}",
               token=name_tok)
        return None, 0
    # resolve path to .bloc file
    resolved_path = resolve_bloc_path(path_tok.text)
    if resolved_path is None:
        ctx.report(Severity.ERROR,
               f"bloc file not found: {path_tok.text!r}",
               token=path_tok)
        return None, 0
    # get BlockSpec from cache or create it by parsing the .bloc file
    if resolved_path not in _bloc_spec_cache:
        spec = parse_bloc_file(resolved_path)
        if spec is None:
            ctx.report(Severity.ERROR,
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
            ctx.report(Severity.ERROR,
                   f"invalid parameter name {param_name!r}",
                   token=tok)
            return None, 0
        if param_name not in spec_param_names:
            ctx.report(Severity.WARNING,
                   f"unmatched parameter {param_name!r} will be ignored",
                   token=tok)
        try:
            supplied_params[param_name] = int(value_str, 0)
        except ValueError:
            ctx.report(Severity.ERROR,
                   f"invalid value {value_str!r} "
                   f"for {param_name!r}; expected an integer",
                   token=tok)
            return None, 0
    # warn about params not supplied
    for param in spec.params:
        if param.name not in supplied_params:
            ctx.report(Severity.INFO,
                   f"parameter {param.name!r} not supplied, "
                   f"using default value {param.default}",
                   column=OMIT)
    # resolve BlockSpec to BlockDef - set context for resolve() errors
    ctx.set(token=name_tok)
    block_def = resolve(spec, name_tok.text, supplied_params)
    if block_def is None:
        ctx.report(Severity.ERROR,
               f"failed to resolve {path_tok.text!r} as {name_tok.text!r}",
               column=OMIT)
        return None, 0
    # add to design
    try:
        blockdef = design.add_block_def(block_def)
    except EmblocsError as e:
        ctx.report(Severity.ERROR, str(e), token=name_tok)
        return None, 0
    return blockdef, n_tokens

def cmd_block(tokens: list[Token], design: Design) -> tuple[BlockInstance | None, int]:
    """
    Handle the 'block' command.
    Syntax: block <instance-name> <blockdef-name>
    No subcommands are defined for block instances.
    """
    if len(tokens) < 3:
        ctx.report(Severity.ERROR,
               "'block' requires an instance name and a blockdef name",
               column=OMIT)
        return None, 0
    name_tok = tokens[1]
    def_tok = tokens[2]
    if not name_tok.text.isidentifier():
        ctx.report(Severity.ERROR,
               f"invalid block instance name {name_tok.text!r}",
               token=name_tok)
        return None, 0
    if not def_tok.text.isidentifier():
        ctx.report(Severity.ERROR,
               f"invalid blockdef name {def_tok.text!r}",
               token=def_tok)
        return None, 0
    # create the instance
    try:
        block = design.add_block_instance(name_tok.text, def_tok.text)
    except EmblocsError as e:
        ctx.report(Severity.ERROR, str(e), column=OMIT)
        return None, 0
    return block, 3

def cmd_signal(tokens: list[Token], design: Design) -> tuple[Signal | None:, int]:
    """
    Handle the 'signal' command.
    Syntax: signal <signal-name> <type>
    A signal creation command can be followed by zero or more
    single-token subcommands that act on the new signal.
    """
    if len(tokens) < 3:
        ctx.report(Severity.ERROR,
               "'signal' requires a signal name and a type",
               column=OMIT)
        return None, 0
    name_tok = tokens[1]
    type_tok = tokens[2]
    if not name_tok.text.isidentifier():
        ctx.report(Severity.ERROR,
               f"invalid signal name {name_tok.text!r}",
               token=name_tok)
        return None, 0
    if type_tok.text not in SIGNAL_TYPES:
        ctx.report(Severity.ERROR,
               f"invalid signal type {type_tok.text!r}",
               token=type_tok)
        return None, 0
    sig_type = SIGNAL_TYPES[type_tok.text]
    # create the signal
    try:
        sig = design.add_signal(name_tok.text, sig_type)
    except EmblocsError as e:
        ctx.report(Severity.ERROR, str(e), column=OMIT)
        return None, 0
    return sig, 3

def cmd_thread(tokens: list[Token], design: Design) -> tuple[Thread | None, int]:
    """
    Handle the 'thread' command.
    Syntax: thread <thread-name> <periodns>
    A thread creation command can be followed by zero or more
    single-token subcommands that act on the new thread.
    """
    if len(tokens) < 3:
        ctx.report(Severity.ERROR,
               "'thread' requires a thread name and a period",
               column=OMIT)
        return None, 0
    name_tok = tokens[1]
    period_tok = tokens[2]
    if not name_tok.text.isidentifier():
        ctx.report(Severity.ERROR,
               f"invalid thread name {name_tok.text!r}",
               token=name_tok)
        return None, 0
    ctx.set(token=period_tok)
    period_ns = get_value(period_tok.text, PinType.U32)
    if period_ns is None:
        return None, 0
    # create the thread
    try:
        thread = design.add_thread(name_tok.text, period_ns)
    except EmblocsError as e:
        ctx.report(Severity.ERROR, str(e), column=OMIT)
        return None, 0
    return thread, 3


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def subcmd_signal(cmd: str, arg: str, signal: Signal, design: Design) -> None:
    """
    Handle a single-token subcommand that applies to a Signal target.
    Currently no subcommands are implemented, so this just reports an error.
    """
    ctx.report(Severity.ERROR,
        f"un-implemented subcommand {cmd!r} with arg {arg!r} on signal {signal.name!r}")

def subcmd_pin(cmd: str, arg: str, pin : PinInstance, design: Design) -> None:
    """
    Handle a single-token subcommand that applies to a Pin target.
    Currently no subcommands are implemented, so this just reports an error.
    """
    ctx.report(Severity.ERROR,
        f"un-implemented subcommand {cmd!r} with arg {arg!r} on pin {pin.pindef.name!r}")

def subcmd_thread(cmd: str, arg: str, thread : Thread, design: Design) -> None:
    """
    Handle a single-token subcommand that applies to a Thread target.
    Currently no subcommands are implemented, so this just reports an error.
    """
    ctx.report(Severity.ERROR,
        f"un-implemented subcommand {cmd!r} with arg {arg!r} on thread {thread.name!r}")

def subcmd_funct(cmd: str, arg: str, funct : FunctInstance, design: Design) -> None:
    """
    Handle a single-token subcommand that applies to a Function target.
    Currently no subcommands are implemented, so this just reports an error.
    """
    ctx.report(Severity.ERROR,
        f"un-implemented subcommand {cmd!r} with arg {arg!r} on function {funct.funct_def.name!r}")

# ---------------------------------------------------------------------------
# dispatcher
# ---------------------------------------------------------------------------

CMD_DISPATCH = {
    "blockdef": cmd_blockdef,
    "block":    cmd_block,
    "signal":   cmd_signal,
    "thread":   cmd_thread,
}

# longer prefixes must come first to ensure correct matching
SUBCMD_DISPATCH = {
    Signal:        ( subcmd_signal, ("-+", "+", "-", "=") ),
    PinInstance:   ( subcmd_pin,    ("-+", "+", "-", "=") ),
    Thread:        ( subcmd_thread, ("-+", "+", "-") ),
    FunctInstance: ( subcmd_funct,  ("-+", "+", "-") ),
}

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
    keyword = tokens[0]
    ctx.set(token=keyword)
    handler = CMD_DISPATCH.get(keyword.text)
    if handler is not None:
        # create the target object
        target, n_tokens = handler(tokens, design)
        if target is None:
            # handler alredy reported an error
            return
        subcommand_tokens = tokens[n_tokens:]
        target_name = target.name
    else:
        # look up target object
        try:
            target = design.find_object_by_name(keyword.text)
        except EmblocsError as e:
            ctx.report(Severity.ERROR,
                    f"unknown command or object {keyword.text!r}: {str(e)}",
                    token=keyword)
            return
        subcommand_tokens = tokens[1:]
        target_name = keyword.text
    # dispatch subcommands if any
    if subcommand_tokens:
        entry = SUBCMD_DISPATCH.get(type(target))
        if entry is None:
            ctx.report(
                Severity.ERROR,
                f"{target_name!r} ({type(target).__name__}) has no subcommands, "
                f"got {subcommand_tokens[0].text!r}",
                token=subcommand_tokens[0])
            return
        handler, prefixes = entry
        # dispatch each remaining token as a subcommand
        for tok in subcommand_tokens:
            ctx.set(token=tok)
            subcmd = tok.text
            for prefix in prefixes:
                if subcmd.startswith(prefix):
                    suffix = subcmd[len(prefix):]
                    handler(prefix, suffix, target, design)
                    break
            else:
                ctx.report(Severity.ERROR,
                    f"subcommand {subcmd!r} is invalid for target "
                    f"{target_name!r} ({type(target).__name__})")
                # break - # uncomment to stop after one bad subcommand


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
        ctx.report(Severity.ERROR,
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
        design = Design(source_path=ctx.source)

    for tokens in lex_lines(lines):
        parse_command(tokens, design)

    return design if ctx.no_errors() else None


def parse_blocs_file(path: str,
                     design: Design | None = None) -> Design | None:
    """
    Parse a .blocs file and return a populated Design object.
    Convenience wrapper around read_source_file() and parse_blocs().
    Returns None if the file could not be read or parsing failed.
    """
    lines = read_source_file(path)
    if lines is None:
        ctx.summarize()
        ctx.pop()
        return None
    design = parse_blocs(lines, design)
    ctx.summarize()
    ctx.pop()
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
        ctx.summarize()
        ctx.pop()
        return None
    design = parse_blocs(lines, design)
    ctx.summarize()
    ctx.pop()
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
