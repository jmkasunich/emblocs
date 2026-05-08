# bloc_parser.py
# Parser for .bloc block template files.
# Reads a .bloc file and returns a BlockSpec object.
#
import sys
from emblocs import BlockSpec, ParamSpec, Statement, PinSpec, DimSpec, VarDef, FunctDef, PinType, PinDir
import re
from collections import namedtuple
from dataclasses import dataclass, field
from enum import Enum, auto
from expressions import evaluate, ExpressionError

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

U32_MAX = 0xFFFFFFFF

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
        return
    if len(tokens) < 2:
        report(Severity.FATAL, "'block' declaration requires a name", token=keyword)
    name_tok = tokens[1]
    if not name_tok.text.isidentifier():
        report(Severity.ERROR, f"invalid block name: {name_tok.text!r}", token=name_tok)
        return
    spec.name        = name_tok.text
    spec.description = description

def parse_param(spec: BlockSpec, tokens: list[Token], description: str) -> None:
    """
    Handle the 'param' declaration.
    Syntax: param <NAME> <type> default=<value> [min=<value>] [max=<value>]
    Appends a ParamSpec to spec.params, or reports errors and returns.
    """
    keyword = tokens[0]

    if len(tokens) < 4:
        report(Severity.ERROR,
               "'param' requires name, type, and default=value",
               token=keyword)
        return

    name_tok = tokens[1]
    type_tok = tokens[2]

    if not name_tok.text.isidentifier():
        report(Severity.ERROR,
               f"invalid parameter name: {name_tok.text!r}",
               token=name_tok)
        return

    if any(p.name == name_tok.text for p in spec.params):
        report(Severity.ERROR,
               f"duplicate parameter name: {name_tok.text!r}",
               token=name_tok)
        return

    if type_tok.text not in ("bool", "u32"):
        report(Severity.ERROR,
               f"invalid parameter type {type_tok.text!r}; "
               f"expected 'bool' or 'u32'",
               token=type_tok)
        return

    param_type = type_tok.text

    # parse key=value tokens for default, min, max
    default = None
    min_val = None
    max_val = None

    for tok in tokens[3:]:
        key, sep, val_str = tok.text.partition("=")
        if key not in ("default", "min", "max") or sep != "=":
            report(Severity.ERROR,
                   f"unexpected token {tok.text!r}; "
                   f"expected 'default=', 'min=', or 'max='",
                   token=tok)
            return
        if not val_str:
            report(Severity.ERROR,
                   f"missing value after '{key}='",
                   token=tok)
            return

        try:
            val = evaluate(val_str)
        except ExpressionError as e:
            report(Severity.ERROR, str(e), token=tok)
            return

        if param_type == "u32":
            if val < 0 or val > U32_MAX:
                report(Severity.ERROR,
                       f"{key} value {val} is out of range for u32 "
                       f"[0, {U32_MAX}]",
                       token=tok)
                return
        elif param_type == "bool":
            if val not in (0, 1):
                report(Severity.WARNING,
                       f"{key} value {val} is not 0 or 1 for bool parameter",
                       token=tok)

        if key == "default" and default is None:
            default = val
        elif key == "min" and min_val is None:
            min_val = val
        elif key == "max" and max_val is None:
            max_val = val
        else:
            report(Severity.ERROR, f"duplicate '{key}=' token", token=tok)
            return

    if default is None:
        report(Severity.ERROR,
               f"'param' requires a 'default=' value",
               lineno=keyword.line)
        return

    if min_val is not None and param_type == "bool":
        report(Severity.WARNING,
               "'min' is not meaningful for bool parameters",
               lineno=keyword.line)
    if max_val is not None and param_type == "bool":
        report(Severity.WARNING,
               "'max' is not meaningful for bool parameters",
               lineno=keyword.line)

    # cross-validate min, max, default
    if min_val is not None and max_val is not None:
        if min_val > max_val:
            report(Severity.ERROR,
                   f"min ({min_val}) is greater than max ({max_val})",
                   lineno=keyword.line)
            return

    if min_val is not None and default < min_val:
        report(Severity.ERROR,
               f"default ({default}) is less than min ({min_val})",
               lineno=keyword.line)
        return

    if max_val is not None and default > max_val:
        report(Severity.ERROR,
               f"default ({default}) is greater than max ({max_val})",
               lineno=keyword.line)
        return

    spec.params.append(ParamSpec(
        name        = name_tok.text,
        param_type  = param_type,
        default     = default,
        min_val     = min_val,
        max_val     = max_val,
        description = description,
    ))


_TEMPLATE_SPEC_RE = re.compile(r"""
    \{              # opening brace
    (?P<expr>       # start of 'expr' capture group
        [^}:]+      #   one or more chars that are not } or :
    )               # end of 'expr' capture group
    :               # colon separator
    (?P<width>      # start of 'width' capture group
        [1-9]       #   exactly one digit, 1-9
    )               # end of 'width' capture group
    \}              # closing brace
""", re.VERBOSE)

