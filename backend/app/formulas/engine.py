"""High-level formula engine — ties tokenizer, parser, evaluator together."""

import difflib
from decimal import Decimal

from app.formulas.tokenizer import tokenize, TokenType
from app.formulas.parser import (
    parse,
)
from app.formulas.evaluator import evaluate


class FormulaEngine:
    """Stateless formula engine used by DAG executor and validation endpoints."""

    def execute(self, formula: str, context: dict[str, Decimal]) -> Decimal:
        tokens = tokenize(formula)
        ast = parse(tokens)
        return evaluate(ast, context)

    def validate(self, formula: str, known_vars: set[str]) -> list[str]:
        """Validate formula syntax and check variable references."""
        errors: list[str] = []
        try:
            tokens = tokenize(formula)
        except ValueError as e:
            return [str(e)]

        try:
            ast = parse(tokens)
        except ValueError as e:
            return [str(e)]

        refs = self.extract_variable_refs(formula)
        for ref in refs:
            if ref not in known_vars:
                suggestions = difflib.get_close_matches(ref, known_vars, n=1, cutoff=0.6)
                if suggestions:
                    errors.append(f"Unknown variable: {ref} (did you mean '{suggestions[0]}'?)")
                else:
                    errors.append(f"Unknown variable: {ref}")

        return errors

    def extract_variable_refs(self, formula: str) -> list[str]:
        """Extract all variable names referenced in a formula."""
        try:
            tokens = tokenize(formula)
        except ValueError:
            return []
        return [t.value for t in tokens if t.type == TokenType.VARIABLE]

    def resolve_formula(self, formula: str, context: dict[str, Decimal]) -> str:
        """Show formula with values substituted for debugging/trace."""
        resolved = formula
        for var_name, value in sorted(context.items(), key=lambda x: -len(x[0])):
            resolved = resolved.replace(var_name, str(value))
        return resolved
