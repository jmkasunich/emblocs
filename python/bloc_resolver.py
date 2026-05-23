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
    PinSpec, FieldDef, PinDef, DimSpec,
    VarDef,
    FunctSpec, FunctDef,
    Statement,
    PinType, PinDir,
)
from expressions import evaluate, ExpressionError
from parse_common import ( ctx, OMIT)

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

    for param in spec.params:
        # get supplied value or default
        val = supplied.get(param.name, param.default)
        # validate type and range
        if param.param_type == "bool":
            if val not in (0, 1):
                ctx.warning(f"parameter {param.name!r} is bool; "
                            f"value {val} is not 0 or 1", column=OMIT)
        elif param.param_type == "u32":
            if val < param.min_val:
                ctx.error(f"parameter {param.name!r} value {val} "
                          f"is less than min ({param.min_val})", column=OMIT)
            if val > param.max_val:
                ctx.error(f"parameter {param.name!r} value {val} "
                          f"is greater than max ({param.max_val})", column=OMIT)
        # save value
        variables[param.name] = val
    return variables


# ---------------------------------------------------------------------------
# Statement expanders
# ---------------------------------------------------------------------------

def _recurse_pin(pin_spec: PinSpec, dims: list[DimSpec],
                variables: dict[str, int], field: FieldDef) -> list[PinDef]:
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
        name = _evaluate_template(pin_spec.name_template, variables)
        if name is None:
            return []
        if pin_spec.export_condition is not None:
            try:
                exported = evaluate(pin_spec.export_condition, variables)
            except ExpressionError as e:
                ctx.error(f"export condition error in pin "
                          f"{pin_spec.name_template!r}: {e}")
                return []
            if not exported:
                return []
        return [PinDef(
            name         = name,
            field        = field,
            field_indices = tuple(variables[dim.index_var] for dim in pin_spec.dims),
            description  = pin_spec.description,
        )]
    else:
        # recursive case: expand the next dimension
        dim = dims[0]
        dim_index = len(pin_spec.dims) - len(dims)
        size = field.dims[dim_index]
        results = []
        for idx in range(size):
            slot_vars = {**variables, dim.index_var: idx}
            results.extend(_recurse_pin(pin_spec, dims[1:], slot_vars, field))
        return results


def _expand_pin(pin_spec: PinSpec,
                variables: dict[str, int]) -> tuple[FieldDef, list[PinDef]]:
    """
    Expand a PinSpec into a FieldDef and one or more PinDef objects.

    For scalar pins, returns a single PinDef.
    For array pins, iterates all dimension index variables and returns
    one PinDef per slot for which the export condition is true.
    """
    # evaluate concrete dimension sizes for the FieldDef
    dims = []
    for d in pin_spec.dims:
        try:
            dims.append(evaluate(d.size_expr, variables))
        except ExpressionError as e:
            ctx.error(f"dimension size error in pin {pin_spec.name_template!r}: {e}")
            return None, []
    field = FieldDef(
        name      = pin_spec.field_name,
        dims      = tuple(dims),
        pin_type  = pin_spec.pin_type,
        direction = pin_spec.direction,
        c_decl    = None,
    )
    return field, _recurse_pin(pin_spec, pin_spec.dims, variables, field)


def _expand_var(var_def: VarDef,
                variables: dict[str, int]) -> tuple[FieldDef, list[VarDef]]:
    """
    Expand a VarDef into a FieldDef and a list containing the VarDef.
    Variables dict is unused but present for dispatcher symmetry.
    """
    field = FieldDef(
        name      = var_def.field_name,
        dims      = (),
        pin_type  = None,
        direction = None,
        c_decl    = var_def.c_decl,
    )
    return field, [var_def]


def _expand_funct(funct_spec: FunctSpec,
                  variables: dict[str, int]) -> tuple[None, list[FunctDef]]:
    """
    Convert a FunctSpec to a FunctDef.
    Variables dict is unused but present for dispatcher symmetry.
    """
    return None, [FunctDef(
        name        = funct_spec.name,
        description = funct_spec.description,
    )]


def _expand_statement(statement: Statement,
                      variables: dict[str, int]) -> tuple[FieldDef | None, list]:
    """
    Evaluate #if conditions for a statement, then dispatch to the
    appropriate expander.  Returns (None, []) if any condition
    is false or if an error occurs.
    """
    # evaluate all active #if conditions
    for cond in statement.conditions:
        try:
            result = evaluate(cond, variables)
        except ExpressionError as e:
            ctx.error(f"condition expression error {cond!r}: {e}")
            return None, []
        if not result:
            return None, []

    obj = statement.statement
    if isinstance(obj, PinSpec):
        return _expand_pin(obj, variables)
    elif isinstance(obj, VarDef):
        return _expand_var(obj, variables)
    elif isinstance(obj, FunctSpec):
        return _expand_funct(obj, variables)
    else:
        ctx.error(f"unknown statement type: {type(obj).__name__}")
        return None, []


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
            ctx.error(f"template expression error {expr_str!r}: {e}")
            return None
        result = result.replace(m.group(0), str(int(val)).zfill(width), 1)
    return result


# ---------------------------------------------------------------------------
# Top-level resolver
# ---------------------------------------------------------------------------

def resolve(spec: BlockSpec, variant_name: str, orig_path: str,
            supplied_params: dict[str, int] | None = None) -> BlockDef | None:
    """
    Resolve a BlockSpec against concrete parameter values to produce a BlockDef.

    supplied_params -- dict of param name -> value; parameters not supplied
                       use their default values from spec.params.
                       Pass None or {} to use all defaults.

    Requires an active ErrorContext (push_context() must be called before
    resolve() and pop_context() after). Reports errors into the current context.
    Returns a BlockDef if successful, None if any errors were reported.
    """
    # ensure we have a clean context to work with
    if not ctx.no_errors():
        ctx.error("resolve() called with pre-existing errors in context")
        return None

    if not variant_name.isidentifier():
        ctx.error(f"invalid variant name {variant_name!r}")
        return None

    if supplied_params is None:
        supplied_params = {}

    variables = _build_variables(spec, supplied_params)
    if not ctx.no_errors():
        return None

    ordered_fields = []
    namespace = {}
    pins      = {}
    functions = {}
    type_to_dict = { PinDef: pins, FunctDef: functions }

    for statement in spec.statements:
        field, expanded = _expand_statement(statement, variables)
        if field is not None:
            ordered_fields.append(field)
        for obj in expanded:
            if not isinstance(obj, VarDef):
                if obj.name in namespace:
                    ctx.error(f"duplicate name {obj.name!r} after resolution")
                else:
                    namespace[obj.name] = obj
                    target_dict = type_to_dict.get(type(obj))
                    if target_dict is not None:
                        target_dict[obj.name] = obj
    if not ctx.no_errors():
        return None

    return BlockDef(
        name                 = variant_name,
        abs_path             = spec.abs_path,
        orig_path            = orig_path,
        description          = spec.description,
        params               = variables,
        pins                 = pins,
        functions            = functions,
        namespace            = namespace,
        ordered_fields       = ordered_fields,
    )


# ---------------------------------------------------------------------------
# Test driver
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import os
    from bloc_parser import parse_bloc
    from parse_common import push_context, pop_context

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

    push_context(source=variant_name)
    block_def = resolve(spec, variant_name, path, supplied)
    ctx.summarize()
    ctx = pop_context()
    if block_def is None:
        sys.exit(1)

    print(block_def.describe())
