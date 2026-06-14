# bloc_parser.py
# Parser for .bloc block template files.
# Reads a .bloc file and returns a BlockSpec object.
#
from __future__ import annotations
import sys
import re
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum, auto
from emblocs import (BlockSpec, ParamSpec, Statement, PinSpec,
                     DimSpec, VarDef, FunctSpec, PinType, PinDir, U32_MAX)
from expressions import evaluate, ExpressionError
from parse_common import (Token, tokenize_line,
                          ctx, OMIT,
                          read_source_file, read_source_string)

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
# Parser state
# ---------------------------------------------------------------------------

class Section(Enum):
    BLOCK  = auto()
    PARAMS = auto()
    BODY   = auto()

_ALLOWED = {
    Section.BLOCK:  {"block"},
    Section.PARAMS: {"param", "include"},
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
        ctx.error("'block' declared more than once", token=keyword)
        return
    if len(tokens) < 2:
        ctx.error("'block' declaration requires a name", token=keyword)
        return
    name_tok = tokens[1]
    if not name_tok.text.isidentifier():
        ctx.error(f"invalid block name: {name_tok.text!r}", token=name_tok)
        return
    spec.name        = name_tok.text
    spec.description = description

def parse_param(spec: BlockSpec, tokens: list[Token], description: str) -> None:
    """
    Handle the 'param' declaration.
    Syntax: param <type> <NAME> default=<value> [min=<value>] [max=<value>]
    Appends a ParamSpec to spec.params, or reports errors and returns.
    """
    keyword = tokens[0]

    if len(tokens) < 4:
        ctx.error("'param' requires name, type, and default=value",
                  token=keyword)
        return

    type_tok = tokens[1]
    name_tok = tokens[2]

    if type_tok.text not in ("bool", "u32"):
        ctx.error(f"invalid parameter type {type_tok.text!r}; "
                  f"expected 'bool' or 'u32'", token=type_tok)
        return
    param_type = type_tok.text

    if not name_tok.text.isidentifier():
        ctx.error(f"invalid parameter name: {name_tok.text!r}",
                  token=name_tok)
        return

    if any(p.name == name_tok.text for p in spec.params):
        ctx.error(f"duplicate parameter name: {name_tok.text!r}",
                  token=name_tok)
        return

    # parse key=value tokens for default, min, max
    default = None
    min_val = 0
    max_val = U32_MAX

    for tok in tokens[3:]:
        key, sep, val_str = tok.text.partition("=")
        if key not in ("default", "min", "max") or sep != "=":
            ctx.error(f"unexpected token {tok.text!r}; "
                      f"expected 'default=', 'min=', or 'max='",
                      token=tok)
            return
        if not val_str:
            ctx.error(f"missing value after '{key}='", token=tok)
            return

        try:
            val = evaluate(val_str)
        except ExpressionError as e:
            ctx.error(f"bad {key}: {str(e)}", token=tok)
            return

        if param_type == "u32":
            if val < 0 or val > U32_MAX:
                ctx.error(f"{key} value {val} is out of range for u32 "
                          f"[0, {U32_MAX}]", token=tok)
                return
        elif param_type == "bool":
            if val not in (0, 1):
                ctx.warning(f"{key} value {val} is not 0 or 1 for bool parameter",
                            token=tok)

        if key == "default" and default is None:
            default = val
        elif key == "min" and min_val == 0:
            min_val = val
        elif key == "max" and max_val == U32_MAX:
            max_val = val
        else:
            ctx.error(f"duplicate '{key}=' token", token=tok)
            return

    if default is None:
        ctx.error(f"'param' requires a 'default=' value",
                  lineno=keyword.line, column=OMIT)
        return

    if min_val != 0 and param_type == "bool":
        ctx.warning("'min' is not meaningful for bool parameters",
                    lineno=keyword.line, column=OMIT)
    if max_val != U32_MAX and param_type == "bool":
        ctx.warning("'max' is not meaningful for bool parameters",
                    lineno=keyword.line, column=OMIT)

    # cross-validate min, max, default
    if min_val > max_val:
        ctx.error(f"min ({min_val}) is greater than max ({max_val})",
                  lineno=keyword.line, column=OMIT)
        return

    if default < min_val:
        ctx.error(f"default ({default}) is less than min ({min_val})",
                  lineno=keyword.line, column=OMIT)
        return

    if default > max_val:
        ctx.error(f"default ({default}) is greater than max ({max_val})",
                  lineno=keyword.line, column=OMIT)
        return

    spec.params.append(ParamSpec(
        name        = name_tok.text,
        param_type  = param_type,
        default     = default,
        min_val     = min_val,
        max_val     = max_val,
        description = description,
    ))


def _is_valid_include_path(text: str) -> bool:
    if len(text) < 3:
        return False
    if text[0] == '"' and text[-1] == '"':
        return True
    if text[0] == '<' and text[-1] == '>':
        return True
    return False

def parse_include(spec: BlockSpec, tokens: list[Token], description: str) -> None:
    """
    Handle the 'include' declaration.
    Syntax: include <NAME> or include "NAME"
    Appends full name token to spec.includes, or reports errors and returns.
    """
    keyword = tokens[0]

    if len(tokens) < 2:
        ctx.error("'include' requires include filename",
                  token=keyword)
        return

    name_tok = tokens[1]
    name = name_tok.text
    if not _is_valid_include_path(name):
        ctx.error(f"invalid include path: {name!r}",
                  token=name_tok)
        return
    spec.includes.append(name)

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
        ctx.error(f"'pin' declaration must have 4 or 6 tokens, got {len(tokens)}",
                  lineno=keyword.line, column=OMIT)
        return None

    # token assignment
    type_tok    = tokens[1]
    dir_tok     = tokens[2]
    name_tok    = tokens[3]
    if_tok      = tokens[4] if len(tokens) == 6 else None
    if_cond_tok = tokens[5] if len(tokens) == 6 else None

    # validate type and direction
    if type_tok.text not in PIN_TYPES:
        ctx.error(f"unknown pin type {type_tok.text!r}; "
                  f"expected one of {list(PIN_TYPES)}", token=type_tok)
        return None
    if dir_tok.text not in PIN_DIRS:
        ctx.error(f"unknown pin direction {dir_tok.text!r}; "
                  f"expected 'input' or 'output'", token=dir_tok)
        return None

    # split name/template from dimension specifiers
    # e.g. "ch{i:2}_out[i=NCHAN]" -> template="ch{i:2}_out", dim_strings=["i=NCHAN]"]
    template, *dim_strings = name_tok.text.split('[')
    ctx.set(token=name_tok)
    if not template:
        ctx.error("pin name/template cannot be empty")
        return None
    # parse dimension specifiers, collecting index variables
    dims = []
    template_vars = dict(spec.defaults)   # copy, grows as index vars are added
    for dim_string in dim_strings:
        if not dim_string.endswith(']'):
            ctx.error(f"missing closing ']' in dimension {dim_string!r}")
            return None
        dim_string = dim_string[:-1]  # strip closing ']'
        index, sep, expr = dim_string.partition('=')
        if sep != '=':
            ctx.error(f"missing '=' in dimension {dim_string!r}")
            return None
        if not index.isidentifier():
            ctx.error(f"invalid index variable {index!r}")
            return None
        if index in template_vars:
            ctx.error(f"index variable name {index!r} already in use")
            return None
        if not expr:
            ctx.error(f"missing size in dimension {dim_string!r}")
            return None
        # validate dimension size expression using params
        try:
            val=evaluate(expr, spec.defaults)
        except ExpressionError as e:
            ctx.error(f"invalid dimension: {str(e)}")
            return None
        if val < 1:
            ctx.error(f"invalid dimension: {val}; must be at least 1")
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
        ctx.error(f"malformed template specifier in {template!r}; "
                  f"expected {{expr:N}} where N is 1-9")
        return None

    # field_name (with trailing _) must be a valid C identifier
    if not field_name.isidentifier():
        ctx.error(f"template {template!r} produces invalid field name {field_name!r}")
        return None

    dedup_name = field_name

    # check for duplicate in namespace
    if dedup_name in spec.namespace:
        ctx.error(f"duplicate name {dedup_name!r} in block namespace")
        return None

    # validate each specifier's expression
    for m in _TEMPLATE_SPEC_RE.finditer(template):
        expr_str = m.group('expr')
        try:
            evaluate(expr_str, template_vars)
        except ExpressionError as e:
            ctx.error(f"invalid template: {str(e)}")
            return None

    # parse optional trailing export condition
    export_cond = None
    if if_tok is not None:
        if if_tok.text != "if":
            ctx.error(f"expected 'if', got {if_tok.text!r}", token=if_tok)
            return None
        # validate export condition using params + index vars
        try:
            evaluate(if_cond_tok.text, template_vars)
        except ExpressionError as e:
            ctx.error(f"invalid 'if' condition: {str(e)}", token=if_cond_tok)
            return None
        export_cond = if_cond_tok.text

    return PinSpec(
        name_template    = template,
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
        ctx.error("'var' statement requires a C declaration", token=keyword)
        return None

    # reconstruct C declaration from tokens (whitespace not preserved)
    c_decl = " ".join(t.text for t in tokens[1:])

    if not c_decl.endswith(";"):
        ctx.error("'var' declaration must end with a semicolon", token=tokens[-1])
        return None

    # extract field name from last token before semicolon
    last_tok = tokens[-1]
    # strip leading '*' (pointer declarations) and everything from '[' onward (arrays)
    field_name = last_tok.text.rstrip(";").lstrip("*").split("[")[0]

    if not field_name.isidentifier():
        ctx.error(f"could not extract valid field name from 'var' declaration; "
                  f"got {field_name!r}", token=last_tok)
        return None

    # check for duplicate in namespace
    if field_name in spec.namespace:
        ctx.error(f"duplicate name {field_name!r} in block namespace", token=last_tok)
        return None

    return VarDef(
        field_name = field_name,
        dedup_name = field_name,
        c_decl     = c_decl,
    )


def parse_function(spec: BlockSpec, tokens: list[Token], description: str) -> FunctSpec | None:
    """
    Handle the 'function' declaration.
    Syntax: function <name>  /// description

    Function names are always plain identifiers, never templates.
    dedup_name is name + '_', consistent with pin field names, so that
    a function and a pin with the same base name are detected as a collision.
    """
    keyword = tokens[0]

    if len(tokens) != 2:
        ctx.error("'function' declaration should be 'function <name>'",
                  token=keyword)
        return None

    name_tok = tokens[1]

    if not name_tok.text.isidentifier():
        ctx.error(f"invalid function name: {name_tok.text!r}", token=name_tok)
        return None

    dedup_name = name_tok.text + '_'

    if dedup_name in spec.namespace:
        ctx.error(f"duplicate name {name_tok.text!r} in block namespace",
                  token=name_tok)
        return None

    return FunctSpec(
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
        ctx.error(f"unexpected keyword {keyword.text!r} in current section",
                  token=keyword)
        return

    # Step 3: dispatch
    if keyword.text == "block":
        parse_block(spec, tokens, description)
    elif keyword.text == "param":
        parse_param(spec, tokens, description)
    elif keyword.text == "include":
        parse_include(spec, tokens, description)
    elif keyword.text == "pin":
        _wrap(spec, state, parse_pin(spec, tokens, description))
    elif keyword.text == "var":
        _wrap(spec, state, parse_var(spec, tokens, description))
    elif keyword.text == "function":
        _wrap(spec, state, parse_function(spec, tokens, description))

    elif keyword.text == "#if":
        if len(tokens) < 2:
            ctx.error("'#if' requires an expression", token=keyword)
        else:
            ifexpr = tokens[1]
            # validate #if expression - can contain only params, constants, operators
            try:
                val = evaluate(ifexpr.text, spec.defaults)
            except ExpressionError as e:
                ctx.error(f"bad #if condition: {str(e)}", token=ifexpr)
                return
            state.if_stack.append(ifexpr.text)

    elif keyword.text == "#endif":
        if len(tokens) > 1:
            ctx.warning("'#endif' takes no arguments", token=tokens[1])
        if not state.if_stack:
            ctx.error("'#endif' without matching '#if'", token=keyword)
        else:
            state.if_stack.pop()

    else:
        ctx.error(f"unrecognized token: {keyword.text!r}", token=keyword)


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_bloc(lines: list[str]) -> BlockSpec | None:
    """
    Parse a list of source lines and return a populated BlockSpec.
    Expects an active ErrorContext (pushed by parse_bloc_file or
    parse_bloc_string).
    """
    spec  = BlockSpec(abs_path=Path(ctx.source).resolve().as_posix())
    state = ParseState()
    pending_tokens:      list[Token] = []
    pending_description: str         = ""

    def flush():
        nonlocal pending_tokens, pending_description
        if pending_tokens:
            parse_statement(spec, state, pending_tokens,
                            pending_description.rstrip().strip("\n"))
        pending_tokens      = []
        pending_description = ""

    for lineno, line in enumerate(lines, start=1):
        # split token section from comment/description
        first_part, sep, last_part = line.partition("//")
        new_tokens = tokenize_line(first_part, lineno)
        # determine if last part is description or comment/nothing
        if last_part.startswith("/"):
            new_description = last_part[1:]
        else:
            new_description = ""
        # apply language rules
        if pending_description and new_description and not new_tokens:
            # description continuation line
            pending_description += new_description
        else:
            # any previous statement is now complete
            flush()
            if new_description and not new_tokens:
                # misplaced description
                ctx.error("Misplaced description",
                          lineno=lineno, column=len(first_part))
            elif new_tokens:
                # new statement
                pending_tokens      = new_tokens
                pending_description = new_description
            # else: empty line or comment-only line, do nothing
    # end of input
    flush()
    if spec.name == "" and ctx.no_errors():
        ctx.error("no 'block' declaration found", lineno=OMIT)
    if state.if_stack:
        ctx.error(f"end-of-file with {len(state.if_stack)} "
                  f"unterminated '#if' statements", lineno=OMIT)
    return spec if ctx.no_errors() else None


def parse_bloc_file(path: str) -> BlockSpec | None:
    """
    Parse a .bloc file and return a populated BlockSpec.
    Convenience wrapper around read_source_file() and parse_bloc().
    Returns None if the file could not be read or parsing failed.
    """
    lines = read_source_file(path)
    if lines is None:
        ctx.summarize()
        ctx.pop()
        return None
    result = parse_bloc(lines)
    if not ctx.is_clean():
        ctx.summarize()
    ctx.pop()
    return result


def parse_bloc_string(text: str, source: str = "<string>") -> BlockSpec | None:
    """
    Parse a .bloc string and return a populated BlockSpec.
    Convenience wrapper around read_source_string() and parse_bloc().
    Returns None if the string contains encoding errors or parsing failed.
    """
    lines = read_source_string(text, source=source)
    if lines is None:
        ctx.pop()
        return None
    result = parse_bloc(lines)
    ctx.pop()
    return result


# ---------------------------------------------------------------------------
# Test driver
# ---------------------------------------------------------------------------

if __name__ == "__main__":   # pragma: no cover
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <file.bloc>", file=sys.stderr)
        sys.exit(1)

    block_spec = parse_bloc_file(sys.argv[1])
    if block_spec is not None:
        print(block_spec)
    else:
        print("Parsing failed due to errors.", file=sys.stderr)
