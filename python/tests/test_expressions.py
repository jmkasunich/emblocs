import pytest
from expressions import evaluate, ExpressionError


@pytest.mark.parametrize("expr, mode, expected", [
    # --- Integer constants ---
    ("1", "int", 1),
    ("0", "int", 0),
    ("42", "int", 42),
    ("0xFF", "int", 255),
    ("0x0F", "int", 15),
    ("-5", "int", -5),
    ("+5", "int", 5),
    ("0xFFFFFFFF", "int", 4294967295),
    ("4294967296", "int", 4294967296),
    # --- Integer arithmetic ---
    ("1+2", "int", 3),
    ("10-3", "int", 7),
    ("3*4", "int", 12),
    ("10/3", "int", 3),
    ("10%3", "int", 1),
    # modulo edge cases
    ("1%1", "int", 0),
    ("0%1", "int", 0),
    # division edge
    ("-3/2", "int", -1),  # confirm truncation toward zero
    ("3/2", "int", 1),

    # --- Integer bitwise operations ---
    ("0xFF&0x0F", "int", 15),
    ("0xFF|0x00", "int", 255),
    ("0xFF^0x0F", "int", 240),
    ("~0", "int", -1),
    ("1<<4", "int", 16),
    ("256>>4", "int", 16),
    # --- Integer comparisons ---
    ("1==1", "int", 1),
    ("1==2", "int", 0),
    ("1!=2", "int", 1),
    ("1!=1", "int", 0),
    ("2>1", "int", 1),
    ("1>2", "int", 0),
    ("1<2", "int", 1),
    ("2<1", "int", 0),
    ("2>=2", "int", 1),
    ("2>=3", "int", 0),
    ("2<=2", "int", 1),
    ("3<=2", "int", 0),
    # --- Integer logical operators ---
    ("1&&1", "int", 1),
    ("1&&0", "int", 0),
    ("0&&1", "int", 0),
    ("0&&0", "int", 0),
    ("1||0", "int", 1),
    ("0||1", "int", 1),
    ("0||0", "int", 0),
    ("!0", "int", 1),
    ("!1", "int", 0),
    ("!42", "int", 0),
    # --- Float constants ---
    ("1.0", "float", 1.0),
    ("0.5", "float", 0.5),
    ("3.5", "float", 3.5),
    ("-1.5", "float", -1.5),
    ("+2.5", "float", 2.5),
    # --- Float arithmetic ---
    ("1.0", "float", 1.0),
    ("0.5", "float", 0.5),
    ("3.5", "float", 3.5),
    ("1.5+2.0", "float", 3.5),
    ("3.5-1.0", "float", 2.5),
    ("2.0*1.5", "float", 3.0),
    ("7.0/2.0", "float", 3.5),
    # --- Float comparisons ---
    ("1.5==1.5", "float", 1),
    ("1.5==2.5", "float", 0),
    ("1.5<2.5", "float", 1),
    ("2.5>1.5", "float", 1),
    ("1.5!=2.5", "float", 1),
    # --- Mixed int/float constants (float mode) ---
    ("1+1.5", "float", 2.5),
    ("2*1.5", "float", 3.0),
    # --- order of operations ---
    ("(3-1)*(4+2)", "int", 12),
    ("3-(1*4)+2", "int", 1),
    ("((3-1)*4)+2", "int", 10),
    ("(3<<2)|(0x00030000>>8)", "int", 0x30C),
    # --- whitespace variations ---
    ("1+2", "int", 3),
    (" 1+2", "int", 3),
    ("1 +2", "int", 3),
    ("1+ 2", "int", 3),
    (" 1 + 2 ", "int", 3),
])
def test_constant_expressions(expr, mode, expected):
    assert evaluate(expr, mode=mode) == expected


@pytest.mark.parametrize("expr, expected", [
    # --- basic logical translation ---
    ("1&&1", 1),
    ("1||0", 1),
    ("!0", 1),

    # --- NOT vs != (critical edge case) ---
    ("1!=2", 1),
    ("1!=1", 0),

    # make sure '!' does NOT corrupt '!='
    ("!(1!=2)", 0),
    ("!(1!=1)", 1),
    ("!1!=0", 0),

    # --- combinations ---
    ("(0&&0)||1", 1),   # order of operations
    ("0&&(0||1)", 0),
    ("0&&0||1", 1),
    ("!(1&&0)", 1),

    # --- multiple operators ---
    ("1&&1&&1", 1),
    ("0||0||1", 1),
    ("!!!1", 0),  # nested NOT

    # --- edge formatting ---
    ("!1||1", 1),    # order of operations
    ("!(1||1)", 0),
    ("(!1)||1", 1),

    # --- spacing should not matter (defensive) ---
    ("1&&1", 1),
])
def test_logical_translation(expr, expected):
    result = evaluate(expr, mode="int")
    assert result == expected


