# ABSNexus — Structured Finance DAG Builder

## Overview

Paying agent tool for structured finance deals (ABS, MBS, CRT). Two teams:
- **Analytics** models deals: variables, cell mappings, DAG calculations, export configs
- **Analysts** processes monthly: upload tapes, extract, execute, validate, export CSVs

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy 2.0, Pydantic v2, MSSQL (prod) / SQLite (dev/test)
- **Frontend:** React, TypeScript, CSS Modules, Vite, React Flow
- **CI/CD:** Azure DevOps — black, mypy strict, pylint ≥8.0, pytest ≥80%

## Quick Start

```bash
# Backend
cd backend
pip install -r requirements.txt
python run.py

# Frontend
cd frontend
npm install
npm run dev
```

## Project Structure (PRs 1-6)

```
backend/
  app/
    core/           # Config, database engine
    models/         # SQLAlchemy models (User, Servicer, Deal, AuditLog, Variable, Mapping, Tranche, DAG)
    schemas/        # Pydantic v2 request/response models
    services/       # Auth, Audit, Deal services
    dependencies.py # Windows username auth, role enforcement
    routers/        # Auth, Servicers, Deals, Health
    variables/      # 3-tier variable system (dao/service/router)
    mappings/       # Cell mapping (dao/service/router)
    tranches/       # Tranche management (dao/service/router)
    dag/            # DAG builder with versioning (dao/service/router)
    formulas/       # Formula engine (tokenizer/parser/evaluator/engine/router)
    utils/          # ExcelReader, FileManager
  tests/
    unit/           # Service + engine tests
    functional/     # Route tests
  alembic/          # Database migrations

frontend/
  src/
    api/            # Fetch client
    auth/           # AuthProvider, useAuth
    components/     # AppShell, Sidebar
    pages/          # DealList, VariableLibrary, Processing, AuditLog
    styles/         # Global dark theme CSS
    types/          # TypeScript interfaces
```

## Architecture Decisions

- **Normalized DAG tables** not JSON blobs — enables versioning, querying, cloning
- **Every save = new DAG version** — full snapshot with revert capability
- **Two streams enforced at schema level** — distribution vs validation, never cross
- **Custom formula parser** (~250 LOC) — MIN/MAX/ABS/IF/ROUND/CEILING/FLOOR/SUM
- **3-tier variables** — system → servicer → deal override semantics
- **Windows username auth** — no login screen, pre-registered users only
- **Sync SQLAlchemy** — 30 users, no need for async complexity
