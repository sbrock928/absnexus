"""Seed script — populates database with demo data for local development.

Creates:
  - 3 users (root as admin, jane.chen as analytics, sam.analyst as analyst)
  - 3 servicers (Wells Fargo, Nationstar, Servicer B)
  - System-level variables (canonical names)
  - 1 fully-configured demo deal: SVCB 2022-7
      - 27 variable mappings across 5 sheets
      - 6 tranches (Class A split 144A/RegS, Classes B/C/D)
      - 17 DAG nodes + 20 edges (distribution stream)
      - 2 validation nodes (validation stream)
      - 1 saved DAG version
      - 7 export columns (System A layout)

Run from repo root:
    cd backend
    python -m app.seed

Safe to re-run — skips anything that already exists by name/key.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.dag.service import DagService
from app.export.service import ExportColumnService
from app.models.dag import DagEdge, DagNode
from app.models.deal import Deal
from app.models.export import ExportColumn
from app.models.variable_mapping import VariableMapping
from app.models.servicer import Servicer
from app.models.tranche import DealTranche, TrancheBalance
from app.models.user import User
from app.models.variable import VariableDefinition
from app.schemas.dag import DagNodeCreate, DagEdgeCreate
from app.tranches.service import TrancheService


# ══════════════════════════════════════════════════════════════════════════════
# Users
# ══════════════════════════════════════════════════════════════════════════════

USERS = [
    {"username": "root", "display_name": "Root Admin", "role": "admin"},
    {"username": "jane.chen", "display_name": "Jane Chen", "role": "analytics"},
    {"username": "sam.analyst", "display_name": "Sam Patel", "role": "analyst"},
]


def seed_users(db: Session) -> dict[str, User]:
    """Insert demo users if they don't exist. Returns dict by username."""
    print("\n── Users ──")
    result: dict[str, User] = {}
    for u in USERS:
        existing = db.query(User).filter(User.username == u["username"]).first()
        if existing:
            print(f"  = {u['username']} (already exists)")
            result[u["username"]] = existing
        else:
            user = User(**u)
            db.add(user)
            db.flush()
            print(f"  + {u['username']} ({u['role']})")
            result[u["username"]] = user
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Servicers
# ══════════════════════════════════════════════════════════════════════════════

SERVICERS = [
    {"name": "Wells Fargo", "short_code": "WFC"},
    {"name": "Nationstar", "short_code": "NSTR"},
    {"name": "Servicer B", "short_code": "SVCB"},
]


def seed_servicers(db: Session) -> dict[str, Servicer]:
    print("\n── Servicers ──")
    result: dict[str, Servicer] = {}
    for s in SERVICERS:
        existing = db.query(Servicer).filter(Servicer.name == s["name"]).first()
        if existing:
            print(f"  = {s['name']} (already exists)")
            result[s["name"]] = existing
        else:
            svc = Servicer(**s)
            db.add(svc)
            db.flush()
            print(f"  + {s['name']}")
            result[s["name"]] = svc
    return result


