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
from emblocs import BlockSpec, PinSpec, VarDef, FunctDef, PinType, PinDir
import re
from collections import namedtuple

Token = namedtuple("Token", ["text", "line", "column"])

# ---------------------------------------------------------------------------
# Error reporting
# ---------------------------------------------------------------------------

def parse_error(path: str, lineno: int, column: int, message: str) -> None:
    """Print an error message with file and line context, then exit."""
    print(f"{path}:{lineno}:{column} error: {message}", file=sys.stderr)
    sys.exit(1)


def parse_error_tok(path: str, token: Token, message: str) -> None:
    """Print an error message using Token location"""
    parse_error(path, token.line, token.column, message)

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
# Per-keyword parse functions
# ---------------------------------------------------------------------------

def parse_block(path: str, spec: BlockSpec,
                tokens: list[Token], description: str) -> None:
    """Handle the 'block' declaration."""
    keyword = tokens[0]
    if spec.name:
        parse_error_tok(path, keyword, "'block' declared more than once")
    if len(tokens) < 2:
        parse_error_tok(path, keyword, "'block' declaration requires a name")
    name_tok = tokens[1]
    if not name_tok.text.isidentifier():
        parse_error_tok(path, name_tok,
                        f"invalid block name: {name_tok.text!r}")
    spec.name        = name_tok.text
    spec.description = description


def parse_pin(path: str, spec: BlockSpec,
              tokens: list[Token], description: str) -> None:
    """Handle the 'pin' declaration."""
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


def parse_var(path: str, spec: BlockSpec,
              tokens: list[Token], description: str) -> None:
    """Handle the 'var' declaration."""
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


def parse_function(path: str, spec: BlockSpec,
                   tokens: list[Token], description: str) -> None:
    """Handle the 'function' declaration."""
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

def parse_statement(path, spec, tokens, description):
    print(f"STATEMENT: {[t.text for t in tokens]}")
    if description:
        print(f"  DESCRIPTION: {description!r}")

def parse_statement_bak(path: str, spec: BlockSpec,
                    tokens: list[Token], description: str) -> None:
    """
    Dispatch a complete statement to the appropriate per-keyword handler.

    tokens is guaranteed non-empty.  description may be "".
    """
    keyword = tokens[0]

    if keyword.text == "block":
        parse_block(path, spec, tokens, description)
    elif keyword.text == "pin":
        parse_pin(path, spec, tokens, description)
    elif keyword.text == "var":
        parse_var(path, spec, tokens, description)
    elif keyword.text == "function":
        parse_function(path, spec, tokens, description)

    # Unsupported but recognized keywords
    elif keyword.text == "param":
        parse_error_tok(path, keyword,
                        "'param' declarations are not yet supported")
    elif keyword.text == "init":
        parse_error_tok(path, keyword,
                        "'init' declarations are not yet supported")
    elif keyword.text in ("#if", "#endif"):
        parse_error_tok(path, keyword,
                        f"'{keyword.text}' is not yet supported")
    elif keyword.text == "for":
        parse_error_tok(path, keyword,
                        "'for' loops are not yet supported")

    else:
        parse_error_tok(path, keyword,
                        f"unrecognized declaration: {keyword.text!r}")


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
    spec = BlockSpec(source_path=path)
    pending_tokens: list[Token] = []
    pending_description: str = ""

    def flush():
        """
        If there are pending tokens, call parse_statement(),
        then reset to process next statement.
        """
        nonlocal pending_tokens, pending_description
        if pending_tokens:
            parse_statement(path, spec, pending_tokens, pending_description)
        pending_tokens      = []
        pending_description = ""

    try:
        with open(path, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                if not line.isascii():
                    parse_error(path, lineno, 1,
                                "Non-ASCII character found")

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
                        parse_error(path, lineno, len(first_part) + 1,
                                    "Misplaced description")
                    elif new_tokens :
                        # new statement
                        pending_tokens = new_tokens
                        pending_description = new_description
                    else :
                        # empty line or comment-only line
                        pass
            # end of file, process pending if any
            flush()

    except UnicodeDecodeError:
        print(f"{path}: error: Unicode decode error", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"{path}: error: File not found", file=sys.stderr)
        sys.exit(1)

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