@pytest.mark.parametrize("expr, variables, mode, expected", [
    # --- simple variables ---
    ("A", {"A": 10, "B": 3}, "int", 10),
    ("B", {"A": 10, "B": 3}, "int", 3),

    # --- simple variables ---
    ("A+B", {"A": 10, "B": 3}, "int", 13),
    ("A-B", {"A": 10, "B": 3}, "int", 7),
    ("A*B", {"A": 10, "B": 3}, "int", 30),
    ("A/B", {"A": 10, "B": 3}, "int", 3),
    ("A%B", {"A": 10, "B": 3}, "int", 1),

    # --- comparisons with variables ---
    ("A>B", {"A": 10, "B": 3}, "int", 1),
    ("A==B", {"A": 10, "B": 3}, "int", 0),
    ("A!=B", {"A": 10, "B": 3}, "int", 1),

    # --- logical expressions ---
    ("A&&B", {"A": 10, "B": 0}, "int", 0),
    ("A||B", {"A": 0, "B": 5}, "int", 1),
    ("!A", {"A": 0}, "int", 1),

    # --- bitmask-style use ---
    ("(INPUTS>>0)&1", {"INPUTS": 0xFF}, "int", 1),
    ("(INPUTS>>7)&1", {"INPUTS": 0xFF}, "int", 1),
    ("(INPUTS>>8)&1", {"INPUTS": 0xFF}, "int", 0),
    ("(INPUTS>>3)&1", {"INPUTS": 0x0F}, "int", 1),
    ("(INPUTS>>4)&1", {"INPUTS": 0xFFFFFFEF}, "int", 0),
    ("(INPUTS>>30)&1", {"INPUTS": 0x40000000}, "int", 1),
    ("(INPUTS<<16)&0x10000", {"INPUTS": 1}, "int", 0x10000),

    # --- float interactions ---
    ("A+0.5", {"A": 2}, "float", 2.5),
    ("B*1.5", {"B": 3}, "float", 4.5),
])
def test_with_variables(expr, variables, mode, expected):
    result = evaluate(expr, variables, mode)
    assert result == expected


@pytest.mark.parametrize("expr, variables, mode, expected", [
    ("HAS_ENABLE", {"HAS_ENABLE": 0, "HAS_HOLD": 1}, "int", 0),
    ("HAS_HOLD",   {"HAS_ENABLE": 0, "HAS_HOLD": 1}, "int", 1),
    ("HAS_ENABLE&&HAS_HOLD", {"HAS_ENABLE": 0, "HAS_HOLD": 1}, "int", 0),
    ("HAS_ENABLE||HAS_HOLD", {"HAS_ENABLE": 0, "HAS_HOLD": 1}, "int", 1),
    ("!HAS_ENABLE", {"HAS_ENABLE": 0}, "int", 1),
    ("!HAS_HOLD",   {"HAS_HOLD": 1}, "int", 0),
])
def test_boolean_variables(expr, variables, mode, expected):
    assert evaluate(expr, variables, mode) == expected


# test patterns that should cause errors
@pytest.mark.parametrize("expr, variables, mode, expected_message", [
    # --- empty expression ---
    ("", {}, "int", "Error in expression '': invalid syntax"),
    # --- whitespace only expression ---
    ("  ", {}, "float", "Error in expression '  ': invalid syntax"),
    # --- whitespace only expression ---
    (":", {}, "int", "Error in expression ':': invalid syntax"),
    # --- whitespace only expression ---
    ("_", {}, "int", "Error in expression '_': unknown variable: '_'"),
    # --- whitespace only expression ---
    ("None", {}, "float", "Error in expression 'None': constant None not valid for float"),
    # --- invalid expression type ---
    ("1", {}, "bool", "Invalid expression mode: 'bool'; expected 'int' or 'float'"),
    # --- syntax error ---
    ("1+", {}, "int", "Error in expression '1+': invalid syntax"),
    # --- float constant in int mode ---
    ("1.5", {}, "int", "Error in expression '1.5': constant 1.5 not valid for int"),
    # --- hex constant in float mode ---
    ("...", {}, "float", "Error in expression '...': constant Ellipsis not valid for float"),
    # --- unknown variable ---
    ("foo", {"bar":1}, "int", "Error in expression 'foo': unknown variable: 'foo'"),
    # --- mistyped variable ---
    ("foo", {"foo":1.5}, "int", "Error in expression 'foo': variable 'foo' must be integer"),
    # --- mistyped variable ---
    ("foo", {"foo":...}, "float", "Error in expression 'foo': variable 'foo' must be number"),
    # --- unsupported operator ---
    ("1//2", {}, "int", "Error in expression '1//2': operator 'FloorDiv' not supported for int"),
    # --- bitwise and not allowed in float mode ---
    ("1&2", {}, "float", "Error in expression '1&2': operator 'BitAnd' not supported for float"),
    # --- bitwise invert not allowed in float mode ---
    ("~1.2", {}, "float", "Error in expression '~1.2': unary 'Invert' not supported for float"),
    # --- division by zero ---
    ("1/0", {}, "int", "Error in expression '1/0': division by zero"),
    # --- chained comparison ---
    ("1<2<3", {}, "int", "Error in expression '1<2<3': chained compare not supported; use '&&' to combine multiple comparisons"),
    # --- unsupported comparison operator ---
    ("1 is 3", {}, "int", "Error in expression '1 is 3': unsupported comparison operator: 'Is'"),
    # --- unsupported constructs ---
    ("len(x)", {}, "int", "Error in expression 'len(x)': unsupported construct: Call"),
    ("[1,2,3]", {}, "int", "Error in expression '[1,2,3]': unsupported construct: List"),

    # --- negative shift ---
    ("1<<-1", {}, "int", "Error in expression '1<<-1': operator 'LShift': negative shift count"),
])
def test_error_cases(expr, variables, mode, expected_message):
    import pytest

    with pytest.raises(ExpressionError) as e:
        evaluate(expr, variables, mode)

    # strict check
    actual = str(e.value)
    assert actual == expected_message, (
        f"\n\nINPUT: expr: {expr!r}, vars: {variables!r}, mode: {mode!r}\n"
        f"EXPECTED:{expected_message}\n"
        f"ACTUAL:{actual}\n"
    )
