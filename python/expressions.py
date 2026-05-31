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

from __future__ import annotations
import ast
import operator
import re

# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------

class ExpressionError(Exception):
    def __init__(self, message : str, expression : str):
        super().__init__(message)
        self.expression = expression
        self.message = message

    def __str__(self):
        base = "expression"
        if self.expression is not None:
            base += f" '{self.expression}'"
        if self.message:
            base += f": {self.message}"
        if self.__cause__:
            base += f": {getattr(self.__cause__, 'msg', str(self.__cause__))}"
        return base

# ---------------------------------------------------------------------------
# Operator tables
# ---------------------------------------------------------------------------

INT_BIN_OPS = {
    ast.Add:    operator.add,
    ast.Sub:    operator.sub,
    ast.Mult:   operator.mul,
    ast.Div:    lambda a, b: _int_div(a, b),
    ast.Mod:    lambda a, b: _int_mod(a, b),
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
        raise ZeroDivisionError("division by zero")
    return int(a / b)

def _int_mod(a: int, b: int) -> int:
    """Integer modulo truncating toward zero, C-style."""
    if b == 0:
        raise ZeroDivisionError("integer modulo by zero")
    return (a - (_int_div(a, b) * b))

_NOT_RE = re.compile(r'!(?!=)')

def _translate(expr: str) -> str:
    """
    Translate C-style logical operators to Python equivalents.
    Converts '&&' to ' and ', '||' to ' or ',
          and '!' to ' not ' (but not '!=').
    """
    expr = _NOT_RE.sub(' not ', expr)
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
    def __init__(self, expr: str, variables: dict, mode: str):
        self.expr_str = expr
        self.variables = variables
        self.mode      = mode
        if mode == 'int' :
            self.bin_ops   = INT_BIN_OPS
            self.unary_ops = INT_UNARY_OPS
        elif mode == 'float':
            self.bin_ops   = FLOAT_BIN_OPS
            self.unary_ops = FLOAT_UNARY_OPS
        else :
            assert False, f"unexpected mode: {mode!r}"

    def error(self, message=None, *, cause=None):
        if cause is not None:
            raise ExpressionError(message, self.expr_str) from cause
        else:
            raise ExpressionError(message, self.expr_str)

    def evaluate(self):
        translated = _translate(self.expr_str)
        try:
            tree = ast.parse(translated.strip(), mode='eval')
        except (SyntaxError, ValueError, TypeError) as e:
            self.error(cause=e)
        return self.visit(tree)

    def visit(self, node):
        method = getattr(self, f"_visit_{type(node).__name__}", None)
        if method is None:
            self.error(f"unsupported construct: {type(node).__name__}")
        return method(node)

    def _visit_Expression(self, node):
        return self.visit(node.body)

    def _visit_Constant(self, node):
        if self.mode == 'int' and isinstance(node.value, int):
            return node.value
        if self.mode == 'float' and isinstance(node.value, (int, float)):
            return float(node.value)
        self.error(f"constant {node.value!r} not valid for {self.mode}")

    def _visit_Name(self, node):
        if node.id not in self.variables:
            self.error(f"unknown variable: {node.id!r}")
        val = self.variables[node.id]
        if self.mode == 'int' and not isinstance(val, int):
            self.error(f"variable {node.id!r} must be integer")
        elif self.mode == 'float' and not isinstance(val, (int, float)):
            self.error(f"variable {node.id!r} must be number")
        return val

    def _visit_BinOp(self, node):
        op_type = type(node.op)
        if op_type not in self.bin_ops:
            self.error(f"operator {op_type.__name__!r} not supported for {self.mode}")
        left  = self.visit(node.left)
        right = self.visit(node.right)
        try:
            return self.bin_ops[op_type](left, right)
        except (ArithmeticError, ValueError, TypeError) as e:
            self.error(f"operator {op_type.__name__!r}", cause=e)

    def _visit_UnaryOp(self, node):
        op_type = type(node.op)
        if op_type not in self.unary_ops:
            self.error(f"unary {op_type.__name__!r} not supported for {self.mode}")
        try:
            return self.unary_ops[op_type](self.visit(node.operand))
        except (ArithmeticError, ValueError, TypeError) as e:
            self.error(f"operator {op_type.__name__!r}", cause=e)

    def _visit_BoolOp(self, node):
        if isinstance(node.op, ast.And):
            for v in node.values:
                if not self.visit(v):
                    return 0
            return 1
        elif isinstance(node.op, ast.Or):
            for v in node.values:
                if self.visit(v):
                    return 1
            return 0
        else:
            assert False, f"unexpected BoolOp: {type(node.op).__name__}"

    def _visit_Compare(self, node):
        if len(node.ops) > 1:
            self.error("chained compare not supported; "
                "use '&&' to combine multiple comparisons")
        op_type = type(node.ops[0])
        if op_type not in CMP_OPS:
            self.error(f"unsupported comparison operator: {op_type.__name__!r}")
        left  = self.visit(node.left)
        right = self.visit(node.comparators[0])
        try:
            return int(CMP_OPS[op_type](left, right))
        except (ArithmeticError, ValueError, TypeError) as e:
            self.error(f"operator {op_type.__name__!r}", cause=e)


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
    if mode not in ('int', 'float'):
        raise ValueError(f"invalid mode {mode!r}; expected 'int' or 'float'")
    if variables is None:
        variables = {}
    evaluator = _Evaluator(expr, variables, mode)
    return evaluator.evaluate()


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
