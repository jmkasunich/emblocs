# bloc_resolver.py
# Resolves a BlockSpec against concrete parameter values to produce a BlockDef.
#
# The resolver walks the BlockSpec's ordered statements, evaluates #if
# conditions, expands array pins, and produces a flat BlockDef with
# concrete PinDef, VarDef, and FunctDef objects.

import sys
from emblocs import (
    BlockSpec, BlockDef,
    ParamSpec,
    PinSpec, PinDef, DimSpec,
    VarDef,
    FunctSpec, FunctDef,
    Statement,
    PinType, PinDir,
)
from expressions import evaluate, ExpressionError


# ---------------------------------------------------------------------------
# Error reporting
# ---------------------------------------------------------------------------

# Module-level state: context string for error messages.
# Reset at the start of each resolve() call.
_error_context: str = ""
_error_count:   int = 0
_warning_count: int = 0

def report(message: str, is_error: bool = True) -> None:
    """
    Report a resolver error or warning with block name context.
    Errors increment _error_count; warnings increment _warning_count.
    """
    global _error_count, _warning_count
    prefix = "error" if is_error else "warning"
    print(f"{_error_context}: {prefix}: {message}", file=sys.stderr)
    if is_error:
        _error_count += 1
    else:
        _warning_count += 1


# ---------------------------------------------------------------------------
# Parameter validation and variable dict construction
# ---------------------------------------------------------------------------

def _build_variables(spec: BlockSpec,
                     supplied: dict[str, int]) -> dict[str, int] | None:
    """
    Merge supplied parameter values with defaults from spec.params.
    Validate all values against their type and range constraints.
    Returns a complete variables dict, or None if any error was reported.
    """
    variables = {}

    # check for unknown supplied parameters
    known = {p.name for p in spec.params}
    for name in supplied:
        if name not in known:
            report(f"unknown parameter {name!r}")

    for param in spec.params:
        if param.name in supplied:
            val = supplied[param.name]
        else:
            val = param.default

        # validate type
        if param.param_type == "bool":
            if val not in (0, 1):
                report(f"parameter {param.name!r} is bool; "
                       f"value {val} is not 0 or 1", is_error=False)
        elif param.param_type == "u32":
            if val < param.min_val:
                report(f"parameter {param.name!r} value {val} "
                       f"is less than min ({param.min_val})")
            if val > param.max_val:
                report(f"parameter {param.name!r} value {val} "
                       f"is greater than max ({param.max_val})")

        variables[param.name] = val

    if _error_count > 0:
        return None
    return variables


# ---------------------------------------------------------------------------
# Statement expanders
# ---------------------------------------------------------------------------

def _recurse_pin(pin_spec: PinSpec, dims: list[DimSpec],
                variables: dict[str, int]) -> list[PinDef]:
    """
    Recursively expand a PinSpec into PinDef objects.
     dims is the list of remaining dimensions to expand; variables contains
     the current values of all index variables for the dimensions already
     expanded.

     Returns a list of PinDef objects for all slots of the pin for which
     the export condition is true.
    """
    if not dims:
        # base case: no more dimensions, produce a PinDef
        emblocs_name = _evaluate_template(pin_spec.emblocs_name, variables)
        if emblocs_name is None:
            return []
        if pin_spec.export_condition is not None:
            try:
                exported = evaluate(pin_spec.export_condition, variables)
            except ExpressionError as e:
                report(f"export condition error in pin "
                       f"{pin_spec.emblocs_name!r}: {e}")
                return []
            if not exported:
                return []
        return [PinDef(
            emblocs_name = emblocs_name,
            field_name   = pin_spec.field_name,
            pin_type     = pin_spec.pin_type,
            direction    = pin_spec.direction,
            field_indices = tuple(variables[dim.index_var] for dim in pin_spec.dims),
            description  = pin_spec.description,
        )]
    else:
        # recursive case: expand the next dimension
        dim = dims[0]
        try:
            size = evaluate(dim.size_expr, variables)
        except ExpressionError as e:
            report(f"dimension size error in pin "
                   f"{pin_spec.emblocs_name!r}: {e}")
            return []
        results = []
        for idx in range(size):
            slot_vars = {**variables, dim.index_var: idx}
            results.extend(_recurse_pin(pin_spec, dims[1:], slot_vars))
        return results


def _expand_pin(pin_spec: PinSpec,
                variables: dict[str, int]) -> list[PinDef]:
    """
    Expand a PinSpec into one or more PinDef objects.

    For scalar pins, returns a single PinDef.
    For array pins, iterates all dimension index variables and returns
    one PinDef per slot for which the export condition is true.
    """
    return _recurse_pin(pin_spec, pin_spec.dims, variables)


def _expand_var(var_def: VarDef,
                variables: dict[str, int]) -> list[VarDef]:
    """
    Pass a VarDef through unchanged.
    Variables dict is unused but present for dispatcher symmetry.
    """
    return [var_def]


def _expand_funct(funct_spec: FunctSpec,
                  variables: dict[str, int]) -> list[FunctDef]:
    """
    Convert a FunctSpec to a FunctDef.
    Variables dict is unused but present for dispatcher symmetry.
    """
    return [FunctDef(
        name        = funct_spec.name,
        description = funct_spec.description,
    )]


