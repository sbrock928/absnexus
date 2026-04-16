"""Fix SVCB deal 3: add missing variable mappings, edges, and waterfall order.

Issues:
1. DAG input nodes (total_available_funds, svc_fee_tape, trustee_fee_tape,
   backup_svc_fee_tape) have no variable mappings → tape extraction never
   produces them → executor defaults to 0 → waterfall can't find starting var.

2. Validation nodes (val_dist_check) reference distribution node keys
   (dist_svc_fee, dist_d_int, etc.) but no edges link distributions →
   validations, so topo-sort may place validations first → "Unknown variable".

3. Distribution nodes have no waterfall_order → waterfall trace has no ordering.

Run:
    cd backend
    python fix_svcb.py
"""
from app.core.database import SessionLocal
from app.models.dag import DagNode, DagVersion, DagEdge
from app.models.variable import VariableDefinition
from app.models.variable_mapping import VariableMapping

db = SessionLocal()

DEAL_ID = 3

# ── 1. Add missing variable mappings ─────────────────────────────────────────
# The DAG input node keys must match extracted variable names.
# These system variables exist but aren't mapped for deal 3.
NEW_MAPPINGS = [
    # (variable_name,     sheet,     col, row, tape_label)
    ("total_available_funds", "Sheet 1", "K", 81, "Total Available Funds"),
    ("svc_fee_tape",          "Sheet 1", "J", 84, "Servicing Fee (tape)"),
    ("trustee_fee_tape",      "Sheet 1", "J", 86, "Trustee Fee (tape)"),
    ("backup_svc_fee_tape",   "Sheet 1", "J", 85, "Backup Svc Fee (tape)"),
]

print("── Adding missing variable mappings ──")
for var_name, sheet, col, row, label in NEW_MAPPINGS:
    var = (
        db.query(VariableDefinition)
        .filter(VariableDefinition.name == var_name, VariableDefinition.scope == "system")
        .first()
    )
    if not var:
        print(f"  ! Variable {var_name} not found, skipping")
        continue

    existing = (
        db.query(VariableMapping)
        .filter(
            VariableMapping.deal_id == DEAL_ID,
            VariableMapping.variable_id == var.id,
        )
        .first()
    )
    if existing:
        print(f"  = {var_name} (id={var.id}) already mapped")
        continue

    db.add(VariableMapping(
        deal_id=DEAL_ID,
        variable_id=var.id,
        sheet_name=sheet,
        column_letter=col,
        row_number=row,
        tape_label=label,
    ))
    print(f"  + {var_name} (id={var.id}) → {sheet} {col}{row}")

db.flush()

# ── 2. Add edges from distribution nodes → validation nodes ──────────────────
# val_dist_check references: dist_svc_fee, dist_d_int, dist_e_int,
#   dist_f_int, dist_prin, total_available_funds
# val_oc_check references: end_pool_bal, class_d_balance, class_e_balance,
#   class_f_balance (tranche context + extracted — no DAG node dependencies)

version = (
    db.query(DagVersion)
    .filter(DagVersion.deal_id == DEAL_ID, DagVersion.is_current == True)
    .first()
)

if not version:
    print("  ! No current DAG version found")
else:
    nodes = db.query(DagNode).filter(DagNode.dag_version_id == version.id).all()
    key_to_id = {n.key: n.id for n in nodes}

    # Edges needed: each dist node → val_dist_check
    NEEDED_EDGES = [
        ("dist_svc_fee", "val_dist_check"),
        ("dist_d_int", "val_dist_check"),
        ("dist_e_int", "val_dist_check"),
        ("dist_f_int", "val_dist_check"),
        ("dist_prin", "val_dist_check"),
        ("total_available_funds", "val_dist_check"),
    ]

    print("\n── Adding missing DAG edges ──")
    for src_key, tgt_key in NEEDED_EDGES:
        src_id = key_to_id.get(src_key)
        tgt_id = key_to_id.get(tgt_key)
        if not src_id or not tgt_id:
            print(f"  ! {src_key} → {tgt_key}: node not found")
            continue

        existing = (
            db.query(DagEdge)
            .filter(
                DagEdge.dag_version_id == version.id,
                DagEdge.source_node_id == src_id,
                DagEdge.target_node_id == tgt_id,
            )
            .first()
        )
        if existing:
            print(f"  = {src_key} → {tgt_key} (already exists)")
            continue

        db.add(DagEdge(
            dag_version_id=version.id,
            source_node_id=src_id,
            target_node_id=tgt_id,
        ))
        print(f"  + {src_key} → {tgt_key}")

    db.flush()

    # ── 3. Set waterfall_order on distribution nodes ──────────────────────────
    WATERFALL_ORDER = {
        "dist_svc_fee": 1,
        "dist_d_int": 2,
        "dist_e_int": 3,
        "dist_f_int": 4,
        "dist_prin": 5,
    }

    print("\n── Setting waterfall_order ──")
    for node in nodes:
        wf = WATERFALL_ORDER.get(node.key)
        if wf is not None and node.waterfall_order != wf:
            node.waterfall_order = wf
            print(f"  + {node.key} → waterfall_order={wf}")
        elif wf is not None:
            print(f"  = {node.key} already has waterfall_order={wf}")

    db.flush()

db.commit()
print("\nDone. Re-extract (step 3) and re-execute (step 4) to pick up changes.")
db.close()
