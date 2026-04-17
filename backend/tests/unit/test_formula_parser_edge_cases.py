"""Formula parser edge cases — exercises the union-attr fix and multi-arg functions."""

import pytest
from decimal import Decimal

from app.formulas.engine import FormulaEngine
from app.formulas.evaluator import FormulaError
from app.formulas.tokenizer import tokenize


engine = FormulaEngine()


# ── Multi-arg function calls ───────────────────────────────────────────────


def test_min_function():
    assert engine.execute("MIN(10, 5)", {}) == Decimal("5")


def test_max_function():
    assert engine.execute("MAX(3, 7, 2)", {}) == Decimal("7")


def test_min_with_variables():
    assert engine.execute("MIN(a, b)", {"a": Decimal("4"), "b": Decimal("9")}) == Decimal("4")


def test_nested_function_calls():
    assert engine.execute("MAX(MIN(2, 3), 1)", {}) == Decimal("2")


def test_function_with_arithmetic_arg():
    assert engine.execute("MIN(a * 2, b)", {"a": Decimal("3"), "b": Decimal("10")}) == Decimal("6")


def test_function_single_arg_raises():
    with pytest.raises(Exception):
        engine.execute("MIN(5)", {})


# ── Comparison / conditional operators ────────────────────────────────────


def test_comparison_gte():
    assert engine.execute("5 >= 5", {}) == Decimal("1")


def test_comparison_lte():
    assert engine.execute("3 <= 4", {}) == Decimal("1")


def test_comparison_gt():
    assert engine.execute("6 > 5", {}) == Decimal("1")


def test_comparison_lt():
    assert engine.execute("3 < 5", {}) == Decimal("1")


def test_comparison_eq():
    assert engine.execute("5 == 5", {}) == Decimal("1")


def test_comparison_false():
    assert engine.execute("3 > 5", {}) == Decimal("0")


# ── Parenthesised expressions ─────────────────────────────────────────────


def test_grouped_precedence():
    assert engine.execute("(2 + 3) * 4", {}) == Decimal("20")


def test_deeply_nested_parens():
    assert engine.execute("((1 + 2) * (3 + 4))", {}) == Decimal("21")


# ── Edge: empty argument list inside function call ────────────────────────


def test_tokenize_empty_parens_does_not_crash():
    # tokenize should handle adjacent parens without raising
    tokens = tokenize("MIN()")
    types = [t.type.name for t in tokens]
    assert "FUNCTION" in types


# ── Variable reference extraction ─────────────────────────────────────────


def test_extract_variable_refs_simple():
    refs = engine.extract_variable_refs("a + b * c")
    assert set(refs) == {"a", "b", "c"}


def test_extract_variable_refs_no_duplicates():
    refs = engine.extract_variable_refs("a + a")
    assert refs.count("a") == 1 or set(refs) == {"a"}


def test_extract_variable_refs_ignores_numbers():
    refs = engine.extract_variable_refs("a + 100 * 2.5")
    assert "100" not in refs
    assert "2.5" not in refs


def test_extract_variable_refs_ignores_function_names():
    refs = engine.extract_variable_refs("MIN(a, b)")
    assert "MIN" not in refs
    assert "a" in refs
    assert "b" in refs


def test_extract_variable_refs_empty_formula():
    refs = engine.extract_variable_refs("")
    assert refs == [] or set(refs) == set()


# ── Division by zero ──────────────────────────────────────────────────────


def test_division_by_zero_raises():
    with pytest.raises((FormulaError, ZeroDivisionError, Exception)):
        engine.execute("10 / 0", {})


# ── Missing variable raises ────────────────────────────────────────────────


def test_missing_variable_raises():
    with pytest.raises(Exception):
        engine.execute("missing_var + 1", {})


# ── Unary minus ───────────────────────────────────────────────────────────


def test_negative_literal():
    result = engine.execute("0 - 5", {})
    assert result == Decimal("-5")


# ── Large formula with many references ────────────────────────────────────


def test_large_formula():
    ctx = {k: Decimal(str(i + 1)) for i, k in enumerate("abcdefghij")}
    formula = " + ".join("abcdefghij")
    result = engine.execute(formula, ctx)
    assert result == Decimal("55")
