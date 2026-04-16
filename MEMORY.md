# Project Handoff for Claude Code

## 1. Project overview

- **Project name**: ABSNexus (UI display name) — repo/package name is `structured-finance-builder`; backend package is `sf-builder-backend`.
- **Goal**: Internal paying agent tool for structured finance deals (ABS, MBS, CRT). Models deals as normalized calculation DAGs, ingests monthly servicer tapes (Excel), runs waterfall distributions + validation checks, reconciles against tape ending balance, and exports CSV load files for downstream payment systems.
- **Primary users**: Two internal teams, ~30 analysts total.
  - **Analytics team (modelers)** — define tranche structures, map servicer tape cells to canonical variables, build DAG calculation graphs, configure export columns. Role string: `analytics`.
  - **Analyst team (processors)** — upload monthly servicer tapes, run extractions, review calculated distributions, reconcile waterfall, validate against tape values, export CSV payment files. Role string: `analyst`. Read-only on deal models.
  - **Admins** — user management + everything else. Role string: `admin`.
- **Current stage**: MVP is functionally complete end-to-end. A single analyst can log in, pick a deal, upload a tape, extract variables, run calculations, reconcile the waterfall, validate against tape values, investigate failures via lineage, and export a CSV — or run multiple deals at once via the batch processor. Demo deal (SVCB 2022-7) seeds a full working configuration. Remaining work is secondary screens (audit log UI, users management UI) and polish (toasts, loading skeletons, Levenshtein typo suggestions in formula validator, PyInstaller bundling).

---

## 2. Tech stack

### Frontend
- **Vite + React 18 + TypeScript** (strict mode).
- **@xyflow/react** (React Flow) for the DAG canvas visual editor. Four custom node types with colored left borders (green=input, blue=calc, purple=distribution, orange=validation).
- **CSS Modules** + a single global stylesheet with CSS custom properties for the dark theme. **No Tailwind** — explicitly rejected.
- **@tanstack/react-query** for server state.
- **react-router-dom** v6 for routing.
- Auth: `AuthProvider` context → `useAuth()` hook → `{ user, role, isModeler, isAdmin, isAnalyst }`. No permission matrix. Gates are inline: `{isModeler && <button>...</button>}`.

### Backend
- **FastAPI** with `create_app()` application factory pattern.
- **Sync** SQLAlchemy 2.0 (`sessionmaker`, not `async_sessionmaker`).
- **Pydantic v2** with `pydantic-settings` for config.
- **`pyodbc`** driver (`mssql+pyodbc`) for MSSQL in production.
- **`oracledb`** for read-only Oracle tranche balance queries.
- **`openpyxl`** for reading servicer tape Excel workbooks.
- **`networkx`** for DAG topological sort, cycle detection, and ancestor tracing (used in `DagExecutor.get_lineage`).
- **Custom recursive-descent formula parser** in `app/formulas/` (tokenizer + parser + evaluator + engine). `Decimal` arithmetic throughout. Supports `+ − * /`, comparisons (`> < >= <= == !=`), parentheses, unary minus, variable refs, and 8 functions: `MIN`, `MAX`, `ABS`, `IF`, `ROUND`, `CEILING`, `FLOOR`, `SUM`. No `eval()`.
- **Alembic** migrations. Auto-apply in DEV/UAT; `alembic upgrade head --sql` for PROD DBA review.
- **Auth**: Windows username auto-detection via `os.getlogin()` in a FastAPI dependency. No login screen.

### Database
- **Microsoft SQL Server** (not containerized) — three environments: DEV, UAT, PROD.
- **SQLite in-memory** for tests (`sqlite:///:memory:` via `ABSNEXUS_DATABASE_URL`, `ABSNEXUS_TESTING=1`).
- **SQLite file** (`backend/absnexus.db`) for local dev. Seeded via `python seed.py` from the `backend/` directory.
- **Oracle** (read-only) for current tranche balances. Queried by CUSIP list at the start of each monthly run.

### Infra / deployment
- Runs locally on analysts' Windows machines. No containerization.
- **PyInstaller** bundling for single-exe distribution of FastAPI + built React static files (planned — see Section 7).
- **Azure DevOps** CI/CD. `azure-pipelines.yml` triggers on every PR to `development` branch.

### Testing
- **pytest** + **pytest-cov** with `httpx` `TestClient`.
- Split into `backend/tests/unit/` (no DB, no IO) and `backend/tests/functional/` (TestClient + SQLite in-memory).
- `conftest.py` provides the test DB fixture, TestClient with dependency overrides on `get_db` and `get_current_user`, plus factories.
- Frontend: `tsc --noEmit` + `vite build` are the CI gates. No unit-test framework wired up.

### Code quality gates (CI-enforced on every PR)
- `black --check` — zero diffs.
- `mypy` strict — zero errors.
- `pylint` — minimum score **8.0**.
- `pytest` — all pass, **≥80%** coverage on new code.
- `tsc --noEmit` — zero TS errors.
- `vite build` — must succeed.

---

## 3. Architecture summary

Monorepo: `backend/` (FastAPI) + `frontend/` (Vite+React) as siblings. The backend uses a **feature-based layered architecture** with shared models/schemas and transaction management concentrated in `get_db`.

