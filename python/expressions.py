# expression evaluator, using a class

import ast
import operator
import sys

# -----------------------------
# Translation layer
# -----------------------------

def translate_expr(expr: str) -> str:
    expr = expr.replace("!=", "_<>_")    # protect "!="
    expr = expr.replace("!", " not ")    # convert "!" to python equivalent
    expr = expr.replace("_<>_", "!=")    # restore "!="
    expr = expr.replace("&&", " and ")   # convert "&&" to python equivalent
    expr = expr.replace("||", " or ")    # convert "||" to python equivalent
    return expr

# -----------------------------
# Integer-only operations
# -----------------------------

def int_div(a, b):
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return int(a / b)

BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: int_div,
    ast.Mod: operator.mod,
    ast.BitAnd: operator.and_,
    ast.BitOr: operator.or_,
    ast.BitXor: operator.xor,
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
}

UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Invert: operator.invert,
}

CMP_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

class SafeEvaluator(ast.NodeVisitor):
    def __init__(self, variables=None):
        self.variables = variables or {}

    def visit_Expression(self, node):
        return self.visit(node.body)

    def visit_Constant(self, node):
        if isinstance(node.value, int):
            return node.value
        raise ValueError("Only integer constants allowed")

    def visit_Name(self, node):
        if node.id not in self.variables:
            raise ValueError(f"Unknown variable: {node.id}")
        val = self.variables[node.id]
        if not isinstance(val, int):
            raise ValueError(f"Variable {node.id} must be integer")
        return val

    def visit_BinOp(self, node):
        if isinstance(node.op, ast.FloorDiv):
            raise ValueError("'//' is not supported")
        op_type = type(node.op)
        if op_type not in BIN_OPS:
            raise ValueError(f"Unsupported operator: {op_type}")
        return BIN_OPS[op_type](self.visit(node.left), self.visit(node.right))

    def visit_UnaryOp(self, node):
        if isinstance(node.op, ast.Not):
            return int(not self.visit(node.operand))
        op_type = type(node.op)
        if op_type not in UNARY_OPS:
            raise ValueError(f"Unsupported unary operator: {op_type}")
        return UNARY_OPS[op_type](self.visit(node.operand))

    def visit_BoolOp(self, node):
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
        raise ValueError("Unsupported boolean operator")

    def visit_Compare(self, node):
        left = self.visit(node.left)
        for op, comp in zip(node.ops, node.comparators):
            right = self.visit(comp)
            op_type = type(op)
            if op_type not in CMP_OPS:
                raise ValueError(f"Unsupported comparison: {op_type}")
            if not CMP_OPS[op_type](left, right):
                return 0
            left = right
        return 1

    def generic_visit(self, node):
        raise ValueError(f"Unsupported expression: {type(node).__name__}")


def evaluate(expr: str, variables=None):
    expr = translate_expr(expr)
    tree = ast.parse(expr, mode='eval')
    return SafeEvaluator(variables).visit(tree)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("expr")
    parser.add_argument("-v", "--var", action="append")

    args = parser.parse_args()

    vars_dict = {}
    if args.var:
        for pair in args.var:
            name, value = pair.split('=')
            vars_dict[name] = int(value)

    try:
        print(evaluate(args.expr, vars_dict))
    except Exception as e:
        print(f"Error: {e}")


###########################################################
# expression evaluator without class

import ast
import operator

# -----------------------------
# Translation layer
# -----------------------------

def translate_expr(expr: str) -> str:
    expr = expr.replace("!=", "_<>_")    # protect "!="
    expr = expr.replace("!", " not ")    # convert "!" to python equivalent
    expr = expr.replace("_<>_", "!=")    # restore "!="
    expr = expr.replace("&&", " and ")   # convert "&&" to python equivalent
    expr = expr.replace("||", " or ")    # convert "||" to python equivalent
    return expr

# -----------------------------
# Integer-only operations
# -----------------------------

def int_div(a, b):
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return int(a / b)  # truncate toward zero (C-like)

BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: int_div,
    ast.Mod: operator.mod,
    ast.BitAnd: operator.and_,
    ast.BitOr: operator.or_,
    ast.BitXor: operator.xor,
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
}

UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Invert: operator.invert,
}

CMP_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

# -----------------------------
# Evaluator (functional)
# -----------------------------

def eval_node(node, variables):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, int):
            return node.value
        raise ValueError("Only integer constants allowed")

    elif isinstance(node, ast.Name):
        if node.id not in variables:
            raise ValueError(f"Unknown variable: {node.id}")
        val = variables[node.id]
        if not isinstance(val, int):
            raise ValueError(f"Variable {node.id} must be integer")
        return val

    elif isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.FloorDiv):
            raise ValueError("'//' is not supported")

        op_type = type(node.op)
        if op_type not in BIN_OPS:
            raise ValueError(f"Unsupported operator: {op_type}")

        left = eval_node(node.left, variables)
        right = eval_node(node.right, variables)
        return BIN_OPS[op_type](left, right)

    elif isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return 1 if not eval_node(node.operand, variables) else 0

        op_type = type(node.op)
        if op_type not in UNARY_OPS:
            raise ValueError(f"Unsupported unary operator: {op_type}")

        return UNARY_OPS[op_type](eval_node(node.operand, variables))

    elif isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            for v in node.values:
                if not eval_node(v, variables):
                    return 0
            return 1

        elif isinstance(node.op, ast.Or):
            for v in node.values:
                if eval_node(v, variables):
                    return 1
            return 0

        raise ValueError("Unsupported boolean operator")

    elif isinstance(node, ast.Compare):
        left = eval_node(node.left, variables)

        for op, comp in zip(node.ops, node.comparators):
            right = eval_node(comp, variables)

            op_type = type(op)
            if op_type not in CMP_OPS:
                raise ValueError(f"Unsupported comparison: {op_type}")

            if not CMP_OPS[op_type](left, right):
                return 0

            left = right

        return 1

    else:
        raise ValueError(f"Unsupported expression: {type(node).__name__}")

# -----------------------------
# Public API
# -----------------------------

def evaluate(expr: str, variables=None):
    variables = variables or {}
    expr = translate_expr(expr)
    tree = ast.parse(expr, mode='eval')
    return eval_node(tree.body, variables)

# -----------------------------
# CLI test harness
# -----------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Evaluate C-like expressions safely (integer-only)."
    )
    parser.add_argument("expr", help="Expression to evaluate")
    parser.add_argument(
        "-v", "--var",
        action="append",
        help="Variables (format: name=value)"
    )

    args = parser.parse_args()

    vars_dict = {}
    if args.var:
        for pair in args.var:
            name, value = pair.split("=")
            vars_dict[name] = int(value)

    try:
        result = evaluate(args.expr, vars_dict)
        print(result)
    except Exception as e:
        print(f"Error: {e}")
