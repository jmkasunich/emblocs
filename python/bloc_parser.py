# bloc_parser.py
# Parser for .bloc block template files.
# Reads a .bloc file and returns a BlockSpec object.
#
# Current limitations (to be lifted as the language coverage grows):
#   - param declarations are not yet supported
#   - array pins (fixed and append) are not yet supported
#   - #if/#endif conditionals are not yet supported
#   - for loops are not yet supported
#   - init declarations are not yet supported
#   - multi-token name templates are not yet supported

import sys
from emblocs import BlockSpec, Statement, PinSpec, VarDef, FunctDef, PinType, PinDir
import re
from collections import namedtuple
from dataclasses import dataclass, field
from enum import Enum, auto

Token = namedtuple("Token", ["text", "line", "column"])

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

# Module-level state: current file path and diagnostic counters.
# Reset at the start of each parse_bloc() call.
_path:          str = ""
_error_count:   int = 0
_warning_count: int = 0
_info_count:    int = 0

def report(severity: Severity, message: str,
           lineno: int = None, column: int = None,
           token: Token = None) -> None:
    """
    Print a diagnostic message and update counters.

    If token is supplied, lineno and column are taken from it.
    If neither token nor lineno/column are supplied, the location
    fields are omitted from the output.

    FATAL raises SystemExit after printing.  All others return normally.
    """
    global _error_count, _warning_count, _info_count

    if token is not None:
        lineno = token.line
        column = token.column

    label = _SEVERITY_LABEL[severity]

    if lineno is not None and column is not None:
        location = f"{_path}:{lineno}:{column}: "
    elif lineno is not None:
        location = f"{_path}:{lineno}: "
    else:
        location = f"{_path}: "

    print(f"{location}{label}: {message}", file=sys.stderr)

    if severity == Severity.ERROR:
        _error_count += 1
    elif severity == Severity.WARNING:
        _warning_count += 1
    elif severity == Severity.INFO:
        _info_count += 1

    if severity == Severity.FATAL:
        sys.exit(1)

# ---------------------------------------------------------------------------
# Keyword tables
# ---------------------------------------------------------------------------

PIN_TYPES = {
    "bool":  PinType.BOOL,
    "u32":   PinType.U32,
    "s32":   PinType.S32,
    "float": PinType.FLOAT,
    "raw":   PinType.RAW,
}

PIN_DIRS = {
    "input":  PinDir.INPUT,
    "output": PinDir.OUTPUT,
}


# ---------------------------------------------------------------------------
# Line-level helpers
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"\S+")

def tokenize_line(line: str, line_no: int) -> list[Token]:
    """
    Tokenize a single line into whitespace-separated tokens.

    Parameters:
        line (str): The source line to tokenize
        line_no (int): 1-based line number

    Returns:
        list[Token]: Tokens with text, line, and column (1-based)
        if line is all whitespace, returns an empty list
    """
    return [
        Token(
            text=m.group(),
            line=line_no,
            column=m.start() + 1
        )
        for m in _TOKEN_RE.finditer(line)
    ]

# ---------------------------------------------------------------------------
# Parser state
# ---------------------------------------------------------------------------

class Section(Enum):
    BLOCK  = auto()
    PARAMS = auto()
    BODY   = auto()

_ALLOWED = {
    Section.BLOCK:  {"block"},
    Section.PARAMS: {"param"},
    Section.BODY:   {"pin", "var", "function", "#if", "#endif"},
}

@dataclass
class ParseState:
    """
    Mutable state threaded through parse_statement and its children.

    Fields:
        section  -- current section of .bloc file; controls which statements
                    are legal at any given point in the file
        if_stack -- stack of #if condition expression strings currently
                    active; innermost condition is last in the list.
                    Empty outside any #if block.
    """
    section:  Section   = Section.BLOCK
    if_stack: list[str] = field(default_factory=list)

# ---------------------------------------------------------------------------
# Per-keyword parse functions
# ---------------------------------------------------------------------------

def parse_block(spec: BlockSpec,
                tokens: list[Token], description: str) -> None:
    """Handle the 'block' declaration."""
    keyword = tokens[0]
    if spec.name:
        report(Severity.ERROR, "'block' declared more than once", token=keyword)
    if len(tokens) < 2:
        report(Severity.FATAL, "'block' declaration requires a name", token=keyword)
    name_tok = tokens[1]
    if not name_tok.text.isidentifier():
        report(Severity.ERROR, f"invalid block name: {name_tok.text!r}", token=name_tok)
    spec.name        = name_tok.text
    spec.description = description