def parse_pin(spec: BlockSpec, tokens: list[Token], description: str) -> PinSpec | None:
    """
    Handle the 'pin' declaration.
    Syntax: pin <type> <direction> <name-or-template>[dims...] [if <expr>]

    The name-or-template token contains the emblocs name template with
    optional {expr:width} format specifiers and optional [index=size]
    dimension specifiers appended directly (no spaces).

    The C struct field name (field_name) is derived from the template by
    replacing each {expr:width} with 'width' zeros and appending '_'.
    """
    keyword = tokens[0]

    if len(tokens) not in (4, 6):
        report(Severity.ERROR,
                f"'pin' declaration must have 4 or 6 tokens, got {len(tokens)}",
                lineno=keyword.line)
        return None

    # token assignment
    type_tok    = tokens[1]
    dir_tok     = tokens[2]
    name_tok    = tokens[3]
    if_tok      = tokens[4] if len(tokens) == 6 else None
    if_cond_tok = tokens[5] if len(tokens) == 6 else None

    # validate type and direction
    if type_tok.text not in PIN_TYPES:
        report(Severity.ERROR,
                f"unknown pin type {type_tok.text!r}; "
                f"expected one of {list(PIN_TYPES)}", token=type_tok)
        return None
    if dir_tok.text not in PIN_DIRS:
        report(Severity.ERROR,
                f"unknown pin direction {dir_tok.text!r}; "
                f"expected 'input' or 'output'", token=dir_tok)
        return None

    # split name/template from dimension specifiers
    # e.g. "ch{i:2}_out[i=NCHAN]" -> template="ch{i:2}_out", dim_strings=["i=NCHAN]"]
    template, *dim_strings = name_tok.text.split('[')

    if not template:
        report(Severity.ERROR,
                "pin name/template cannot be empty", token=name_tok)
        return None

    # parse dimension specifiers, collecting index variables
    dims = []
    template_vars = dict(spec.defaults)   # copy, grows as index vars are added

    for dim_string in dim_strings:
        if not dim_string.endswith(']'):
            report(Severity.ERROR,
                    f"missing closing ']' in dimension {dim_string!r}",
                    token=name_tok)
            return None
        dim_string = dim_string[:-1]  # strip closing ']'
        index, sep, expr = dim_string.partition('=')
        if sep != '=':
            report(Severity.ERROR,
                   f"missing '=' in dimension {dim_string!r}",
                   token=name_tok)
            return None
        if not index.isidentifier():
            report(Severity.ERROR,
                   f"invalid index variable {index!r}",
                   token=name_tok)
            return None
        if index in template_vars:
            report(Severity.ERROR,
                f"index variable name {index!r} already in use",
                token=name_tok)
            return None
        if not expr:
            report(Severity.ERROR,
                   f"missing size in dimension {dim_string!r}",
                   token=name_tok)
            return None
        # validate dimension size expression using params
        try:
            evaluate(expr, spec.defaults)
        except ExpressionError as e:
            report(Severity.ERROR,
                   f"invalid dimension expression {expr!r}: {e}",
                   token=name_tok)
            return None
        template_vars[index] = 0
        dims.append(DimSpec(size_expr=expr, index_var=index))

    # derive field_name from template by replacing {expr:width} with 'width' zeros
    def replace_spec(m):
        width = int(m.group('width'))
        return '0' * width

    field_name = _TEMPLATE_SPEC_RE.sub(replace_spec, template) + '_'

    # any remaining { or } in field_name means a malformed specifier
    if '{' in field_name or '}' in field_name:
        report(Severity.ERROR,
               f"malformed template specifier in {template!r}; "
               f"expected {{expr:N}} where N is 1-9",
               token=name_tok)
        return None

    # field_name (with trailing _) must be a valid C identifier
    if not field_name.isidentifier():
        report(Severity.ERROR,
               f"template {template!r} produces invalid field name {field_name!r}",
               token=name_tok)
        return None

    dedup_name = field_name

    # check for duplicate in namespace
    if dedup_name in spec.namespace:
        report(Severity.ERROR,
               f"duplicate name {dedup_name!r} in block namespace",
               token=name_tok)
        return None

    # validate each specifier's expression
    for m in _TEMPLATE_SPEC_RE.finditer(template):
        expr_str = m.group('expr')
        try:
            evaluate(expr_str, template_vars)
        except ExpressionError as e:
            report(Severity.ERROR,
                   f"invalid expression {expr_str!r} in template: {e}",
                   token=name_tok)
            return None

    # parse optional trailing export condition
    export_cond = None
    if if_tok is not None:
        if if_tok.text != "if":
            report(Severity.ERROR,
                   f"expected 'if', got {if_tok.text!r}",
                   token=if_tok)
            return None
        # validate export condition using params + index vars
        try:
            evaluate(if_cond_tok.text, template_vars)
        except ExpressionError as e:
            report(Severity.ERROR,
                   f"invalid export condition {if_cond_tok.text!r}: {e}",
                   token=if_cond_tok)
            return None
        export_cond = if_cond_tok.text

    return PinSpec(
        emblocs_name     = template,
        field_name       = field_name,
        dedup_name       = dedup_name,
        pin_type         = PIN_TYPES[type_tok.text],
        direction        = PIN_DIRS[dir_tok.text],
        dims             = dims,
        export_condition = export_cond,
        description      = description,
    )

