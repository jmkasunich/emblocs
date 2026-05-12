# expressions.py
# Safe expression evaluator for EMBLOCS tools.
#
# Evaluates C-like expressions using Python's ast module for parsing,
# with a restricted set of operations to prevent side effects and
# arbitrary code execution.
#
# Public API:
#   evaluate(expr, variables=None, mode="int"|"float" ) -> int | float
#
# Raises ExpressionError on any syntax or semantic error.

import ast
import operator

# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------

class ExpressionError(Exception):
    """Raised when an expression cannot be parsed or evaluated."""
    pass

# ---------------------------------------------------------------------------
# Private helper for exception
# ---------------------------------------------------------------------------

def raiseExprError(msg:str):
    """ Raises ExpressionError, prepending msg with the expression """
    raise ExpressionError(f"Error in expression {_expr!r}: {msg}")


# ---------------------------------------------------------------------------
# Operator tables
# ---------------------------------------------------------------------------

INT_BIN_OPS = {
    ast.Add:    operator.add,
    ast.Sub:    operator.sub,
    ast.Mult:   operator.mul,
    ast.Div:    lambda a, b: _int_div(a, b),
    ast.Mod:    operator.mod,
    ast.BitAnd: operator.and_,
    ast.BitOr:  operator.or_,
    ast.BitXor: operator.xor,
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
}

FLOAT_BIN_OPS = {
    ast.Add:  operator.add,
    ast.Sub:  operator.sub,
    ast.Mult: operator.mul,
    ast.Div:  operator.truediv,
    ast.Mod:  operator.mod,
}

INT_UNARY_OPS = {
    ast.UAdd:   operator.pos,
    ast.USub:   operator.neg,
    ast.Invert: operator.invert,
    ast.Not:    lambda x: int(not x),
}

FLOAT_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not:    lambda x: int(not x),
}

