"""Formula engine unit tests — tokenizer, parser, evaluator."""
from decimal import Decimal
from app.formulas.tokenizer import tokenize, TokenType
from app.formulas.parser import parse
from app.formulas.evaluator import evaluate, FormulaError
from app.formulas.engine import FormulaEngine
import pytest


# === Tokenizer ===

def test_tokenize_number():
    tokens = tokenize("42.5")
    assert len(tokens) == 1
    assert tokens[0].type == TokenType.NUMBER
    assert tokens[0].value == "42.5"


def test_tokenize_variable():
    tokens = tokenize("total_collections")
    assert tokens[0].type == TokenType.VARIABLE


def test_tokenize_function():
    tokens = tokenize("MIN(a, b)")
    assert tokens[0].type == TokenType.FUNCTION
    assert tokens[0].value == "MIN"


def test_tokenize_operators():
    tokens = tokenize("a + b * c - d / e")
    ops = [t.value for t in tokens if t.type == TokenType.OPERATOR]
    assert ops == ["+", "*", "-", "/"]


def test_tokenize_comparison():
    tokens = tokenize("a >= b")
    assert any(t.type == TokenType.COMPARISON for t in tokens)


def test_tokenize_invalid_char():
    with pytest.raises(ValueError):
        tokenize("a @ b")


# === Parser + Evaluator ===

def test_simple_arithmetic():
    ctx = {}
    engine = FormulaEngine()
    assert engine.execute("2 + 3", ctx) == Decimal("5")


def test_multiplication_precedence():
    engine = FormulaEngine()
    assert engine.execute("2 + 3 * 4", {}) == Decimal("14")


def test_parentheses():
    engine = FormulaEngine()
    assert engine.execute("(2 + 3) * 4", {}) == Decimal("20")


def test_variable_resolution():
    ctx = {"total": Decimal("100"), "rate": Decimal("0.05")}
    engine = FormulaEngine()
    assert engine.execute("total * rate", ctx) == Decimal("5.00")


def test_min():
    engine = FormulaEngine()
    ctx = {"a": Decimal("10"), "b": Decimal("20")}
    assert engine.execute("MIN(a, b)", ctx) == Decimal("10")


def test_max():
    engine = FormulaEngine()
    ctx = {"a": Decimal("10"), "b": Decimal("20")}
    assert engine.execute("MAX(a, b)", ctx) == Decimal("20")


def test_abs():
    engine = FormulaEngine()
    assert engine.execute("ABS(-5)", {}) == Decimal("5")


def test_if_true():
    engine = FormulaEngine()
    ctx = {"x": Decimal("1")}
    assert engine.execute("IF(x > 0, 100, 200)", ctx) == Decimal("100")


def test_if_false():
    engine = FormulaEngine()
    ctx = {"x": Decimal("-1")}
    assert engine.execute("IF(x > 0, 100, 200)", ctx) == Decimal("200")


def test_round():
    engine = FormulaEngine()
    assert engine.execute("ROUND(3.456, 2)", {}) == Decimal("3.46")


def test_ceiling():
    engine = FormulaEngine()
    assert engine.execute("CEILING(3.2)", {}) == Decimal("4")


def test_floor():
    engine = FormulaEngine()
    assert engine.execute("FLOOR(3.8)", {}) == Decimal("3")


def test_sum():
    engine = FormulaEngine()
    ctx = {"a": Decimal("1"), "b": Decimal("2"), "c": Decimal("3")}
    assert engine.execute("SUM(a, b, c)", ctx) == Decimal("6")


def test_division_by_zero():
    engine = FormulaEngine()
    with pytest.raises(FormulaError):
        engine.execute("10 / 0", {})


def test_unknown_variable():
    engine = FormulaEngine()
    with pytest.raises(FormulaError):
        engine.execute("unknown_var + 1", {})


def test_decimal_precision():
    engine = FormulaEngine()
    ctx = {"bal": Decimal("4521338.42"), "rate": Decimal("0.0025")}
    result = engine.execute("bal * rate", ctx)
    assert result == Decimal("4521338.42") * Decimal("0.0025")


def test_waterfall_pattern():
    """Full waterfall: total - fee = available, MIN(available, due) = payment."""
    engine = FormulaEngine()
    ctx = {
        "total_collections": Decimal("4521338.42"),
        "svc_fee_rate": Decimal("0.0025"),
    }
    fee = engine.execute("total_collections * svc_fee_rate", ctx)
    ctx["servicing_fee"] = fee
    available = engine.execute("total_collections - servicing_fee", ctx)
    ctx["available_funds"] = available
    ctx["a_interest_due"] = Decimal("645823.03")
    payment = engine.execute("MIN(available_funds, a_interest_due)", ctx)
    assert payment == Decimal("645823.03")


def test_extract_variable_refs():
    engine = FormulaEngine()
    refs = engine.extract_variable_refs("MIN(net_distributable, a_interest_due)")
    assert set(refs) == {"net_distributable", "a_interest_due"}


def test_validate_formula_good():
    engine = FormulaEngine()
    errors = engine.validate("a + b", {"a", "b"})
    assert errors == []


def test_validate_formula_unknown_var():
    engine = FormulaEngine()
    errors = engine.validate("a + unknown", {"a"})
    assert any("unknown" in e for e in errors)


def test_validate_formula_bad_syntax():
    engine = FormulaEngine()
    errors = engine.validate("a + + b", {"a", "b"})
    assert len(errors) > 0


def test_validate_typo_suggestion():
    engine = FormulaEngine()
    errors = engine.validate("class_a_balence", {"class_a_balance"})
    assert len(errors) == 1
    assert "did you mean" in errors[0]
    assert "class_a_balance" in errors[0]


def test_validate_no_suggestion_for_gibberish():
    engine = FormulaEngine()
    errors = engine.validate("zzzzzzz", {"class_a_balance", "total_collections"})
    assert len(errors) == 1
    assert "did you mean" not in errors[0]
    assert "Unknown variable: zzzzzzz" == errors[0]


def test_nested_functions():
    engine = FormulaEngine()
    ctx = {"a": Decimal("10"), "b": Decimal("20"), "c": Decimal("5")}
    result = engine.execute("MAX(MIN(a, b), c)", ctx)
    assert result == Decimal("10")
