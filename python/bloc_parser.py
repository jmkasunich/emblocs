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


# ---------------------------------------------------------------------------
# Error reporting
# ---------------------------------------------------------------------------

def parse_error(path: str, lineno: int, message: str) -> None:
    """Print a parse error with file and line context, then exit."""
    print(f"{path}:{lineno}: error: {message}", file=sys.stderr)
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

def strip_description(line: str) -> tuple[str, str]:
    """
    Split a line into its code portion and its /// description text.

    Returns (code, description) where:
      - description is the text after the first '///' on the line, with one
        leading separator space removed and trailing whitespace stripped.
        Remaining leading whitespace is preserved so block authors can indent
        multi-line descriptions.  Returns "" if no '///' is present.
      - code is everything before the '///' (stripped), with any trailing
        '//' comment also removed.

    Examples:
      "pin float input in  /// value to clamp"  -> ("pin float input in", "value to clamp")
      "pin float input in  // plain comment"     -> ("pin float input in", "")
      "/// block description"                    -> ("", "block description")
      "///   indented continuation"              -> ("", "  indented continuation")
    """
    # Look for /// first (/// takes priority over plain //)
    idx = line.find("///")
    if idx != -1:
        description = line[idx + 3:].rstrip()
        if description.startswith(" "):
            description = description[1:]   # strip exactly one separator space
        code = line[:idx].strip()
        return code, description

    # No ///, strip any plain // comment
    idx = line.find("//")
    if idx != -1:
        line = line[:idx]

    return line.strip(), ""