### Backend layout

```
app/
├── core/                # Shared: config, database (auto-commit get_db), Base
├── dependencies.py      # get_current_user (Windows username), require_role()
├── models/              # Shared SQLAlchemy 2.0 Mapped declarative models
├── schemas/             # Shared Pydantic v2 request/response schemas
├── utils/               # excel_reader, file_manager, oracle_client
├── formulas/            # tokenizer + parser + evaluator + engine + router
├── routers/             # Legacy flat routers (auth, health, servicers, deals)
├── services/            # Legacy services (tape_extractor, dag_executor,
│                        #   prior_month_service, export_service, audit_service,
│                        #   deal_service, auth_service, clone_service, etc.)
├── variables/           # router.py + service.py + dao.py (3-tier + aliases)
├── mappings/            # router.py + service.py + dao.py (tape cell → variable)
├── tranches/            # router.py + service.py + dao.py (Oracle sync)
├── dag/                 # router.py + service.py + dao.py (versioning, revert)
├── processing/          # router.py + service.py + dao.py (runs, extract,
│                        #   execute, waterfall, export wiring, reextract)
├── export/              # router.py + service.py + dao.py (configurable columns,
│                        #   presets: system_a, system_b)
├── batch/               # router.py + service.py + dao.py (multi-deal runs, zip)
└── __init__.py          # create_app() + include_router() for every feature
```

**Note:** There are two partially-overlapping organizational patterns in the repo — newer features (`variables/`, `mappings/`, `tranches/`, `dag/`, `processing/`, `export/`, `batch/`) follow the feature-folder router/service/dao split; older pieces still live in `app/routers/` and `app/services/` (notably `tape_extractor.py`, `dag_executor.py`, `prior_month_service.py`, `export_service.py`, `audit_service.py`, `deal_service.py`, `clone_service.py`). Newer code tends to import from the feature folders; services and legacy routers continue to work. Don't refactor this mid-feature; match whatever pattern the surrounding code uses.

### Layering rules
- **`router.py`** — FastAPI endpoints. Handles HTTP concerns, 404s, `HTTPException`, role guards via `require_role()`. Returns SQLAlchemy objects; FastAPI `response_model` serializes.
- **`service.py`** — pure business logic. Never calls `commit()`. Returns SQLAlchemy objects.
- **`dao.py`** — database access only: `db.add()`, `db.flush()`, `db.delete()`, queries. Never commits. `flush()` assigns IDs.
- **`app/core/database.py::get_db()`** — owns transaction management. Auto-commits on request success, rolls back on exception, closes session in `finally`.

### Monthly processing pipeline

```
Servicer Excel tape ─► FileManager stores at data/uploads/{period}/{deal}/
                       │
                       ▼
                ProcessingRun (pending)
                       │
                       ▼                  (snapshots VariableMappings onto run)
                TapeExtractor.extract_all ─────► ExtractedValue rows
                       │                          + prior-month % change warnings
                       │                          + >50% delta flags
                       ▼
                DagExecutor.execute ─► assembles 5-source context:
                       │                 1. Prior month's completed run tape values (_prior)
                       │                 2. Prior month's completed run calc results (_prior)
                       │                 3. Current run tape values
                       │                 4. Tranche balances (auto + 144A/RegS splits)
                       │                 5. Current upstream node results (topo-sort order)
                       │               ...then topologically executes each DagNode,
                       │               writing an ExecutionStep per node with the
                       │               resolved formula and result. Validation nodes
                       │               compare calculated vs tape, within tolerance.
                       │               Stamps run.dag_version_id + run.prior_run_id.
                       ▼
                Waterfall reconciliation ──► if calculated remainder ≠ tape ending
                       │                       balance (within tolerance), BLOCK export.
                       ▼
                ExportService.generate_csv ─► writes CSV to
                                               data/exports/{deal_id}/{period}/,
                                               stamps run.export_file_path + SHA-256
                                               file hash, marks run completed.
```

**Two calculation streams, never cross.** Distribution-stream nodes are the only nodes that appear in exports. Validation-stream nodes do tolerance checks against tape values. Cross-stream edges are rejected at save time.

**DAG versioning.** Every save on the DAG editor creates a new `dag_version` with a full snapshot. `processing_run.dag_version_id` is stamped at execution time for reproducibility. Revert creates a new version (append-only).

**Variable three-layer naming.** Canonical (`total_collections`, used in formulas), display alias (per-deal/servicer UI override in `variable_alias`), tape label (on the Excel, stored on `variable_mapping.tape_label`). Formulas always use canonical.

---

## 4. Important directories and files