def _expand_statement(statement: Statement,
                      variables: dict[str, int]) -> list:
    """
    Evaluate #if conditions for a statement, then dispatch to the
    appropriate expander.  Returns an empty list if any condition
    is false or if an error occurs.
    """
    # evaluate all active #if conditions
    for cond in statement.conditions:
        try:
            result = evaluate(cond, variables)
        except ExpressionError as e:
            report(f"condition expression error {cond!r}: {e}")
            return []
        if not result:
            return []

    obj = statement.statement
    if isinstance(obj, PinSpec):
        return _expand_pin(obj, variables)
    elif isinstance(obj, VarDef):
        return _expand_var(obj, variables)
    elif isinstance(obj, FunctSpec):
        return _expand_funct(obj, variables)
    else:
        report(f"unknown statement type: {type(obj).__name__}")
        return []


# ---------------------------------------------------------------------------
# Template evaluation
# ---------------------------------------------------------------------------

import re

_TEMPLATE_SPEC_RE = re.compile(r"""
    \{              # opening brace
    (?P<expr>       # expression
        [^}:]+
    )
    :               # colon separator
    (?P<width>      # width digit
        [1-9]
    )
    \}              # closing brace
""", re.VERBOSE)


def _evaluate_template(template: str,
                       variables: dict[str, int]) -> str | None:
    """
    Evaluate all {expr:N} format specifiers in a template string,
    substituting the integer result zero-padded to N digits.
    Returns the expanded string, or None if any expression fails.
    """
    result = template
    for m in _TEMPLATE_SPEC_RE.finditer(template):
        expr_str = m.group('expr')
        width    = int(m.group('width'))
        try:
            val = evaluate(expr_str, variables)
        except ExpressionError as e:
            report(f"template expression error {expr_str!r}: {e}")
            return None
        result = result.replace(m.group(0), str(int(val)).zfill(width), 1)
    return result


# ---------------------------------------------------------------------------
# Top-level resolver
# ---------------------------------------------------------------------------

def resolve(spec: BlockSpec, variant_name: str,
            supplied_params: dict[str, int] | None = None,
            error_context: str | None = None) -> BlockDef | None:
    """
    Resolve a BlockSpec against concrete parameter values to produce a BlockDef.

    supplied_params -- dict of param name -> value; parameters not supplied
                       use their default values from spec.params.
                       Pass None or {} to use all defaults.

    Returns a BlockDef, or None if any error was reported.
    """
    global _error_context, _error_count, _warning_count
    _error_context = error_context if error_context is not None else variant_name
    _error_count   = 0
    _warning_count = 0

    if not variant_name.isidentifier():
        report(f"invalid variant name {variant_name!r}")
        return None

    if supplied_params is None:
        supplied_params = {}

    variables = _build_variables(spec, supplied_params)
    if variables is None:
        return None

    ordered_declarations = []
    pins      = {}
    functions = {}

    for statement in spec.statements:
        expanded = _expand_statement(statement, variables)
        for obj in expanded:
            ordered_declarations.append(obj)
            if isinstance(obj, PinDef):
                if obj.emblocs_name in pins:
                    report(f"duplicate pin name {obj.emblocs_name!r} "
                           f"after resolution")
                else:
                    pins[obj.emblocs_name] = obj
            elif isinstance(obj, FunctDef):
                if obj.name in functions:
                    report(f"duplicate function name {obj.name!r} "
                           f"after resolution")
                else:
                    functions[obj.name] = obj

    print(f"{_error_context}: "
          f"{_error_count} error(s), {_warning_count} warning(s)",
          file=sys.stderr)

    if _error_count > 0:
        return None

    return BlockDef(
        name                 = variant_name,
        source_path          = spec.source_path,
        description          = spec.description,
        params               = variables,
        pins                 = pins,
        functions            = functions,
        ordered_declarations = ordered_declarations,
    )


# ---------------------------------------------------------------------------
# Test driver
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import os
    from bloc_parser import parse_bloc

    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <file.bloc> [variant_name] [PARAM=value ...]",
              file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    remaining = sys.argv[2:]

    # optional variant name (first non-param argument)
    if remaining and "=" not in remaining[0]:
        variant_name = remaining[0]
        remaining = remaining[1:]
    else:
        variant_name = os.path.splitext(os.path.basename(path))[0]

    # remaining arguments are PARAM=value pairs
    supplied = {}
    for arg in remaining:
        if "=" not in arg:
            print(f"error: expected PARAM=value, got {arg!r}",
                  file=sys.stderr)
            sys.exit(1)
        name, _, value = arg.partition("=")
        try:
            supplied[name] = int(value, 0)
        except ValueError:
            print(f"error: invalid value {value!r} for parameter {name!r}",
                  file=sys.stderr)
            sys.exit(1)

    spec = parse_bloc(path)
    if spec is None:
        sys.exit(1)

    block_def = resolve(spec, variant_name, supplied )
    if block_def is None:
        sys.exit(1)

    print(block_def.describe())