def tokenize(code: str) -> list[str]:
    """Split a code string into whitespace-separated tokens."""
    return code.split()


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_bloc(path: str) -> BlockSpec:
    """
    Parse a .bloc file and return a populated BlockSpec.

    Every .bloc file must contain exactly one 'block' declaration giving
    the block's name and optional description.  All other declarations
    (pin, var, function, param) may appear in any order.

    Raises SystemExit (via parse_error) on any syntax or semantic error.
    """
    spec = BlockSpec(source_path=path)

    # pending_* holds the fields for a declaration that has been parsed but
    # not yet finalized, because the next line may continue its /// description.
    #
    # pending_kind is one of: None, "block", "pin", "function"
    # (var does not use the pending machinery as it takes no /// description)
    pending_kind:        str | None = None
    pending_fields:      dict       = {}
    pending_description: str        = ""

    def finalize_pending():
        """Construct and store the object for the current pending declaration."""
        nonlocal pending_kind, pending_fields, pending_description
        if pending_kind is None:
            return
        if pending_kind == "block":
            spec.name        = pending_fields["name"]
            spec.description = pending_description
        elif pending_kind == "pin":
            spec.struct_members.append(PinSpec(
                field_name   = pending_fields["field_name"],
                emblocs_name = pending_fields["emblocs_name"],
                pin_type     = pending_fields["pin_type"],
                direction    = pending_fields["direction"],
                dims         = pending_fields["dims"],
                description  = pending_description,
            ))
        elif pending_kind == "function":
            spec.functions.append(FunctDef(
                name        = pending_fields["name"],
                description = pending_description,
            ))
        pending_kind        = None
        pending_fields      = {}
        pending_description = ""

    def set_pending(kind: str, fields: dict, description: str):
        """Finalize any previous pending item, then set a new one."""
        finalize_pending()
        nonlocal pending_kind, pending_fields, pending_description
        pending_kind        = kind
        pending_fields      = fields
        pending_description = description

    # Read the file, checking for non-ASCII bytes
    try:
        with open(path, "r", encoding="ascii") as f:
            raw_lines = f.readlines()
    except UnicodeDecodeError as e:
        print(f"{path}: error: non-ASCII character in file: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"{path}: error: file not found", file=sys.stderr)
        sys.exit(1)

    for lineno, raw_line in enumerate(raw_lines, start=1):
        line = raw_line.rstrip("\r\n")
        code, description = strip_description(line)
        tokens = tokenize(code)

        # --- Blank line -----------------------------------------------------
        if not tokens and not description:
            finalize_pending()
            continue

        # --- Description-only line (bare ///) --------------------------------
        if not tokens and description:
            if pending_kind is not None:
                # Continue the /// description of the current pending declaration.
                pending_description = (pending_description + "\n" + description
                                       if pending_description else description)
            # A bare /// with no pending declaration is treated as a plain comment.
            continue

        # --- Declaration line (tokens present) ------------------------------
        keyword = tokens[0]

        # Unsupported preprocessor directives
        if keyword in ("#if", "#endif"):
            parse_error(path, lineno,
                        f"'{keyword}' is not yet supported by this parser")

        # 'for' loop
        if keyword == "for":
            parse_error(path, lineno,
                        "'for' loops are not yet supported by this parser")

        # 'param' declaration
        if keyword == "param":
            parse_error(path, lineno,
                        "'param' declarations are not yet supported by this parser")

        # 'init' declaration
        if keyword == "init":
            parse_error(path, lineno,
                        "'init' declarations are not yet supported by this parser")

        # 'block' declaration ------------------------------------------------
        if keyword == "block":
            if spec.name:
                parse_error(path, lineno,
                            "'block' declared more than once")
            if len(tokens) < 2:
                parse_error(path, lineno,
                            "'block' declaration requires a name")
            block_name = tokens[1]
            if not block_name.isidentifier():
                parse_error(path, lineno,
                            f"invalid block name: {block_name!r}")
            set_pending("block", {"name": block_name}, description)
            continue

        # 'pin' declaration --------------------------------------------------
        if keyword == "pin":
            if len(tokens) < 4:
                parse_error(path, lineno,
                            "'pin' declaration needs at least type, direction, "
                            f"and field name; got: {code!r}")
            type_str  = tokens[1]
            dir_str   = tokens[2]
            field_str = tokens[3]

            if type_str not in PIN_TYPES:
                parse_error(path, lineno,
                            f"unknown pin type {type_str!r}; "
                            f"expected one of {list(PIN_TYPES)}")
            if dir_str not in PIN_DIRS:
                parse_error(path, lineno,
                            f"unknown pin direction {dir_str!r}; "
                            f"expected 'input' or 'output'")

            # For now we only support scalar pins (no brackets).
            if "[" in field_str:
                parse_error(path, lineno,
                            "array pin dimensions are not yet supported; "
                            f"field: {field_str!r}")
            field_name = field_str

            # Optional name template; defaults to field name for scalar pins.
            emblocs_name = tokens[4] if len(tokens) >= 5 else field_name

            set_pending("pin", {
                "field_name":   field_name,
                "emblocs_name": emblocs_name,
                "pin_type":     PIN_TYPES[type_str],
                "direction":    PIN_DIRS[dir_str],
                "dims":         [],          # [] = scalar
            }, description)
            continue

        # 'var' declaration --------------------------------------------------
        if keyword == "var":
            # var takes no /// description; finalize any pending item first.
            finalize_pending()

            rest = code[code.index("var") + 3:].strip()
            if not rest.endswith(";"):
                parse_error(path, lineno,
                            f"'var' declaration must end with a semicolon: {code!r}")
            c_decl = rest[:-1].strip()
            if not c_decl:
                parse_error(path, lineno, "'var' declaration has no C declaration")

            # Extract the field name from the C declaration.
            # Takes the last whitespace-separated token, strips leading '*'
            # (pointer declarations) and trailing '[' (array declarations).
            # Deliberately simple; will need revisiting for complex C types.
            decl_tokens = c_decl.split()
            if len(decl_tokens) < 2:
                parse_error(path, lineno,
                            f"cannot extract field name from 'var' declaration: "
                            f"{c_decl!r}")
            field_name = decl_tokens[-1].lstrip("*").split("[")[0]
            if not field_name.isidentifier():
                parse_error(path, lineno,
                            f"could not parse field name from 'var' declaration: "
                            f"{c_decl!r}")

            spec.struct_members.append(VarDef(
                field_name = field_name,
                c_decl     = c_decl,
            ))
            continue

        # 'function' declaration ---------------------------------------------
        if keyword == "function":
            if len(tokens) < 2:
                parse_error(path, lineno,
                            "'function' declaration requires a name")
            func_name = tokens[1]
            if not func_name.isidentifier():
                parse_error(path, lineno,
                            f"invalid function name: {func_name!r}")
            set_pending("function", {"name": func_name}, description)
            continue

        # Unknown keyword ----------------------------------------------------
        parse_error(path, lineno, f"unrecognized declaration: {tokens[0]!r}")

    # End of file: finalize any trailing pending item
    finalize_pending()

    # Every .bloc file must have exactly one 'block' declaration.
    if not spec.name:
        print(f"{path}: error: no 'block' declaration found", file=sys.stderr)
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