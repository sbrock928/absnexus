"""Formula evaluator — walks AST with Decimal arithmetic."""

import math
from decimal import Decimal, ROUND_HALF_UP

from app.formulas.parser import (
    ASTNode,
    NumberNode,
    VariableNode,
    BinaryOpNode,
    ComparisonNode,
    FunctionCallNode,
    UnaryMinusNode,
)


class FormulaError(Exception):
    pass


def evaluate(node: ASTNode, context: dict[str, Decimal]) -> Decimal:
    """Evaluate an AST node with the given variable context."""
    if isinstance(node, NumberNode):
        return Decimal(node.value)

    if isinstance(node, VariableNode):
        if node.name not in context:
            raise FormulaError(f"Unknown variable: {node.name}")
        return context[node.name]

    if isinstance(node, UnaryMinusNode):
        return -evaluate(node.operand, context)

    if isinstance(node, BinaryOpNode):
        left = evaluate(node.left, context)
        right = evaluate(node.right, context)
        if node.op == "+":
            return left + right
        if node.op == "-":
            return left - right
        if node.op == "*":
            return left * right
        if node.op == "/":
            if right == 0:
                raise FormulaError("Division by zero")
            return left / right
        raise FormulaError(f"Unknown operator: {node.op}")

    if isinstance(node, ComparisonNode):
        left = evaluate(node.left, context)
        right = evaluate(node.right, context)
        result = False
        if node.op == ">":
            result = left > right
        elif node.op == "<":
            result = left < right
        elif node.op == ">=":
            result = left >= right
        elif node.op == "<=":
            result = left <= right
        elif node.op == "==":
            result = left == right
        elif node.op == "!=":
            result = left != right
        return Decimal("1") if result else Decimal("0")

    if isinstance(node, FunctionCallNode):
        return _eval_function(node, context)

    raise FormulaError(f"Unknown node type: {type(node)}")


def _eval_function(node: FunctionCallNode, context: dict[str, Decimal]) -> Decimal:
    args = [evaluate(a, context) for a in node.args]
    name = node.name

    if name == "MIN":
        if len(args) < 2:
            raise FormulaError("MIN requires at least 2 arguments")
        return min(args)

    if name == "MAX":
        if len(args) < 2:
            raise FormulaError("MAX requires at least 2 arguments")
        return max(args)

    if name == "ABS":
        if len(args) != 1:
            raise FormulaError("ABS requires exactly 1 argument")
        return abs(args[0])

    if name == "IF":
        if len(args) != 3:
            raise FormulaError("IF requires exactly 3 arguments (condition, true_val, false_val)")
        return args[1] if args[0] != Decimal("0") else args[2]

    if name == "ROUND":
        if len(args) not in (1, 2):
            raise FormulaError("ROUND requires 1 or 2 arguments")
        places = int(args[1]) if len(args) == 2 else 0
        return args[0].quantize(Decimal(10) ** -places, rounding=ROUND_HALF_UP)

    if name == "CEILING":
        if len(args) not in (1, 2):
            raise FormulaError("CEILING requires 1 or 2 arguments")
        if len(args) == 1:
            return Decimal(math.ceil(args[0]))
        multiple = args[1]
        if multiple == 0:
            return Decimal("0")
        return Decimal(math.ceil(args[0] / multiple)) * multiple

    if name == "FLOOR":
        if len(args) not in (1, 2):
            raise FormulaError("FLOOR requires 1 or 2 arguments")
        if len(args) == 1:
            return Decimal(math.floor(args[0]))
        multiple = args[1]
        if multiple == 0:
            return Decimal("0")
        return Decimal(math.floor(args[0] / multiple)) * multiple

    if name == "SUM":
        return sum(args, Decimal("0"))

    raise FormulaError(f"Unknown function: {name}")
