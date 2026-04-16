"""Fix SVCB deal 3 part 2: tranche balances + validation formula.

Issues:
1. Tranche balances only exist for 2025-06 but run uses 2026-04 →
   class_d/e/f_balance resolve to 0 → interest calculations are 0.

2. val_dist_check formula only sums distribution nodes but omits trustee_fee
   and backup_svc_fee (which are deducted but have no dist node) → sum is
   always short by 3,250.

Run:
    cd backend
    python fix_svcb_2.py
"""
from decimal import Decimal
from app.core.database import SessionLocal
from app.models.dag import DagNode, DagVersion, DagEdge
from app.models.tranche import DealTranche, TrancheBalance
from app.tranches.dao import TrancheDAO

db = SessionLocal()

DEAL_ID = 3

# ── 1. Copy tranche balances from 2025-06 to 2026-04 ─────────────────────────
print("── Adding 2026-04 tranche balances ──")
dao = TrancheDAO(db)
tranches = dao.list_for_deal(DEAL_ID)

for t in tranches:
    existing_2026 = dao.get_balance(t.id, "2026-04")
    if existing_2026:
        print(f"  = tranche {t.id} ({t.class_label}) already has 2026-04 balance: {existing_2026.balance}")
        continue

    bal_2025 = dao.get_balance(t.id, "2025-06")
    if bal_2025:
        new_bal = dao.set_balance(t.id, "2026-04", bal_2025.balance, source="seed_copy")
        print(f"  + tranche {t.id} ({t.class_label}) 2026-04 balance = {new_bal.balance} (copied from 2025-06)")
    else:
        # No prior balance — set to 0
        dao.set_balance(t.id, "2026-04", Decimal("0"), source="seed_default")
        print(f"  + tranche {t.id} ({t.class_label}) 2026-04 balance = 0 (no 2025-06 data)")

db.flush()

# ── 2. Fix val_dist_check formula to include all fees ─────────────────────────
print("\n── Fixing val_dist_check formula ──")
version = (
    db.query(DagVersion)
    .filter(DagVersion.deal_id == DEAL_ID, DagVersion.is_current == True)
    .first()
)

nodes = db.query(DagNode).filter(DagNode.dag_version_id == version.id).all()
key_to_id = {n.key: n.id for n in nodes}

val_node = next((n for n in nodes if n.key == "val_dist_check"), None)
if val_node:
    old_formula = val_node.formula
    new_formula = "ABS(dist_svc_fee + dist_d_int + dist_e_int + dist_f_int + dist_prin + trustee_fee_tape + backup_svc_fee_tape)"
    val_node.formula = new_formula
    print(f"  old: {old_formula}")
    print(f"  new: {new_formula}")
    db.flush()

    # Add edges from trustee_fee_tape and backup_svc_fee_tape → val_dist_check
    for src_key in ("trustee_fee_tape", "backup_svc_fee_tape"):
        src_id = key_to_id.get(src_key)
        tgt_id = val_node.id
        if not src_id:
            print(f"  ! {src_key} node not found")
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
            print(f"  = edge {src_key} → val_dist_check already exists")
        else:
            db.add(DagEdge(
                dag_version_id=version.id,
                source_node_id=src_id,
                target_node_id=tgt_id,
            ))
            print(f"  + edge {src_key} → val_dist_check")
    db.flush()
else:
    print("  ! val_dist_check node not found")

db.commit()
print("\nDone. Re-extract and re-execute to see corrected results.")
db.close()