```
structured-finance-builder/
├── azure-pipelines.yml              # CI/CD gates
├── MEMORY.md                        # this file
├── README.md                        # quick-start
├── .gitignore                       # Python, Node, editors, project-specific
├── backend/
│   ├── .venv/                       # venv HERE, not at repo root
│   ├── requirements.txt
│   ├── pyproject.toml               # black / mypy / pylint / pytest config
│   ├── alembic.ini
│   ├── run.py                       # uvicorn entrypoint for local dev
│   ├── seed.py                      # Demo data seed — users, servicers, vars,
│   │                                #   SVCB 2022-7 full config
│   ├── fix_svcb.py                  # One-off fix for missing mappings/edges
│   │                                #   on the SVCB deal. Run only when seed
│   │                                #   drifts; not part of normal workflow.
│   ├── absnexus.db                  # local SQLite (gitignored)
│   ├── alembic/
│   │   ├── env.py                   # reads URL from app/core/config.py
│   │   └── versions/                # migration files — tracked in git
│   ├── app/
│   │   ├── __init__.py              # create_app() + router wiring
│   │   ├── core/                    # config.py, database.py, __init__.py
│   │   ├── dependencies.py          # get_current_user, require_role
│   │   ├── models/
│   │   │   ├── __init__.py          # imports all for Alembic discovery
│   │   │   ├── user.py
│   │   │   ├── servicer.py
│   │   │   ├── deal.py
│   │   │   ├── audit_log.py         # AuditLog (model only; no UI yet)
│   │   │   ├── variable.py          # VariableDefinition + VariableAlias
│   │   │   ├── variable_mapping.py  # VariableMapping (has tape_label column)
│   │   │   ├── tranche.py           # DealTranche + TrancheBalance
│   │   │   ├── dag.py               # DagNode, DagEdge, DagVersion
│   │   │   ├── processing.py        # ProcessingRun, ExtractedValue,
│   │   │   │                        #   ExecutionStep
│   │   │   ├── export.py            # ExportTemplate (legacy),
│   │   │   │                        #   ExportTemplateColumn (legacy),
│   │   │   │                        #   ExportFieldMapping (legacy),
│   │   │   │                        #   ExportColumn (NEW configurable model)
│   │   │   └── batch.py             # BatchRun
│   │   ├── schemas/                 # mirrors models/
│   │   ├── formulas/
│   │   │   ├── tokenizer.py         # numbers, vars, funcs, ops, comparisons
│   │   │   ├── parser.py            # recursive descent — AST nodes
│   │   │   ├── evaluator.py         # Decimal walk + 8 functions + div-by-zero
│   │   │   ├── engine.py            # FormulaEngine (execute/validate/
│   │   │   │                        #   extract_variable_refs/resolve_formula)
│   │   │   └── router.py            # POST /validate + POST /test
│   │   ├── variables/               # 3-tier scope + aliases
│   │   ├── mappings/                # per-deal cell mappings + cross-deal view
│   │   ├── tranches/                # Oracle refresh + build_tranche_context
│   │   ├── dag/                     # save-creates-version + revert + deactivate
│   │   ├── processing/              # runs, upload, extract, execute, trace,
│   │   │                            #   lineage, waterfall, reextract-variable,
│   │   │                            #   export, clone
│   │   ├── export/                  # Configurable columns with PRESETS dict
│   │   │                            #   (system_a, system_b), preview, generate
│   │   ├── batch/                   # Multi-deal run orchestration + zip export
│   │   ├── routers/                 # Legacy: auth.py, health.py, servicers.py
│   │   ├── services/                # Legacy services; newer features are
│   │   │                            #   inside feature folders
│   │   └── utils/
│   │       ├── excel_reader.py
│   │       ├── file_manager.py
│   │       └── oracle_client.py
│   └── tests/
│       ├── conftest.py              # test DB, TestClient with DI overrides
│       ├── unit/                    # test_formula_engine, test_tape_extractor,
│       │                            #   test_dag_service, test_batch_service,
│       │                            #   test_export_service, test_prior_month,
│       │                            #   ...
│       └── functional/              # test_processing_routes (full e2e),
│                                    #   test_batch_routes, test_dag_routes,
│                                    #   test_mapping_routes, ...
├── frontend/
│   ├── package.json                 # @xyflow/react, react-query, react-router
│   ├── tsconfig.json                # strict
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                  # <AuthProvider>, route table
│       ├── styles/global.css        # dark theme CSS variables
│       ├── types/index.ts
│       ├── api/
│       │   ├── client.ts            # fetch wrapper (api.get, api.post, ...)
│       │   ├── deals.ts
│       │   ├── variables.ts
│       │   ├── mappings.ts          # (incl. reextractVariable)
│       │   ├── tranches.ts
│       │   ├── dag.ts
│       │   ├── processing.ts
│       │   ├── export.ts
│       │   └── batch.ts             # getBatchSummary, getBatchZipUrl, ...
│       ├── auth/                    # AuthProvider, useAuth, AccessDenied
│       ├── components/
│       │   ├── layout/              # AppShell, Sidebar, DealDetailLayout
│       │   ├── dag-builder/         # React Flow custom nodes + canvas
│       │   │                        #   (InputNode, CalcNode, DistNode,
│       │   │                        #    ValidationNode, DagGraphView,
│       │   │                        #    NodePropertiesPanel, VersionHistory)
│       │   ├── cell-mapper/         # CellMapper + CellMapperModal (used
│       │   │                        #   inline in ProcessingPage extraction)
│       │   └── processing/          # WaterfallTrace
│       └── pages/
│           ├── DealListPage.tsx
│           ├── DealDetailPage.tsx
│           ├── VariableLibraryPage.tsx
│           ├── DealAliasesPage.tsx
│           ├── MappingOverviewPage.tsx
│           ├── CellMapperPage.tsx
│           ├── CrossDealComparisonPage.tsx
│           ├── TrancheSetupPage.tsx
│           ├── DagEditorPage.tsx    # toggle: table view / graph view
│           ├── ExportConfigPage.tsx
│           ├── ProcessingPage.tsx   # 6-step stepper (adds Waterfall step)
│           ├── ExecutionTracePage.tsx
│           ├── LineagePage.tsx      # failure investigation + "Likely culprit"
│           ├── BatchProcessingPage.tsx
│           ├── BatchResultsPage.tsx
│           ├── BatchHistoryPage.tsx
│           └── AuditLogPage.tsx     # ⚠ STUB — renders "Coming in PR-14"
└── data/
    ├── uploads/{YYYY-MM}/{deal_id}/{filename}
    └── exports/{deal_id}/{YYYY-MM}/{filename}
```

