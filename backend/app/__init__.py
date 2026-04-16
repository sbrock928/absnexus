"""Application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import engine, Base
from app.routers import auth, servicers, deals, health
from app.variables.router import router as variables_router
from app.mappings.router import router as mappings_router
from app.tranches.router import router as tranches_router
from app.dag.router import router as dag_router
from app.formulas.router import router as formulas_router
from app.processing.router import router as processing_router
from app.export.router import router as export_router
from app.audit.router import router as audit_router
from app.users.router import router as users_router
from app.batch.router import router as batch_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core import settings
    if not settings.testing:
        import app.models  # noqa: F401
        Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="ABSNexus", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(servicers.router, prefix="/api/servicers", tags=["servicers"])
    app.include_router(deals.router, prefix="/api/deals", tags=["deals"])
    app.include_router(variables_router, prefix="/api/variables", tags=["variables"])
    app.include_router(mappings_router, prefix="/api/deals", tags=["mappings"])
    app.include_router(tranches_router, prefix="/api/deals", tags=["tranches"])
    app.include_router(dag_router, prefix="/api/deals", tags=["dag"])
    app.include_router(formulas_router, prefix="/api/formulas", tags=["formulas"])
    app.include_router(processing_router, prefix="/api/deals", tags=["processing"])
    app.include_router(export_router, prefix="/api", tags=["export"])
    app.include_router(audit_router, prefix="/api/audit", tags=["audit"])
    app.include_router(users_router, prefix="/api/users", tags=["users"])
    app.include_router(batch_router, prefix="/api", tags=["batch"])

    return app