# ══════════════════════════════════════════════════════════════════════════════
# System-level variables (canonical names used across all deals)
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_VARIABLES = [
    # Collections
    ("total_collections", "Total Monthly Collections", "decimal", "Sum of all cash collected"),
    ("prin_collections", "Principal Collections", "decimal", "Principal portion of collections"),
    ("int_collections", "Interest Collections", "decimal", "Interest portion of collections"),
    ("sched_principal", "Scheduled Principal", "decimal", "Scheduled principal payments"),
    ("unsched_principal", "Unscheduled Principal", "decimal", "Prepayments + curtailments"),
    ("liquidation_proceeds", "Liquidation Proceeds", "decimal", "Net from liquidations"),
    ("total_available_funds", "Total Available Funds", "decimal", "Total funds to distribute"),

    # Fees (tape)
    ("svc_fee_tape", "Servicing Fee (tape)", "decimal", "Servicing fee as reported on tape"),
    ("trustee_fee_tape", "Trustee Fee (tape)", "decimal", "Trustee fee as reported on tape"),
    ("backup_svc_fee_tape", "Backup Svc Fee (tape)", "decimal", "Backup servicer fee from tape"),

    # Rates
    ("svc_fee_rate", "Servicing Fee Rate", "percentage", "Annual servicing fee rate"),
    ("trustee_fee_rate", "Trustee Fee Rate", "percentage", "Annual trustee fee rate"),

    # Pool
    ("cur_pool_bal", "Current Pool Balance", "decimal", "End-of-period pool balance"),
    ("end_pool_bal", "End Pool Balance", "decimal", "End pool balance after distribution"),

    # OC / triggers
    ("reported_oc", "Reported OC", "decimal", "Overcollateralization as servicer reports"),
    ("oc_floor", "OC Floor", "decimal", "OC floor threshold"),
    ("target_oc_pct", "Target OC %", "percentage", "Target overcollateralization %"),

    # Shortfalls
    ("int_shortfall_prior", "Int Shortfall Prior", "decimal", "Prior period interest shortfall"),

    # Bond details (note rates + balances reported on tape)
    ("a_note_rate", "Class A Note Rate", "percentage", "Class A coupon"),
    ("b_note_rate", "Class B Note Rate", "percentage", "Class B coupon"),
    ("c_note_rate", "Class C Note Rate", "percentage", "Class C coupon"),
    ("d_note_rate", "Class D Note Rate", "percentage", "Class D coupon"),
    ("e_note_rate", "Class E Note Rate", "percentage", "Class E coupon"),
    ("f_note_rate", "Class F Note Rate", "percentage", "Class F coupon"),

    # Bond balances reported on tape
    ("a_note_balance", "Class A Note Balance", "decimal", "Class A outstanding balance"),
    ("b_note_balance", "Class B Note Balance", "decimal", "Class B outstanding balance"),
    ("c_note_balance", "Class C Note Balance", "decimal", "Class C outstanding balance"),
    ("d_note_balance", "Class D Note Balance", "decimal", "Class D outstanding balance"),
    ("e_note_balance", "Class E Note Balance", "decimal", "Class E outstanding balance"),
    ("f_note_balance", "Class F Note Balance", "decimal", "Class F outstanding balance"),
]


def seed_system_variables(db: Session) -> dict[str, VariableDefinition]:
    print("\n── System variables ──")
    result: dict[str, VariableDefinition] = {}
    for name, display, dtype, desc in SYSTEM_VARIABLES:
        existing = (
            db.query(VariableDefinition)
            .filter(
                VariableDefinition.name == name,
                VariableDefinition.scope == "system",
            )
            .first()
        )
        if existing:
            result[name] = existing
            continue
        var = VariableDefinition(
            name=name,
            display_name=display,
            data_type=dtype,
            scope="system",
            description=desc,
        )
        db.add(var)
        db.flush()
        result[name] = var
    print(f"  {len(result)} variables registered")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Demo deal: SVCB 2022-7
# ══════════════════════════════════════════════════════════════════════════════

SVCB_MAPPINGS = [
    # (variable_name, sheet, col, row, tape_label)
    ("total_available_funds", "Distribution Summary", "C", 14, "Total Available Funds"),
    ("total_collections", "Distribution Summary", "C", 15, "Total Collections"),
    ("svc_fee_tape", "Distribution Summary", "C", 18, "Servicing Fee"),
    ("trustee_fee_tape", "Distribution Summary", "C", 19, "Trustee Fee"),
    ("backup_svc_fee_tape", "Distribution Summary", "C", 20, "Backup Svc Fee"),
    ("prin_collections", "Distribution Summary", "C", 22, "Principal Collections"),
    ("int_collections", "Distribution Summary", "C", 23, "Interest Collections"),
    ("sched_principal", "Distribution Summary", "C", 24, "Scheduled Principal"),
    ("unsched_principal", "Distribution Summary", "C", 25, "Unscheduled Principal"),
    ("liquidation_proceeds", "Distribution Summary", "C", 26, "Liquidation Proceeds"),
    ("int_shortfall_prior", "Distribution Summary", "C", 30, "Prior Int Shortfall"),

    ("svc_fee_rate", "Fee Schedule", "C", 3, "Servicing Fee Rate"),
    ("trustee_fee_rate", "Fee Schedule", "C", 5, "Trustee Fee Rate"),

    ("cur_pool_bal", "Pool Statistics", "D", 8, "Current Pool Balance"),
    ("end_pool_bal", "Pool Statistics", "D", 10, "End Pool Balance"),

    ("a_note_balance", "Bond Details", "F", 3, "Class A Balance"),
    ("a_note_rate", "Bond Details", "F", 4, "Class A Rate"),
    ("b_note_balance", "Bond Details", "F", 5, "Class B Balance"),
    ("b_note_rate", "Bond Details", "F", 6, "Class B Rate"),
    ("c_note_balance", "Bond Details", "F", 7, "Class C Balance"),
    ("c_note_rate", "Bond Details", "F", 8, "Class C Rate"),
    ("d_note_balance", "Bond Details", "F", 9, "Class D Balance"),
    ("d_note_rate", "Bond Details", "F", 10, "Class D Rate"),
    ("e_note_balance", "Bond Details", "F", 11, "Class E Balance"),
    ("e_note_rate", "Bond Details", "F", 12, "Class E Rate"),
    ("f_note_balance", "Bond Details", "F", 13, "Class F Balance"),
    ("f_note_rate", "Bond Details", "F", 14, "Class F Rate"),

    ("reported_oc", "Triggers", "D", 22, "Reported OC"),
]