def parse_pin(tokens: list[Token], description: str) -> PinSpec | None:
    """Handle the 'pin' declaration."""
    report(Severity.INFO, "parse_pin not yet implemented", token=tokens[0])
    return None

    keyword   = tokens[0]
    if len(tokens) < 4:
        parse_error_tok(path, keyword,
                        "'pin' declaration needs at least type, direction, "
                        "and field name")
    type_tok  = tokens[1]
    dir_tok   = tokens[2]
    field_tok = tokens[3]

    if type_tok.text not in PIN_TYPES:
        parse_error_tok(path, type_tok,
                        f"unknown pin type {type_tok.text!r}; "
                        f"expected one of {list(PIN_TYPES)}")
    if dir_tok.text not in PIN_DIRS:
        parse_error_tok(path, dir_tok,
                        f"unknown pin direction {dir_tok.text!r}; "
                        f"expected 'input' or 'output'")
    if "[" in field_tok.text:
        parse_error_tok(path, field_tok,
                        "array pin dimensions are not yet supported")

    field_name   = field_tok.text
    emblocs_name = tokens[4].text if len(tokens) >= 5 else field_name

    spec.struct_members.append(PinSpec(
        field_name   = field_name,
        emblocs_name = emblocs_name,
        pin_type     = PIN_TYPES[type_tok.text],
        direction    = PIN_DIRS[dir_tok.text],
        dims         = [],
        description  = description,
    ))


def parse_var(tokens: list[Token], description: str) -> VarDef | None:
    """Handle the 'var' declaration."""
    report(Severity.INFO, "parse_var not yet implemented", token=tokens[0])
    return None

    keyword          = tokens[0]
    c_decl_with_semi = " ".join(t.text for t in tokens[1:])
    if not c_decl_with_semi.endswith(";"):
        parse_error_tok(path, keyword,
                        "'var' declaration must end with a semicolon")
    c_decl = c_decl_with_semi[:-1].rstrip()
    if not c_decl:
        parse_error_tok(path, keyword,
                        "'var' declaration has no C declaration")

    # Extract the field name from the last token (before the semicolon).
    # Strip leading '*' (pointer declarations) and trailing '[' (arrays).
    # Deliberately simple; will need revisiting for complex C types.
    last_tok = tokens[-1]
    raw_name = last_tok.text.rstrip(";").lstrip("*").split("[")[0]
    if not raw_name.isidentifier():
        parse_error_tok(path, last_tok,
                        f"could not parse field name from 'var' declaration: "
                        f"{c_decl!r}")

    spec.struct_members.append(VarDef(
        field_name = raw_name,
        c_decl     = c_decl,
    ))


def parse_function(tokens: list[Token], description: str) -> FunctDef | None:
    """Handle the 'function' declaration."""
    report(Severity.INFO, "parse_function not yet implemented", token=tokens[0])
    return None

    keyword = tokens[0]
    if len(tokens) < 2:
        parse_error_tok(path, keyword,
                        "'function' declaration requires a name")
    name_tok = tokens[1]
    if not name_tok.text.isidentifier():
        parse_error_tok(path, name_tok,
                        f"invalid function name: {name_tok.text!r}")
    spec.functions.append(FunctDef(
        name        = name_tok.text,
        description = description,
    ))


# ---------------------------------------------------------------------------
# Statement dispatcher
# ---------------------------------------------------------------------------

def _wrap(spec: BlockSpec, state: ParseState, obj) -> None:
    """Wrap a parsed object in a Statement and append to spec."""
    if obj is not None:
        spec.statements.append(
            Statement(conditions=list(state.if_stack), statement=obj))
        
def parse_statement_debug(spec, tokens, description):
    """ Temporary testing replacement for parse_statement();
        simply prints the tokens and description, then returns."""
    print(f"STATEMENT: {[t.text for t in tokens]}")
    if description:
        print(f"  DESCRIPTION: {description!r}")

