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
        raise ExpressionError("division by zero")
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
            raise ExpressionError(f"invalid mode: {mode!r}; expected 'int' or 'float'")

    def visit(self, node):
        method = getattr(self, f"_visit_{type(node).__name__}", None)
        if method is None:
            raise ExpressionError(
                f"unsupported expression construct: {type(node).__name__}")
        return method(node)

    def _visit_Expression(self, node):
        return self.visit(node.body)

    def _visit_Constant(self, node):
        if self.mode == 'int' and isinstance(node.value, int):
            return node.value
        if self.mode == 'float' and isinstance(node.value, (int, float)):
            return float(node.value)
        raise ExpressionError(
            f"constant {node.value!r} is not valid in {self.mode} expression")

    def _visit_Name(self, node):
        if node.id not in self.variables:
            raise ExpressionError(f"unknown variable: {node.id!r}")
        val = self.variables[node.id]
        if self.mode == 'int' and not isinstance(val, int):
            raise ExpressionError(
                f"variable {node.id!r} must be an integer")
        elif self.mode == 'float' and not isinstance(val, (int, float)):
            raise ExpressionError(
                f"variable {node.id!r} must be a number")
        return val

    def _visit_BinOp(self, node):
        op_type = type(node.op)
        if op_type not in self.bin_ops:
            raise ExpressionError(
                f"operator {op_type.__name__!r} is not supported in {self.mode} expression")
        left  = self.visit(node.left)
        right = self.visit(node.right)
        return self.bin_ops[op_type](left, right)

    def _visit_UnaryOp(self, node):
        op_type = type(node.op)
        if op_type not in self.unary_ops:
            raise ExpressionError(
                f"unary {op_type.__name__!r} is not supported in {self.mode} expression")
        return self.unary_ops[op_type](self.visit(node.operand))

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
        raise ExpressionError("unsupported boolean operator")

    def _visit_Compare(self, node):
        if len(node.ops) > 1:
            raise ExpressionError(
                "chained comparisons are not supported; "
                "use '&&' to combine multiple comparisons")
        op_type = type(node.ops[0])
        if op_type not in CMP_OPS:
            raise ExpressionError(
                f"unsupported comparison operator: {op_type.__name__!r}")
        left  = self.visit(node.left)
        right = self.visit(node.comparators[0])
        return int(CMP_OPS[op_type](left, right))


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
    if variables is None:
        variables = {}
    try:
        translated = _translate(expr)
        tree       = ast.parse(translated.strip(), mode='eval')
    except SyntaxError as e:
        raise ExpressionError(f"syntax error in expression {expr!r}: {e}") from e

    return _Evaluator(variables, mode).visit(tree)


# ---------------------------------------------------------------------------
# Test driver
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1:
        # No arguments: run a single expression interactively
        print("usage:")
        print(f"  {sys.argv[0]} <expr> [-v NAME=value] [-f]")
        print(f"  {sys.argv[0]} <testfile>")
        sys.exit(0)

    # If argument looks like a file, run test file mode
    import os
    if os.path.isfile(sys.argv[1]):
        # ---------------------------------------------------------------
        # Test file mode
        # ---------------------------------------------------------------
        test_path  = sys.argv[1]
        variables  = {}
        pass_count = 0
        fail_count = 0
        error_count = 0

        with open(test_path, "r") as f:
            for lineno, raw_line in enumerate(f, start=1):
                line = raw_line.strip()

                # blank lines and comments
                if not line or line.startswith("#"):
                    continue

                # 'clear' command
                if line == "clear":
                    variables = {}
                    continue

                # 'var NAME=value' command
                if line.startswith("var "):
                    rest = line[4:].strip()
                    if "=" not in rest:
                        print(f"{test_path}:{lineno}: error: "
                              f"invalid var syntax: {rest!r}")
                        error_count += 1
                        continue
                    name, _, value = rest.partition("=")
                    name  = name.strip()
                    value = value.strip()
                    # try int first (handles 0x prefix), then float
                    try:
                        variables[name] = int(value, 0)
                    except ValueError:
                        try:
                            variables[name] = float(value)
                        except ValueError:
                            print(f"{test_path}:{lineno}: error: "
                                  f"invalid value {value!r} for variable {name!r}")
                            error_count += 1
                    continue

                # test case: expression  mode  expected
                parts = line.split()
                if len(parts) < 3:
                    print(f"{test_path}:{lineno}: error: "
                          f"expected 'expression mode result', got: {line!r}")
                    error_count += 1
                    continue

                expr_str  = parts[0]
                mode_str  = parts[1]
                expected_str = parts[2]

                if mode_str not in ("int", "float"):
                    print(f"{test_path}:{lineno}: error: "
                          f"invalid mode {mode_str!r}; expected 'int' or 'float'")
                    error_count += 1
                    continue

                # parse expected result
                try:
                    expected = (int(expected_str, 0) if mode_str == "int"
                                else float(expected_str))
                except ValueError:
                    print(f"{test_path}:{lineno}: error: "
                          f"invalid expected value {expected_str!r}")
                    error_count += 1
                    continue

                # evaluate and compare
                try:
                    result = evaluate(expr_str, variables, mode_str)
                    if result == expected:
                        pass_count += 1
                    else:
                        print(f"{test_path}:{lineno}: FAIL: "
                              f"{expr_str!r} = {result!r}, expected {expected!r}")
                        fail_count += 1
                except ExpressionError as e:
                    print(f"{test_path}:{lineno}: FAIL: "
                          f"{expr_str!r} raised ExpressionError: {e}")
                    fail_count += 1

        total = pass_count + fail_count
        print(f"\n{test_path}: {total} tests: "
              f"{pass_count} passed, {fail_count} failed, "
              f"{error_count} file error(s)")
        sys.exit(0 if fail_count == 0 and error_count == 0 else 1)

    else:
        # ---------------------------------------------------------------
        # Single expression mode (original CLI)
        # ---------------------------------------------------------------
        import argparse

        arg_parser = argparse.ArgumentParser(
            description="Evaluate a C-like expression (integer or float)."
        )
        arg_parser.add_argument("expr",
                                help="expression to evaluate")
        arg_parser.add_argument("-v", "--var", action="append",
                                help="variable definition, format: NAME=value")
        arg_parser.add_argument("-f", "--float", action="store_true",
                                help="use float mode instead of integer mode")

        args = arg_parser.parse_args()

        variables = {}
        if args.var:
            for pair in args.var:
                try:
                    name, value = pair.split("=", 1)
                    variables[name] = float(value) if args.float else int(value, 0)
                except ValueError:
                    print(f"error: invalid variable definition: {pair!r}",
                          file=sys.stderr)
                    sys.exit(1)

        mode = 'float' if args.float else 'int'

        try:
            result = evaluate(args.expr, variables, mode)
            print(result)
        except ExpressionError as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(1)