SVCB_TRANCHES = [
    # (class_label, cusip, regulation_type, note_rate, original_balance)
    ("A", "SVCB22A144", "144A", Decimal("0.0412"), Decimal("120000000")),
    ("A", "SVCB22AREG", "RegS", Decimal("0.0412"), Decimal("31710000")),
    ("B", "SVCB22B144", None, Decimal("0.0455"), Decimal("50000000")),
    ("C", "SVCB22C144", None, Decimal("0.0486"), Decimal("25000000")),
    ("D", "SVCB22D144", None, Decimal("0.0520"), Decimal("15000000")),
    ("E", "SVCB22E144", None, Decimal("0.0575"), Decimal("10000000")),
]


SVCB_BALANCES = {
    # class_label → (144a balance April, RegS balance April) or (total, None)
    "A": (Decimal("80000000"), Decimal("20000000")),
    "B": (Decimal("45000000"), None),
    "C": (Decimal("22000000"), None),
    "D": (Decimal("13000000"), None),
    "E": (Decimal("9000000"), None),
}


# DAG nodes — matches your screenshot (17 distribution + 2 validation = 19 total)
SVCB_DIST_NODES = [
    # (node_key, name, type, formula, payment_type, position_x, position_y)
    # Row 1: input nodes (tape values)
    ("total_available_funds_in", "Total Available Funds", "input", None, None, 100, 50),
    ("svc_fee_tape_in", "Servicing Fee (tape)", "input", None, None, 300, 50),
    ("trustee_fee_tape_in", "Trustee Fee (tape)", "input", None, None, 500, 50),
    ("backup_svc_fee_tape_in", "Backup Svc Fee (tape)", "input", None, None, 700, 50),

    # Row 2: fee aggregation
    (
        "total_fees",
        "Total Fees",
        "calculation",
        "svc_fee_tape + trustee_fee_tape + backup_svc_fee_tape",
        None, 400, 180,
    ),

    # Row 3: net distributable
    (
        "net_available",
        "Net Available for Distribution",
        "calculation",
        "total_available_funds - total_fees",
        None, 400, 280,
    ),

    # Row 4: interest calculations per class (D, E, F only in distribution stream)
    (
        "class_d_int_calc",
        "Class D Interest (calc)",
        "calculation",
        "class_d_balance * class_d_note_rate / 12",
        None, 150, 400,
    ),
    (
        "class_e_int_calc",
        "Class E Interest (calc)",
        "calculation",
        "class_e_balance * class_e_note_rate / 12",
        None, 400, 400,
    ),
    (
        "class_f_int_calc",
        "Class F Interest (calc)",
        "calculation",
        "class_f_balance * class_f_note_rate / 12",
        None, 650, 400,
    ),

    # Row 5: after interest
    (
        "remaining_after_int",
        "Remaining After Interest",
        "calculation",
        "MAX(net_available - class_d_int_calc - class_e_int_calc - class_f_int_calc, 0)",
        None, 400, 520,
    ),

    # Row 6: distribution nodes (export)
    ("svc_fee_pmt", "Servicing Fee Pmt", "distribution", "svc_fee_tape", "SVC_FEE", 50, 640),
    (
        "class_d_int_pmt",
        "Class D Interest Pmt",
        "distribution",
        "MIN(net_available, class_d_int_calc)",
        "INT_PMT_D", 250, 640,
    ),
    (
        "class_e_int_pmt",
        "Class E Interest Pmt",
        "distribution",
        "MIN(MAX(net_available - class_d_int_calc, 0), class_e_int_calc)",
        "INT_PMT_E", 450, 640,
    ),
    (
        "class_f_int_pmt",
        "Class F Interest Pmt",
        "distribution",
        "MIN(MAX(net_available - class_d_int_calc - class_e_int_calc, 0), class_f_int_calc)",
        "INT_PMT_F", 650, 640,
    ),
    (
        "principal_dist",
        "Principal Distribution",
        "distribution",
        "remaining_after_int",
        "PRIN_PMT_D", 400, 760,
    ),
]