---

## 5. How to run the project

```bash
# Backend (first time)
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
pip install -r requirements.txt

# Seed the local SQLite DB (creates absnexus.db with demo SVCB deal)
python seed.py

# If the demo deal needs mapping fixes (normally not required):
# python fix_svcb.py

# Run dev server
python run.py                 # http://localhost:8000 (docs at /docs)

# Run tests
ABSNEXUS_TESTING=1 ABSNEXUS_DATABASE_URL="sqlite:///:memory:" pytest -q
# With coverage
pytest --cov=app --cov-report=term-missing

# Lint / typecheck
black --check app tests
mypy app
pylint app

# Frontend
cd ../frontend
npm install
npm run dev                   # http://localhost:5173, /api proxied to :8000
npm run build                 # vite build → dist/
npx tsc --noEmit              # typecheck

# Alembic
alembic revision --autogenerate -m "description"
alembic upgrade head          # DEV/UAT
alembic upgrade head --sql    # PROD — generates DDL script for DBA review
```

**Known install issue**: `pyodbc` on Windows requires Microsoft Visual C++ 14.0 Build Tools.

---

## 6. Current functionality

Essentially everything from PRs 1–13 of the v6 plan is shipped and exercised by the SVCB 2022-7 demo. Concretely:

**Auth & users**
- Windows username auto-detection. `/api/auth/me` returns role + display name.
- `require_role()` enforces role gates on write endpoints.
- Frontend: `AuthProvider` → `useAuth()` → `{ isModeler, isAdmin, isAnalyst }`. Sidebar is role-filtered. Admin-only `/users` nav link renders (but the page itself isn't built yet — see Section 7).

**Deals**
- Full CRUD. Status filter tabs (All / Active / Draft / Archived). Servicer column with lookup.
- `DealDetailPage` with tabbed sub-layout: Overview, Mappings, Tranches, DAG, Export, Aliases.
- **Deal cloning**: `POST /api/deals/{id}/clone` with toggles for DAG, mappings, exports, tranches. `CloneService` duplicates all child records with FK remapping. New deal starts in `draft` status.

**Variables**
- 3-tier scope (system / servicer / deal) with resolution: deal → servicer → system.
- `VariableAlias` table for per-deal/servicer display-name overrides. Cosmetic only; canonical name is always used in formulas.
- `VariableLibraryPage` with scope tabs, create/edit, inline editing.
- `DealAliasesPage` for per-deal aliases (also editable inline on the deal detail page).
- `CrossDealComparisonPage` for one variable across all deals.

**Cell mappings**
- `VariableMapping` with `sheet_name`, `column_letter`, `row_number`, `tape_label`.
- `CellMapper` component renders a live Excel grid with click-to-bind, green highlights for mapped cells, test-extract preview.
- `MappingOverviewPage` groups mappings by sheet, shows unmapped section.
- Inline remapping during processing: if extraction throws a warning, user clicks "Remap" → `CellMapperModal` opens pre-selected → save re-extracts just that variable.

**Tranches**
- `DealTranche` + `TrancheBalance` with 144A/RegS split support on same class label.
- Oracle sync button queries by CUSIP list; manual entry also supported.
- `TrancheService.build_tranche_context()` auto-injects deterministic formula variables at execution time: `class_a_balance`, `class_a_balance_144a`, `class_a_balance_regs`, `class_a_note_rate`, plus `_prior` variants.
- `TrancheSetupPage` shows card grid per class with both CUSIP variants visible.

**DAG builder**
- `DagNode` (with `default_prior_value`, `input_source`, `stream`, `is_active`), `DagEdge`, `DagVersion`. Every save creates a new version; revert is non-destructive. Node deactivation (soft) rather than deletion.
- Cross-stream edges rejected at save (distribution ↔ validation).
- `DagEditorPage` has both a table view and a React Flow canvas with drag-from-palette, custom node colors, and a properties panel.

**Formula engine** (PR-7 ✅)
- `app/formulas/` — tokenizer, parser (recursive descent), evaluator, `FormulaEngine`, router.
- 8 functions: MIN, MAX, ABS, IF, ROUND, CEILING, FLOOR, SUM. All Decimal.
- Comparisons supported (`> < >= <= == !=`). Unary minus supported.
- Division by zero raises `FormulaError`.
- `POST /api/formulas/validate` (syntax check + unknown-var list).
- `POST /api/formulas/test` (eval with a context dict — used for sandbox testing).
- `FormulaEngine.resolve_formula()` substitutes values into the formula string for trace display.
- ⚠ **Known spec gap**: the PR-7 guide called for Levenshtein "Did you mean?" suggestions on unknown variables. Current code returns `"Unknown variable: {ref}"` without suggestions. Not blocking.

**Tape extraction** (PR-8 ✅)
- `ProcessingRun` (with `tape_file_path`, `tape_file_hash`, `mappings_snapshot`, `prior_run_id`, `dag_version_id`, `status`, `export_file_path`, `export_file_hash`, `batch_id`, etc.). `ExtractedValue` per variable.
- `TapeExtractor.extract_all()` reads by sheet/col/row, casts to data type, snapshots mappings as JSON on the run.
- Prior calendar month lookup filters on `status == "completed"`. >50% change → `warning` field populated. Missing/empty cell → warning.
- `ProcessingService.reextract_variable()` for single-variable re-extraction after a cell remap.

**DAG execution** (PR-9 ✅)
- `DagExecutor.execute()` assembles the 5-source context, topo-sorts via networkx, walks nodes in order. Cycle detection. Per-node `ExecutionStep` row with `formula`, `resolved_formula`, `result`.
- `PriorMonthService` handles `find_prior_run` + `build_prior_context` (`_prior` suffix for every tape and calc value) + `get_default_priors` (first-month fallback using `dag_node.default_prior_value`).
- Stamps `run.dag_version_id`, `run.prior_run_id`, `run.total_distribution`, `run.validations_passed`, `run.validations_total`.
- `ExecutionTracePage` shows banner + 4 stat cards + sectioned tables: inputs, intermediate calcs, distribution outputs, validation checks. Stream toggle (Distribution / Validation).

**Validation + lineage** (PR-10 ✅)
- Validation nodes compare calculated vs tape value. Absolute or percentage tolerance (`tolerance_type` column). `step.passed = 1|0`.
- `DagExecutor.get_lineage(run_id, node_key)` walks `networkx.ancestors()` to build the upstream dependency list.
- `LineagePage` renders the failure-investigation view with "Likely culprit" tagging, per-node prior-value deltas, and a "Probable causes" section.
- Drill-in buttons on `ExecutionTracePage` (Investigate for failures, Trace for passes) and on `BatchResultsPage`.

**Waterfall reconciliation** (bonus — not in original plan)
- Between execution and export: `ProcessingService.get_waterfall()` runs through distribution steps subtracting each from the starting balance. Checks final remainder against tape ending balance within tolerance.
- `WaterfallTrace` component renders step-by-step table, pass/fail banner, 4 stat cards.
- `ExportService.generate_csv()` **blocks** if reconciliation failed: raises `ValueError("Waterfall reconciliation failed...")`.

**Export** (PR-11 ✅, extended)
- Original models present: `ExportTemplate`, `ExportTemplateColumn`, `ExportFieldMapping` (with `prorate_type` for 144A/RegS). `ExportService.generate_csv()` writes to `data/exports/{deal_id}/{period}/`, SHA-256 hash stamped on run.
- Newer `ExportColumn` model for per-deal configurable column layouts. Four value sources: `distribution_node`, `literal`, `run_meta`, `deal_meta`. Supports `prorate_by` / `prorate_class_label` for 144A/RegS splits.
- `ExportColumnService.apply_preset()` with `PRESETS = { "system_a": ..., "system_b": ... }`. Copy-from-preset replaces existing columns.
- `ExportConfigPage` for setup; preview endpoint shows sample CSV rows.

**Processing workflow UI** (PR-12 ✅, extended to 6 steps)
- `ProcessingPage` — 6-step stepper: **Select deal → Upload tape → Extract → Execute → Waterfall → Export**.
- `statusToStep()` resumes a run from whatever status it was left in. `canNavigate()` lets the user click back to any completed step.
- Inline `CellMapperModal` for remapping a variable mid-extraction. Runs history panel shows recent runs per deal.
- Execute step surfaces nodes-executed count, distribution totals, validation pass count.

**Batch processing + multi-deal runs** (PR-13 ✅)
- `BatchRun` model links to N `ProcessingRun` rows via `batch_id`.
- `BatchService.create_batch()` accepts a list of `DealTapeInput` (pre-uploaded tapes). `execute_batch()` runs each deal sequentially: extract → execute → export. Failures in one deal don't halt the batch — `batch.deals_failed` increments, `error_summary` accumulates.
- Final batch status: `completed`, `completed_with_errors`, or `failed`.
- `BatchProcessingPage` lets users upload tapes for multiple deals; `BatchResultsPage` polls every 2s while running and shows per-deal cards (totals, validation pass/fail, fail-investigate link). "Export all CSVs (zip)" button downloads a zip of all generated CSVs. `BatchHistoryPage` lists recent batches.

**CI/CD**
- `azure-pipelines.yml` runs all six gates on every PR to `development`.

---

## 7. Current priorities

End-to-end processing is working. Remaining work, rough-ranked:

1. **Audit log query endpoint + `AuditLogPage` UI.** The `AuditLog` model and `audit_service.log_change()` exist and are written on deal/DAG/mapping changes, but there is no query endpoint and the frontend page is literally stubbed: `<p>Coming in PR-14</p>`. This is the most obvious unfinished piece. Scope: filter by entity type, entity id, user, date range; table view with diff expansion.
2. **Users management page.** Sidebar renders `<NavLink to="/users">` for admins, but the page component doesn't exist in the repo (confirm on inspection). Scope: admin-only CRUD — list users, add user (username + role), change role, deactivate. Backend needs a users router if it doesn't exist yet.
3. **Levenshtein "Did you mean?" suggestions** in `FormulaEngine.validate()`. Small — ~20 LOC using `difflib.get_close_matches` or a hand-rolled Levenshtein. Improves UX for typos like `class_a_balence` → suggests `class_a_balance`. Finishes the PR-7 spec.
4. **Deal status transitions** (draft → active → archived) with guards: can't process a draft deal, can't edit an archived deal. Model already has `status` column; guards are not enforced.
5. **UX polish** — global React error boundary, toast notifications on mutation success/error, loading skeletons instead of "Loading..." text, confirmation dialogs on destructive actions. All cross-cutting; do as one PR.
6. **PyInstaller bundling + build script.** Vite build → copy `dist/` into backend static dir → PyInstaller spec file → smoke test. Enables single-exe distribution.
7. **Expand test coverage.** No frontend test framework; backend coverage may have drifted below 80% on newer features (confirm with `pytest --cov`). Consider adding Vitest for frontend.

---

## 8. Open bugs / issues

- **`AuditLogPage.tsx` is stubbed** — shows "Coming in PR-14". Does not display any audit entries despite them being written.
- **`/users` sidebar link leads nowhere** for admins (assumption — confirm route definition in `App.tsx`).
- **Formula validator lacks typo suggestions** — returns "Unknown variable: X" with no "Did you mean?" hint.
- **`pyodbc` Windows install** requires Microsoft Visual C++ 14.0 Build Tools.
- **`fix_svcb.py` exists** — a one-off script to add missing variable mappings, edges, and waterfall order for the SVCB demo. Should only be run when the seed data drifts; not part of normal development.
- **Mixed architectural patterns** — newer features live in `app/{feature}/` folders (router/service/dao), older services in `app/services/` and older routers in `app/routers/`. Not broken, but don't let it spread further.
- **`ExportTemplate` + `ExportColumn` coexist** — the newer `ExportColumn` model is what the UI drives. Legacy export models are still referenced by `app/services/export_service.py`; `app/export/service.py` is the newer one that the `ExportConfigPage` uses. Pick the right one based on the call site.
- **No frontend test framework** — `tsc --noEmit` + `vite build` are the only enforced gates.

---

## 9. Decisions already made

- **Application factory pattern** (`create_app()`) on backend.
- **Sync SQLAlchemy**, not async — 30 users, 1–2s processing, async has no benefit.
- **Feature-based layered architecture** (router / service / dao) for new features. Shared `models/` and `schemas/`. Transaction management in `get_db` (auto-commit/rollback). DAOs and services never call `commit()`.
- **Windows username auth** — no login screen.
- **Three frontend auth booleans** — inline `{isModeler && ...}`, no wrapper components.
- **CSS Modules + global CSS custom properties dark theme** — Tailwind rejected.
- **DAG stored in normalized tables**, never JSON blobs. Every save creates `dag_version`. Soft deactivate, never delete. Full `audit_log` (writes only — UI pending).
- **Custom formula parser** (~250 LOC). 8 functions. Decimal everywhere. No `eval()`.
- **Five formula context sources**. `_prior` suffix auto-injected. `default_prior_value` handles first-month.
- **Prior month = prior calendar month's completed run**, not just most recent.
- **Two calculation streams never cross** — enforced at schema + save level.
- **144A/RegS** splits stored at tranche level; waterfall uses combined balance; split applied only at export time.
- **Oracle** read-only via `oracledb`.
- **Waterfall reconciliation** blocks export on failure — added after initial plan; retained.
- **6-step processing stepper** (added Waterfall between Execute and Export).
- **Export columns** are now configurable per deal via `ExportColumn` (replaces the rigid `ExportFieldMapping` approach, though legacy models remain).
- **Batch failures don't halt the batch** — deal-level isolation, `error_summary` accumulates.
- **Testing** — SQLite in-memory with dependency overrides. Split unit vs functional. ≥80% coverage.
- **CI/CD** — Azure DevOps, `development` integration branch, six mandatory gates.
- **Branch naming** — `feat/pr{N}-{short-description}` off `development`.
- **Managed file directories** — `data/uploads/{YYYY-MM}/{deal_id}/` and `data/exports/{deal_id}/{YYYY-MM}/`.

---

## 10. Coding conventions

### Backend Python
- Python 3.11+, `from __future__ import annotations` where needed.
- Full type hints; mypy strict. No `Any` without justification.
- SQLAlchemy 2.0 `Mapped[...]` / `mapped_column(...)` style.
- Pydantic v2 — `model_config = ConfigDict(from_attributes=True)` on response schemas reading from ORM.
- DAO: `db.add() + db.flush()`, never `commit()`.
- Service: composes DAOs, returns SQLAlchemy objects, never commits.
- Router: HTTP concerns only — 404 checks, `HTTPException`, role guards.
- `black` line length **100**, target `py311`.
- `pylint` ≥8.0 with `pylint-pydantic`. Disabled: `too-few-public-methods`, `missing-class-docstring`, `no-self-argument`, `import-error`.
- `Decimal` for all monetary values. Never `float`.
- No `print()` — use logging.
- No `eval()` / `exec()`.

### Frontend TypeScript / React
- TypeScript strict. No `any` — use `unknown` and narrow.
- Functional components + hooks.
- CSS Modules (`Foo.tsx` + `Foo.module.css`). No Tailwind, no styled-components, no CSS-in-JS.
- All colors via CSS variables (`var(--bg-card)`, `var(--accent-blue)`, `var(--text-primary)`, `var(--text-secondary)`, `var(--text-muted)`, `var(--accent-green)`, `var(--accent-red)`, `var(--accent-orange)`, `var(--accent-purple)`, `var(--border)`).
- API layer: one module per feature in `src/api/`; `api.get()` / `api.post()` wrapper in `client.ts`.
- React Query: `useQuery` / `useMutation` + query keys like `["deals", dealId, "mappings"]`. Invalidate on mutation success.
- Role gates are always inline: `{isModeler && <button>Edit</button>}`.
- No default exports except page components used in route tables.

### Git / PRs
- Branch off `development`, `feat/pr{N}-{short-description}`.
- One vertical slice per PR.
- `feat(scope): ...` or `refactor: ...` commit titles.
- All six CI gates green before merge.

---

## 11. What Claude Code should do first

1. **Read this file fully** before touching code.
2. **Confirm repo state** — inspect the tree with `git status`, `ls backend/app`, `ls frontend/src/pages`. The userMemories block may be stale.
3. **Establish a green baseline:**
   ```bash
   cd backend && ABSNEXUS_TESTING=1 ABSNEXUS_DATABASE_URL="sqlite:///:memory:" pytest -q
   cd ../frontend && npx tsc --noEmit && npm run build
   ```
   Fix any red before starting new work.
4. **Smoke-test the app** — `python backend/seed.py && python backend/run.py` + `cd frontend && npm run dev`. Open `http://localhost:5173`, log in as `root`/`jane.chen`/`sam.analyst` (depending on what Windows user you spoof via env var), and click through: deal list → SVCB 2022-7 → processing → run through all six steps. If any step fails, prioritize fixing it over new features.
5. **Confirm the next task with the user** before starting — see Section 13. Default next task = audit log query + UI.
6. **Follow the layered architecture strictly** for new features. Router / service / dao per feature. No `commit()` outside `get_db`.
7. **Sequence for every new feature:** model → Alembic migration → DAO → service → router → schemas → tests → frontend. All six CI gates green locally before the first push.

---

## 12. Conversation summary from previous Claude chats

The project evolved across three distinct conversations:

1. **Planning conversation — "MVP implementation plan with pull request artifacts"** (longest). Started from a `sample_skeleton` markdown. The user iterated a 16-PR implementation plan through six versions, with major pivots: rejected Tailwind → CSS Modules; simplified auth from a permission matrix to three booleans; normalized DAG storage; DAG versioning + soft deactivation; tranche balance management with Oracle + 144A/RegS splits; 5-source formula context with `_prior` auto-injection; feature-based layered backend with auto-commit `get_db`; `variable_alias` table for per-deal display overrides. Detailed per-PR guides were generated with commit histories, ASCII mockups, and consistent formatting.
2. **Build conversation — "ABSNexus structured finance DAG builder project"**. Delivered a runnable repo through PR-6 as a zip (67 tests passing, 121KB). DAG builder fixes were uploaded and re-applied.
3. **Legacy — "ABS Payment Processing Architecture"** (Aug 2025, superseded). Proposed three-layer Variables / ExcelLocations / VariableMappings — rejected in favor of the simpler current design.

**After those initial conversations, the codebase kept advancing.** The repo as of this handoff contains working implementations of everything through PR-13 (formula engine, tape extraction, DAG execution, validation/lineage, CSV export, monthly processing UI, batch processing, deal cloning), plus bonus features not in the original plan (waterfall reconciliation gate, configurable export columns with presets, inline cell remapping mid-processing, 6-step processing stepper instead of 5). Principles held throughout: **simplicity over abstraction**, **transparency over magic**, **vertical slices per PR**, **strict code quality gates**.

---

## 13. Exact next task

**Implement the Audit Log query endpoint + `AuditLogPage` UI.**

Branch: `feat/pr14-audit-log-ui` off `development`.

Context: The `AuditLog` model exists (`app/models/audit_log.py`) and `audit_service.log_change()` is called on every create/update/delete across deals, DAG, mappings, tranches, and variable aliases. Rows are accumulating in the database but there is no way to view them — `AuditLogPage.tsx` currently renders only `<p>Coming in PR-14</p>`.

Deliverables:

**Backend:**
- `backend/app/audit/` feature folder with `router.py`, `service.py`, `dao.py`, `__init__.py`.
- `AuditDAO.list_filtered(...)` — paged query supporting filters: `entity_type`, `entity_id`, `user_id`, `action`, `created_at` range.
- `AuditService.list_recent(filters, page, page_size)` — joins with `User` to resolve display names.
- `GET /api/audit/` — returns `{ items: [...], total, page, page_size }`.
- `GET /api/audit/entity/{entity_type}/{entity_id}` — convenience endpoint for drill-in from other pages (e.g., "Show history" button on a deal).
- Router gated: admins and analytics can view; analysts are denied (assumption — confirm with user).
- Pydantic v2 schemas: `AuditLogResponse`, `AuditLogListResponse`, `AuditLogFilters`.
- Register the audit router in `app/__init__.py`.

**Frontend:**
- `src/api/audit.ts` — `fetchAuditLog(filters)`, `fetchEntityHistory(entityType, entityId)`.
- Replace `AuditLogPage.tsx` stub with:
  - Filter bar: entity type dropdown (all, deal, dag_node, variable_mapping, dag_version, tranche, variable_alias), user dropdown, action dropdown (created, updated, deleted, deactivated, reverted, cloned), date range pickers.
  - Table: timestamp, user (display name), entity (type + id + name lookup where feasible), action (badge), description, expandable "Show diff" for the `changes` JSON.
  - Paging controls (page size 50, default).
- Optional stretch: "Show history" button on `DealDetailPage` that links to `AuditLogPage` pre-filtered to `entity_type=deal&entity_id={id}`.

**Tests:**
- `tests/unit/test_audit_service.py` — filtering (by entity, by user, by date range), paging, joins.
- `tests/functional/test_audit_routes.py` — role gates, pagination response shape, date range filter, entity drill-in endpoint.

**Acceptance:**
- Navigate to `/audit` as `jane.chen` → see recent entries from seeded activity.
- Filter by entity type = `deal` → only deal entries show.
- Click "Show diff" on an `updated` entry → JSON of `{ field: { old, new } }` expands inline.
- `sam.analyst` either sees a read-only view or is denied (final call from user).
- All six CI gates green.

---

## 14. Files likely relevant to the next task

Create:
- `backend/app/audit/__init__.py`
- `backend/app/audit/dao.py`
- `backend/app/audit/service.py`
- `backend/app/audit/router.py`
- `backend/app/schemas/audit.py`
- `backend/tests/unit/test_audit_service.py`
- `backend/tests/functional/test_audit_routes.py`
- `frontend/src/api/audit.ts`

Modify:
- `backend/app/__init__.py` — register audit router.
- `frontend/src/pages/AuditLogPage.tsx` — replace stub.
- `frontend/src/App.tsx` — route may already exist; confirm.

Reference (read-only):
- `backend/app/models/audit_log.py` — schema.
- `backend/app/services/audit_service.py` — how entries are written. Keep writes unchanged; this PR only reads.
- `backend/app/dependencies.py` — `require_role()` usage.
- `frontend/src/auth/useAuth.ts` — for role gating.
- `backend/tests/conftest.py` — fixtures to reuse (test user, TestClient).

---

## 15. Notes for safe edits

- **Never call `commit()` in a DAO or service.** Transaction ownership lives in `get_db`.
- **Never introduce async code.** Sync SQLAlchemy throughout.
- **Never use `eval()` or `exec()`.** The formula engine exists to avoid this.
- **Never use `float` for money.** `Decimal` always.
- **Never modify `alembic/versions/*` files after they've been applied.** New migration for new changes.
- **Never delete `dag_node`, `dag_version`, or `processing_run` rows.** Soft-deactivate / append-only.
- **Never overwrite a `ProcessingRun` with `status='completed'`.** Re-processing creates a new run.
- **Never bypass `require_role()` on write endpoints.**
- **Never add Tailwind, styled-components, emotion, or CSS-in-JS.** CSS Modules + CSS variables only.
- **Never introduce a permission matrix or `RequireRole` / `RoleGuard` wrapper.** Keep it inline.
- **Never use a variable name other than canonical in formulas.** Aliases are display-only.
- **Never write 144A/RegS prorate logic into waterfall calculations.** Prorate is export-time only.
- **Never compute "prior month" as "most recent run".** It's the prior calendar month's `status='completed'` run. Use `PriorMonthService`.
- **Never remove the waterfall reconciliation export gate** without user sign-off. It catches real payment errors.
- **Don't refactor the mixed `app/routers/` + `app/services/` (legacy) vs `app/{feature}/` (newer) patterns mid-feature.** Match whatever pattern the code you're editing uses.
- **If `AuditLogPage` or any other stubbed page already has a partial implementation in the repo beyond what this doc describes,** the repo wins. Inspect before rewriting from scratch.
- **If a PR guide or this MEMORY.md disagrees with the actual code**, the code is ground truth unless the user says otherwise.
- **Never leave a branch in a state that fails any of the six CI gates.**