def parse_statement(spec: BlockSpec, state: ParseState,
                    tokens: list[Token], description: str) -> None:
    """
    Dispatch a complete statement to the appropriate per-keyword handler.

    tokens is guaranteed non-empty.  description may be "".

    Section transitions:
        BLOCK  -> PARAMS  on any _ALLOWED[Section.PARAMS] keyword
        BLOCK  -> BODY    on any _ALLOWED[Section.BODY] keyword (no params in file)
        PARAMS -> BODY    on any _ALLOWED[Section.BODY] keyword
    """
    keyword = tokens[0]

    # Step 1: section transitions
    if keyword.text in _ALLOWED[Section.PARAMS]:
        if state.section == Section.BLOCK:
            state.section = Section.PARAMS

    if keyword.text in _ALLOWED[Section.BODY]:
        if state.section in ( Section.BLOCK, Section.PARAMS ):
            state.section = Section.BODY

    # Step 2: validate keyword is allowed in current section
    if keyword.text not in _ALLOWED[state.section]:
        report(Severity.ERROR,
               f"unexpected keyword {keyword.text!r} in current section",
               token=keyword)
        return

    # Step 3: dispatch
    if keyword.text == "block":
        parse_block(spec, tokens, description)
    elif keyword.text == "pin":
        _wrap(spec, state, parse_pin(tokens, description))
    elif keyword.text == "var":
        _wrap(spec, state, parse_var(tokens, description))
    elif keyword.text == "function":
        _wrap(spec, state, parse_function(tokens, description))

    elif keyword.text == "#if":
        if len(tokens) < 2:
            report(Severity.ERROR, "'#if' requires an expression", token=keyword)
        else:
            state.if_stack.append(tokens[1].text)

    elif keyword.text == "#endif":
        if len(tokens) > 1:
            report(Severity.WARNING, "'#endif' takes no arguments", token=tokens[1])
        if not state.if_stack:
            report(Severity.ERROR, "'#endif' without matching '#if'", token=keyword)
        else:
            state.if_stack.pop()

    # Unsupported but recognized keywords
    elif keyword.text in ("param", "#if", "#endif"):
        report(Severity.WARNING, f"'{keyword.text}' not yet supported", token=keyword)

    else:
        report(Severity.ERROR, f"unrecognized token: {keyword.text!r}", token=keyword)


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_bloc(path: str) -> BlockSpec:
    """
    Parse a .bloc file and return a populated BlockSpec.

    This function directly handles line-by-line parsing, tokenization, 
    and description accumulation, then calls parse_statement() for
    each complete statement.

    Raises SystemExit (via parse_error) on any syntax or semantic error.
    """
    global _path, _error_count, _warning_count, _info_count
    _path = path
    _error_count = 0
    _warning_count = 0
    _info_count = 0

    spec = BlockSpec(source_path=path)
    pending_tokens: list[Token] = []
    pending_description: str = ""
    state = ParseState()
    def flush():
        """
        If there are pending tokens, call parse_statement(),
        then reset to process next statement.
        """
        nonlocal pending_tokens, pending_description
        if pending_tokens:
            parse_statement(spec, state, pending_tokens, pending_description)
        pending_tokens      = []
        pending_description = ""

    try:
        with open(path, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                if not line.isascii():
                    report(Severity.ERROR, "Non-ASCII character found", lineno=lineno)
                # split token section from comment/description
                first_part, sep, last_part = line.partition("//")
                new_tokens = tokenize_line(first_part, lineno)
                # determine if last part is description or comment/nothing
                if last_part.startswith("/") :
                    new_description = last_part[1:]
                else:
                    new_description = ""

                # apply language rules
                if pending_description and new_description and not new_tokens :
                    # description continuation line
                    pending_description += new_description
                else :
                    # any previous statement is now complete
                    flush()
                    if new_description and not new_tokens :
                        # misplaced description
                        report(Severity.ERROR, "Misplaced description", lineno=lineno, column=len(first_part))
                    elif new_tokens :
                        # new statement
                        pending_tokens = new_tokens
                        pending_description = new_description
                    else :
                        # empty line or comment-only line
                        pass
            # end of file, process pending if any
            flush()
            if state.if_stack:
                report(Severity.ERROR,
                       f"end-of-file with {len(state.if_stack)} "
                       f"unterminated '#if' statements")

    except UnicodeDecodeError:
        report(Severity.FATAL, "Unicode decode error")
    except FileNotFoundError:
        report(Severity.FATAL,"File not found")

    print(f"{_path}: {_error_count} error(s), "
          f"{_warning_count} warning(s), {_info_count} info(s)", file=sys.stderr)
    return spec


# ---------------------------------------------------------------------------
# Test driver
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <file.bloc>", file=sys.stderr)
        sys.exit(1)

    block_spec = parse_bloc(sys.argv[1])
    print(block_spec.describe())