SVCB_VALIDATION_NODES = [
    (
        "oc_amount_check",
        "OC Amount Check",
        "validation",
        "ABS(end_pool_bal - class_d_balance - class_e_balance - class_f_balance)",
        "reported_oc",
        Decimal("0.01"),
        100, 100,
    ),
    (
        "total_distribution_check",
        "Total Distribution Check",
        "validation",
        "ABS(dist_svc_fee + dist_d_int + dist_e_int + dist_f_int + dist_prin)",
        "total_available_funds",
        Decimal("0.01"),
        400, 100,
    ),
]


SVCB_EDGES = [
    # Flow: inputs → total_fees
    ("svc_fee_tape_in", "total_fees"),
    ("trustee_fee_tape_in", "total_fees"),
    ("backup_svc_fee_tape_in", "total_fees"),

    # Flow: total_available + total_fees → net_available
    ("total_available_funds_in", "net_available"),
    ("total_fees", "net_available"),

    # Flow: net_available + interest calcs
    ("net_available", "class_d_int_pmt"),
    ("net_available", "class_e_int_pmt"),
    ("net_available", "class_f_int_pmt"),

    # Flow: interest calcs → interest payments
    ("class_d_int_calc", "class_d_int_pmt"),
    ("class_e_int_calc", "class_e_int_pmt"),
    ("class_f_int_calc", "class_f_int_pmt"),

    # Flow: net_available → remaining
    ("net_available", "remaining_after_int"),
    ("class_d_int_calc", "remaining_after_int"),
    ("class_e_int_calc", "remaining_after_int"),
    ("class_f_int_calc", "remaining_after_int"),

    # Flow: remaining → principal
    ("remaining_after_int", "principal_dist"),

    # Flow: servicing fee
    ("svc_fee_tape_in", "svc_fee_pmt"),

    # Class E interest needs D interest + net
    ("class_d_int_calc", "class_e_int_pmt"),

    # Class F interest needs D + E interest + net
    ("class_d_int_calc", "class_f_int_pmt"),
    ("class_e_int_calc", "class_f_int_pmt"),

    # Class E remaining depends on D interest
    ("class_e_int_calc", "remaining_after_int"),
]


SVCB_EXPORT_COLUMNS = [
    # (header_label, value_type, node_key or literal or meta, format)
    ("DEAL_ID", "deal_meta", "deal_id", "text"),
    ("PAYMENT_DATE", "run_meta", "payment_date", "text"),
    ("PAYMENT_TYPE", "literal", "DISTRIBUTION", "text"),
    ("FIELD_CODE", "distribution_node", None, "text"),  # special — uses export_field
    ("AMOUNT", "distribution_node", None, "decimal"),
    ("RUN_ID", "run_meta", "run_code", "text"),
]


