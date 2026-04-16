"""Formula validation endpoints."""
from decimal import Decimal
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.formulas.engine import FormulaEngine

router = APIRouter()


class FormulaValidateRequest(BaseModel):
    formula: str
    known_variables: list[str] = []


class FormulaTestRequest(BaseModel):
    formula: str
    context: dict[str, str] = {}


@router.post("/validate")
def validate_formula(body: FormulaValidateRequest):
    engine = FormulaEngine()
    errors = engine.validate(body.formula, set(body.known_variables))
    refs = engine.extract_variable_refs(body.formula)
    return {"valid": len(errors) == 0, "errors": errors, "references": refs}


@router.post("/test")
def test_formula(body: FormulaTestRequest):
    engine = FormulaEngine()
    context = {k: Decimal(v) for k, v in body.context.items()}
    try:
        result = engine.execute(body.formula, context)
        resolved = engine.resolve_formula(body.formula, context)
        return {"result": str(result), "resolved": resolved}
    except Exception as e:
        return {"error": str(e)}