CMP_OPS = {
    ast.Eq:    operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt:    operator.lt,
    ast.LtE:   operator.le,
    ast.Gt:    operator.gt,
    ast.GtE:   operator.ge,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _int_div(a: int, b: int) -> int:
    """Integer division truncating toward zero, C-style."""
    if b == 0:
        raiseExprError("division by zero")
    return int(a / b)


def _translate(expr: str) -> str:
    """
    Translate C-style logical operators to Python equivalents.
    Converts '&&' to ' and ', '||' to ' or ',
          and '!' to ' not ' (while protecting '!=').
    """
    expr = expr.replace("!=", "\x00")   # protect "!="
    expr = expr.replace("!",  " not ")
    expr = expr.replace("\x00", "!=")   # restore "!="
    expr = expr.replace("&&", " and ")
    expr = expr.replace("||", " or ")
    return expr


# ---------------------------------------------------------------------------
# Evaluator (private)
# ---------------------------------------------------------------------------

class _Evaluator:
    """
    AST-walking expression evaluator.  Do not instantiate directly;
    use the module-level evaluate() function.
    """

    def __init__(self, variables: dict, mode: str):
        self.variables = variables
        self.mode      = mode
        if mode == 'int' :
            self.bin_ops   = INT_BIN_OPS
            self.unary_ops = INT_UNARY_OPS
        elif mode == 'float':
            self.bin_ops   = FLOAT_BIN_OPS
            self.unary_ops = FLOAT_UNARY_OPS
        else :
            raise ExpressionError(f"Invalid expression mode: {mode!r}; expected 'int' or 'float'")

    def visit(self, node):
        method = getattr(self, f"_visit_{type(node).__name__}", None)
        if method is None:
            raiseExprError(f"unsupported construct: {type(node).__name__}")
        return method(node)

    def _visit_Expression(self, node):
        return self.visit(node.body)

    def _visit_Constant(self, node):
        if self.mode == 'int' and isinstance(node.value, int):
            return node.value
        if self.mode == 'float' and isinstance(node.value, (int, float)):
            return float(node.value)
        raiseExprError(
            f"constant {node.value!r} not valid for {self.mode}")

    def _visit_Name(self, node):
        if node.id not in self.variables:
            raiseExprError(f"unknown variable: {node.id!r}")
        val = self.variables[node.id]
        if self.mode == 'int' and not isinstance(val, int):
            raiseExprError(f"variable {node.id!r} must be integer")
        elif self.mode == 'float' and not isinstance(val, (int, float)):
            raiseExprError(f"variable {node.id!r} must be number")
        return val

    def _visit_BinOp(self, node):
        op_type = type(node.op)
        if op_type not in self.bin_ops:
            raiseExprError(
                f"operator {op_type.__name__!r} not supported for {self.mode}")
        left  = self.visit(node.left)
        right = self.visit(node.right)
        try:
            return self.bin_ops[op_type](left, right)
        except ValueError as e:
            raiseExprError(
                f"operator {op_type.__name__!r}: {e}"
            )

    def _visit_UnaryOp(self, node):
        op_type = type(node.op)
        if op_type not in self.unary_ops:
            raiseExprError(
                f"unary {op_type.__name__!r} not supported for {self.mode}")
        try:
            return self.unary_ops[op_type](self.visit(node.operand))
        except ValueError as e:
            raiseExprError(
                f"operator {op_type.__name__!r}: {e}"
            )

    def _visit_BoolOp(self, node):
        if isinstance(node.op, ast.And):
            for v in node.values:
                if not self.visit(v):
                    return 0
            return 1
        if isinstance(node.op, ast.Or):
            for v in node.values:
                if self.visit(v):
                    return 1
            return 0
        # FIXME - I believe this cannot be reached, it currently has no test case
        raiseExprError(f"unsupported boolean operator {type(node.op).__name__!r}")

    def _visit_Compare(self, node):
        if len(node.ops) > 1:
            raiseExprError(
                "chained compare not supported; "
                "use '&&' to combine multiple comparisons")
        op_type = type(node.ops[0])
        if op_type not in CMP_OPS:
            raiseExprError(
                f"unsupported comparison operator: {op_type.__name__!r}")
        left  = self.visit(node.left)
        right = self.visit(node.comparators[0])
        try:
            return int(CMP_OPS[op_type](left, right))
        except ValueError as e:
            raiseExprError(
                f"operator {op_type.__name__!r}: {e}"
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(expr: str, variables: dict = None, mode: str = 'int') -> int | float:
    """
    Evaluate a C-like expression and return the result.

    Parameters:
        expr      -- expression string; no internal whitespace required
                     but whitespace is tolerated
        variables -- dict mapping name strings to int (or float in FLOAT mode)
                     values; None is treated as an empty dict
        mode      -- 'int' (default) or 'float'

    Returns an int in INT mode, a float in FLOAT mode.
    Raises ExpressionError on any syntax or semantic problem.
    """
    # save expression in module-level var for error messages
    global _expr
    _expr = expr
    if variables is None:
        variables = {}
    try:
        translated = _translate(expr)
        tree       = ast.parse(translated.strip(), mode='eval')
    except SyntaxError as e:
        raise ExpressionError(f"Error in expression {_expr!r}: {e.msg}") from e

    return _Evaluator(variables, mode).visit(tree)


# ---------------------------------------------------------------------------
# Test driver
# ---------------------------------------------------------------------------




if __name__ == "__main__":
    import sys

    args = sys.argv[1:]

    if not args:
        print("Usage: python expressions.py <expr> [-f] [name=value ...]")
        sys.exit(1)

    expr = args[0]
    mode = "int"
    variables = {}

    for arg in args[1:]:
        if arg == "-f":
            mode = "float"
        elif "=" in arg:
            name, value = arg.split("=", 1)
            try:
                variables[name] = float(value) if mode == "float" else int(value)
            except ValueError:
                print(f"Invalid value for variable '{name}': {value}")
                sys.exit(1)
        else:
            print(f"Unrecognized argument: {arg}")
            sys.exit(1)

    try:
        result = evaluate(expr, variables, mode)
        print(result)
    except ExpressionError as e:
        print(f"Error: {e}")
        sys.exit(2)