def seed_svcb_deal(
    db: Session,
    users: dict[str, User],
    servicers: dict[str, Servicer],
    variables: dict[str, VariableDefinition],
) -> Deal:
    """Create the SVCB 2022-7 demo deal with full configuration."""
    print("\n── SVCB 2022-7 demo deal ──")

    existing = db.query(Deal).filter(Deal.name == "SVCB 2022-7").first()
    if existing:
        print("  = Deal already exists, skipping")
        return existing

    deal = Deal(
        name="SVCB 2022-7",
        servicer_id=servicers["Servicer B"].id,
        product_type="ABS Auto",
        status="active",
        created_by=users["jane.chen"].id,
    )
    db.add(deal)
    db.flush()
    print(f"  + Deal id={deal.id}")

    # Variable mappings
    for var_name, sheet, col, row, label in SVCB_MAPPINGS:
        var = variables.get(var_name)
        if var is None:
            print(f"    ! Variable not found: {var_name}")
            continue
        db.add(VariableMapping(
            deal_id=deal.id,
            variable_id=var.id,
            sheet_name=sheet,
            column_letter=col,
            row_number=row,
            tape_label=label,
        ))
    db.flush()
    print(f"  + {len(SVCB_MAPPINGS)} variable mappings")

    # Tranches
    tranches_by_class: dict[str, list[DealTranche]] = {}
    for class_label, cusip, reg_type, rate, orig_bal in SVCB_TRANCHES:
        t = DealTranche(
            deal_id=deal.id,
            class_label=class_label,
            cusip=cusip,
            regulation_type=reg_type,
            note_rate=rate,
            original_balance=orig_bal,
            maturity_date=date(2035, 1, 15),
        )
        db.add(t)
        db.flush()
        tranches_by_class.setdefault(class_label, []).append(t)

    # Tranche balances for current period (2026-04)
    for class_label, (bal_144a_or_total, bal_regs) in SVCB_BALANCES.items():
        class_tranches = tranches_by_class.get(class_label, [])
        if bal_regs is None:
            # No split — single tranche
            if class_tranches:
                db.add(TrancheBalance(
                    tranche_id=class_tranches[0].id,
                    report_period="2026-04",
                    current_balance=bal_144a_or_total,
                    source="manual",
                    entered_by=users["jane.chen"].id,
                ))
        else:
            # Split into 144A and RegS
            for t in class_tranches:
                amount = bal_144a_or_total if t.regulation_type == "144A" else bal_regs
                db.add(TrancheBalance(
                    tranche_id=t.id,
                    report_period="2026-04",
                    current_balance=amount,
                    source="manual",
                    entered_by=users["jane.chen"].id,
                ))
    db.flush()
    print(f"  + {len(SVCB_TRANCHES)} tranches with balances")

    # DAG — build node + edge schemas, then save as version
    dag_svc = DagService(db)

    node_creates: list[DagNodeCreate] = []
    for key, name, ntype, formula, payment_type, px, py in SVCB_DIST_NODES:
        node_creates.append(DagNodeCreate(
            key=key, name=name, node_type=ntype, stream="distribution",
            formula=formula, payment_type=payment_type,
            position_x=px, position_y=py,
        ))

    for key, name, ntype, formula, comp_var, tolerance, px, py in SVCB_VALIDATION_NODES:
        node_creates.append(DagNodeCreate(
            key=key, name=name, node_type=ntype, stream="validation",
            formula=formula, comparison_variable=comp_var, tolerance=tolerance,
            position_x=px, position_y=py,
        ))

    edge_creates: list[DagEdgeCreate] = [
        DagEdgeCreate(source_key=src, target_key=tgt) for src, tgt in SVCB_EDGES
    ]

    version = dag_svc.save(
        deal_id=deal.id,
        nodes=node_creates,
        edges=edge_creates,
        created_by="root",
        description="Initial waterfall setup from seed",
    )
    print(f"  + {len(node_creates)} nodes + {len(edge_creates)} edges saved as v{version.version_number}")

    # Build node key->id lookup from the saved version for export column reference
    saved_nodes = dag_svc.load(deal.id)
    node_lookup: dict[str, DagNode] = {}
    if saved_nodes:
        for n in saved_nodes["nodes"]:
            node_lookup[n.key] = n

    # Export columns — System A layout
    export_svc = ExportColumnService(db)

    # Map distribution nodes to separate export rows
    dist_nodes_with_export = [
        ("svc_fee_pmt", "SVC_FEE"),
        ("class_d_int_pmt", "INT_PMT_D"),
        ("class_e_int_pmt", "INT_PMT_E"),
        ("class_f_int_pmt", "INT_PMT_F"),
        ("principal_dist", "PRIN_PMT_D"),
    ]

    position = 1
    # Static columns
    export_svc.create_column(
        deal.id, "DEAL_ID", "deal_meta", meta_field="deal_id", position=position,
    )
    position += 1
    export_svc.create_column(
        deal.id, "PAYMENT_DATE", "run_meta", meta_field="payment_date", position=position,
    )
    position += 1
    export_svc.create_column(
        deal.id, "PAYMENT_TYPE", "literal", literal_value="DISTRIBUTION", position=position,
    )
    position += 1
    # One column per distribution node — FIELD_CODE is the export field code
    # and AMOUNT is the calculated result. Since our export model produces one
    # row per distribution node automatically, we just need these two generic
    # columns once:
    export_svc.create_column(
        deal.id, "FIELD_CODE", "literal", literal_value="", position=position,
    )
    position += 1
    export_svc.create_column(
        deal.id, "AMOUNT",
        "distribution_node",
        node_id=node_lookup["svc_fee_pmt"].id,  # first dist node as anchor
        format_type="decimal",
        decimal_places=2,
        position=position,
    )
    position += 1
    export_svc.create_column(
        deal.id, "RUN_ID", "run_meta", meta_field="run_code", position=position,
    )
    db.flush()
    print(f"  + {position} export columns")

    return deal