def parse_var(spec: BlockSpec, tokens: list[Token], description: str) -> VarDef | None:
    """
    Handle the 'var' declaration.
    Syntax: var <C-declaration>;

    Everything after 'var' up to and including the semicolon is the C
    declaration, stored verbatim.  The field name is extracted from the
    last token before the semicolon by stripping leading '*' (pointer
    declarations) and trailing '[' (array declarations).

    The block author is responsible for avoiding collisions with SDK macros
    and other external names.  Collision with pin field names is detected
    via the shared namespace.
    """
    keyword = tokens[0]

    if len(tokens) < 2:
        report(Severity.ERROR,
               "'var' statement requires a C declaration",
               token=keyword)
        return None

    # reconstruct C declaration from tokens (whitespace not preserved)
    c_decl = " ".join(t.text for t in tokens[1:])

    if not c_decl.endswith(";"):
        report(Severity.ERROR,
               "'var' declaration must end with a semicolon",
               token=tokens[-1])
        return None

    # extract field name from last token before semicolon
    last_tok = tokens[-1]
    # strip leading '*' (pointer declarations) and everything from '[' onward (arrays)
    field_name = last_tok.text.rstrip(";").lstrip("*").split("[")[0]

    if not field_name.isidentifier():
        report(Severity.ERROR,
               f"could not extract valid field name from 'var' declaration; "
               f"got {field_name!r}",
               token=last_tok)
        return None

    # check for duplicate in namespace
    if field_name in spec.namespace:
        report(Severity.ERROR,
               f"duplicate name {field_name!r} in block namespace",
               token=last_tok)
        return None

    return VarDef(
        field_name = field_name,
        dedup_name = field_name,
        c_decl     = c_decl,
    )


def parse_function(spec: BlockSpec, tokens: list[Token], description: str) -> FunctDef | None:
    """
    Handle the 'function' declaration.
    Syntax: function <name>  /// description

    Function names are always plain identifiers, never templates.
    dedup_name is name + '_', consistent with pin field names, so that
    a function and a pin with the same base name are detected as a collision.
    """
    keyword = tokens[0]

    if len(tokens) != 2:
        report(Severity.ERROR,
               "'function' declaration should be 'function <name>'",
               token=keyword)
        return None

    name_tok = tokens[1]

    if not name_tok.text.isidentifier():
        report(Severity.ERROR,
               f"invalid function name: {name_tok.text!r}",
               token=name_tok)
        return None

    dedup_name = name_tok.text + '_'

    if dedup_name in spec.namespace:
        report(Severity.ERROR,
               f"duplicate name {name_tok.text!r} in block namespace",
               token=name_tok)
        return None

    return FunctDef(
        name        = name_tok.text,
        dedup_name  = dedup_name,
        description = description,
    )


# ---------------------------------------------------------------------------
# Statement dispatcher
# ---------------------------------------------------------------------------

def _wrap(spec: BlockSpec, state: ParseState, obj) -> None:
    """Wrap a parsed object in a Statement and append to spec."""
    if obj is not None:
        spec.namespace.add(obj.dedup_name)
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
            # generate dict of params and default values
            spec.defaults = { p.name : p.default for p in spec.params }
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
    elif keyword.text == "param":
        parse_param(spec, tokens, description)
    elif keyword.text == "pin":
        _wrap(spec, state, parse_pin(spec, tokens, description))
    elif keyword.text == "var":
        _wrap(spec, state, parse_var(spec, tokens, description))
    elif keyword.text == "function":
        _wrap(spec, state, parse_function(spec, tokens, description))

    elif keyword.text == "#if":
        if len(tokens) < 2:
            report(Severity.ERROR, "'#if' requires an expression", token=keyword)
        else:
            ifexpr = tokens[1]
            # validate #if expression - can contain only params, constants, operators
            try:
                val = evaluate(ifexpr.text, spec.defaults)
            except ExpressionError as e:
                report(Severity.ERROR, str(e), token=ifexpr)
                return
            state.if_stack.append(ifexpr.text)

    elif keyword.text == "#endif":
        if len(tokens) > 1:
            report(Severity.WARNING, "'#endif' takes no arguments", token=tokens[1])
        if not state.if_stack:
            report(Severity.ERROR, "'#endif' without matching '#if'", token=keyword)
        else:
            state.if_stack.pop()

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
            parse_statement(spec, state, pending_tokens, pending_description.rstrip())
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
    if _error_count > 0:
        return None
    return spec


# ---------------------------------------------------------------------------
# Test driver
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <file.bloc>", file=sys.stderr)
        sys.exit(1)

    block_spec = parse_bloc(sys.argv[1])
    if block_spec is not None:
        print(block_spec.describe())
    else:
        print("Parsing failed due to errors.", file=sys.stderr)