# ══════════════════════════════════════════════════════════════════════════════
# Demo deal: SVCA 2022-3  (simpler waterfall — Wells Fargo, ABS Auto)
# ══════════════════════════════════════════════════════════════════════════════

SVCA_MAPPINGS = [
    # (variable_name, sheet, col, row, tape_label)
    ("total_available_funds", "Distribution Summary", "C", 10, "Total Available Funds"),
    ("total_collections", "Distribution Summary", "C", 11, "Total Collections"),
    ("svc_fee_tape", "Distribution Summary", "C", 14, "Servicing Fee"),
    ("trustee_fee_tape", "Distribution Summary", "C", 15, "Trustee Fee"),
    ("prin_collections", "Distribution Summary", "C", 18, "Principal Collections"),
    ("int_collections", "Distribution Summary", "C", 19, "Interest Collections"),
    ("sched_principal", "Distribution Summary", "C", 20, "Scheduled Principal"),
    ("cur_pool_bal", "Pool Statistics", "D", 5, "Current Pool Balance"),
    ("end_pool_bal", "Pool Statistics", "D", 7, "End Pool Balance"),
    ("a_note_balance", "Bond Details", "F", 3, "Class A Balance"),
    ("a_note_rate", "Bond Details", "F", 4, "Class A Rate"),
    ("b_note_balance", "Bond Details", "F", 5, "Class B Balance"),
    ("b_note_rate", "Bond Details", "F", 6, "Class B Rate"),
    ("c_note_balance", "Bond Details", "F", 7, "Class C Balance"),
    ("c_note_rate", "Bond Details", "F", 8, "Class C Rate"),
    ("reported_oc", "Triggers", "D", 15, "Reported OC"),
]


SVCA_TRANCHES = [
    # (class_label, cusip, regulation_type, note_rate, original_balance)
    ("A", "SVCA22A100", "144A", Decimal("0.0385"), Decimal("200000000")),
    ("A", "SVCA22AREG", "RegS", Decimal("0.0385"), Decimal("50000000")),
    ("B", "SVCA22B100", None, Decimal("0.0430"), Decimal("75000000")),
    ("C", "SVCA22C100", None, Decimal("0.0478"), Decimal("30000000")),
]

SVCA_BALANCES = {
    "A": (Decimal("140000000"), Decimal("35000000")),
    "B": (Decimal("68000000"), None),
    "C": (Decimal("27000000"), None),
}

SVCA_DIST_NODES = [
    # (key, name, type, formula, payment_type, px, py)
    ("total_available_funds_in", "Total Available Funds", "input_value", None, None, 100, 50),
    ("svc_fee_tape_in", "Servicing Fee (tape)", "input_value", None, None, 350, 50),
    ("trustee_fee_tape_in", "Trustee Fee (tape)", "input_value", None, None, 600, 50),

    ("total_fees", "Total Fees", "calculation",
     "svc_fee_tape + trustee_fee_tape", None, 475, 180),

    ("net_available", "Net Available for Distribution", "calculation",
     "total_available_funds - total_fees", None, 350, 280),

    ("class_a_int_calc", "Class A Interest (calc)", "calculation",
     "a_note_balance * a_note_rate / 12", None, 100, 400),

    ("class_b_int_calc", "Class B Interest (calc)", "calculation",
     "b_note_balance * b_note_rate / 12", None, 350, 400),

    ("class_c_int_calc", "Class C Interest (calc)", "calculation",
     "c_note_balance * c_note_rate / 12", None, 600, 400),

    ("remaining_after_int", "Remaining After Interest", "calculation",
     "MAX(net_available - class_a_int_calc - class_b_int_calc - class_c_int_calc, 0)",
     None, 350, 520),

    ("svc_fee_pmt", "Servicing Fee Pmt", "distribution", "svc_fee_tape", "SVC_FEE", 50, 640),
    ("class_a_int_pmt", "Class A Interest Pmt", "distribution",
     "MIN(net_available, class_a_int_calc)", "INT_PMT_A", 200, 640),
    ("class_b_int_pmt", "Class B Interest Pmt", "distribution",
     "MIN(MAX(net_available - class_a_int_calc, 0), class_b_int_calc)", "INT_PMT_B", 400, 640),
    ("class_c_int_pmt", "Class C Interest Pmt", "distribution",
     "MIN(MAX(net_available - class_a_int_calc - class_b_int_calc, 0), class_c_int_calc)",
     "INT_PMT_C", 600, 640),
    ("principal_dist", "Principal Distribution", "distribution",
     "remaining_after_int", "PRIN_PMT_A", 350, 760),
]

SVCA_VALIDATION_NODES = [
    ("oc_amount_check", "OC Amount Check", "validation",
     "ABS(end_pool_bal - a_note_balance - b_note_balance - c_note_balance)",
     "reported_oc", Decimal("0.01"), 100, 100),
    ("total_distribution_check", "Total Distribution Check", "validation",
     "ABS(svc_fee_pmt + class_a_int_pmt + class_b_int_pmt + class_c_int_pmt + principal_dist)",
     "total_available_funds", Decimal("0.01"), 450, 100),
]

SVCA_EDGES = [
    ("svc_fee_tape_in", "total_fees"),
    ("trustee_fee_tape_in", "total_fees"),
    ("total_available_funds_in", "net_available"),
    ("total_fees", "net_available"),
    ("net_available", "class_a_int_pmt"),
    ("net_available", "class_b_int_pmt"),
    ("net_available", "class_c_int_pmt"),
    ("class_a_int_calc", "class_a_int_pmt"),
    ("class_b_int_calc", "class_b_int_pmt"),
    ("class_c_int_calc", "class_c_int_pmt"),
    ("net_available", "remaining_after_int"),
    ("class_a_int_calc", "remaining_after_int"),
    ("class_b_int_calc", "remaining_after_int"),
    ("class_c_int_calc", "remaining_after_int"),
    ("remaining_after_int", "principal_dist"),
    ("svc_fee_tape_in", "svc_fee_pmt"),
    ("class_a_int_calc", "class_b_int_pmt"),
    ("class_a_int_calc", "class_c_int_pmt"),
    ("class_b_int_calc", "class_c_int_pmt"),
]


def seed_svca_deal(
    db: Session,
    users: dict[str, User],
    servicers: dict[str, Servicer],
    variables: dict[str, VariableDefinition],
) -> Deal:
    """Create the SVCA 2022-3 demo deal with full configuration."""
    print("\n── SVCA 2022-3 demo deal ──")

    existing = db.query(Deal).filter(Deal.name == "SVCA 2022-3").first()
    if existing:
        # Check if it has a DAG — if not, add one
        dag_svc = DagService(db)
        dag = dag_svc.load(existing.id)
        if dag and dag["nodes"]:
            print("  = Deal already exists with DAG, skipping")
            return existing
        print(f"  = Deal exists (id={existing.id}) but has no DAG, adding config...")
        deal = existing
    else:
        deal = Deal(
            name="SVCA 2022-3",
            servicer_id=servicers["Wells Fargo"].id,
            product_type="ABS Auto",
            status="active",
            created_by="jane.chen",
        )
        db.add(deal)
        db.flush()
        print(f"  + Deal id={deal.id}")

    # Variable mappings (skip if already present)
    existing_mappings = db.query(VariableMapping).filter(
        VariableMapping.deal_id == deal.id
    ).count()
    if existing_mappings == 0:
        for var_name, sheet, col, row, label in SVCA_MAPPINGS:
            var = variables.get(var_name)
            if var is None:
                print(f"    ! Variable not found: {var_name}")
                continue
            db.add(VariableMapping(
                deal_id=deal.id,
                variable_id=var.id,
                sheet_name=sheet,
                column_letter=col,
                row_number=row,
                tape_label=label,
            ))
        db.flush()
        print(f"  + {len(SVCA_MAPPINGS)} variable mappings")
    else:
        print(f"  = {existing_mappings} mappings already exist")

    # Tranches (skip if already present)
    existing_tranches = db.query(DealTranche).filter(
        DealTranche.deal_id == deal.id
    ).count()
    if existing_tranches == 0:
        tranches_by_class: dict[str, list[DealTranche]] = {}
        for class_label, cusip, reg_type, rate, orig_bal in SVCA_TRANCHES:
            t = DealTranche(
                deal_id=deal.id,
                class_label=class_label,
                cusip=cusip,
                regulation_type=reg_type or "combined",
                note_rate=rate,
                original_balance=orig_bal,
                maturity_date="2034-07-15",
            )
            db.add(t)
            db.flush()
            tranches_by_class.setdefault(class_label, []).append(t)

        for class_label, (bal_144a_or_total, bal_regs) in SVCA_BALANCES.items():
            class_tranches = tranches_by_class.get(class_label, [])
            if bal_regs is None:
                if class_tranches:
                    db.add(TrancheBalance(
                        tranche_id=class_tranches[0].id,
                        period="2026-04",
                        balance=bal_144a_or_total,
                        source="manual",
                    ))
            else:
                for t in class_tranches:
                    amount = bal_144a_or_total if t.regulation_type == "144A" else bal_regs
                    db.add(TrancheBalance(
                        tranche_id=t.id,
                        period="2026-04",
                        balance=amount,
                        source="manual",
                    ))
        db.flush()
        print(f"  + {len(SVCA_TRANCHES)} tranches with balances")
    else:
        print(f"  = {existing_tranches} tranches already exist")

    # DAG
    dag_svc = DagService(db)
    node_creates: list[DagNodeCreate] = []
    for key, name, ntype, formula, payment_type, px, py in SVCA_DIST_NODES:
        node_creates.append(DagNodeCreate(
            key=key, name=name, node_type=ntype, stream="distribution",
            formula=formula, payment_type=payment_type,
            position_x=px, position_y=py,
        ))
    for key, name, ntype, formula, comp_var, tolerance, px, py in SVCA_VALIDATION_NODES:
        node_creates.append(DagNodeCreate(
            key=key, name=name, node_type=ntype, stream="validation",
            formula=formula, comparison_variable=comp_var, tolerance=tolerance,
            position_x=px, position_y=py,
        ))

    edge_creates: list[DagEdgeCreate] = [
        DagEdgeCreate(source_key=src, target_key=tgt) for src, tgt in SVCA_EDGES
    ]

    version = dag_svc.save(
        deal_id=deal.id,
        nodes=node_creates,
        edges=edge_creates,
        created_by="root",
        description="Initial waterfall setup from seed",
    )
    print(f"  + {len(node_creates)} nodes + {len(edge_creates)} edges saved as v{version.version_number}")

    # Export columns
    existing_cols = db.query(ExportColumn).filter(
        ExportColumn.deal_id == deal.id
    ).count()
    if existing_cols == 0:
        export_svc = ExportColumnService(db)
        saved_nodes = dag_svc.load(deal.id)
        anchor_node_id = None
        if saved_nodes:
            for n in saved_nodes["nodes"]:
                if n.key == "svc_fee_pmt":
                    anchor_node_id = n.id
                    break

        pos = 1
        export_svc.create_column(deal.id, "DEAL_ID", "deal_meta", meta_field="deal_id", position=pos); pos += 1
        export_svc.create_column(deal.id, "PAYMENT_DATE", "run_meta", meta_field="payment_date", position=pos); pos += 1
        export_svc.create_column(deal.id, "PAYMENT_TYPE", "literal", literal_value="DISTRIBUTION", position=pos); pos += 1
        export_svc.create_column(deal.id, "FIELD_CODE", "literal", literal_value="", position=pos); pos += 1
        export_svc.create_column(deal.id, "AMOUNT", "distribution_node", node_id=anchor_node_id, format_type="decimal", decimal_places=2, position=pos); pos += 1
        export_svc.create_column(deal.id, "RUN_ID", "run_meta", meta_field="run_code", position=pos)
        db.flush()
        print(f"  + 6 export columns")
    else:
        print(f"  = {existing_cols} export columns already exist")

    return deal


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

def run_seed() -> None:
    db = SessionLocal()
    try:
        users = seed_users(db)
        servicers = seed_servicers(db)
        variables = seed_system_variables(db)
        seed_svcb_deal(db, users, servicers, variables)
        seed_svca_deal(db, users, servicers, variables)
        db.commit()
        print("\n✓ Seed complete")
    except Exception as exc:
        db.rollback()
        print(f"\n✗ Seed failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()