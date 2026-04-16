"""Seed script — populates database with demo data for local development.

Creates:
  - 3 users (root as admin, jane.chen as analytics, sam.analyst as analyst)
  - 3 servicers (Servicer A, Servicer B, Servicer C)
  - System-level variables (canonical names)
  - 3 fully-configured deals from real servicer example reports:
      1. Servicer A Deal 3  — 4-class sequential waterfall (ABS Dealer)
      2. Servicer B Deal 7  — 6-class interleaved waterfall (ABS Auto)
      3. Servicer C Deal 7  — same structure as B, different report layout

Run from repo root:
    cd backend
    python -m seed

Safe to re-run — skips anything that already exists by name/key.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.dag.service import DagService
from app.export.service import ExportColumnService
from app.models.dag import DagEdge, DagNode
from app.models.deal import Deal
from app.models.export import ExportColumn
from app.models.variable import VariableDefinition
from app.models.variable_mapping import VariableMapping
from app.models.servicer import Servicer
from app.models.tranche import DealTranche, TrancheBalance
from app.models.user import User
from app.models.global_export import (
    GlobalExportTemplate,
    GlobalExportColumn,
    DealExportRow,
    DealExportCell,
)
from app.schemas.dag import DagNodeCreate, DagEdgeCreate

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
    {"name": "Servicer A", "short_code": "SVCA"},
    {"name": "Servicer B", "short_code": "SVCB"},
    {"name": "Servicer C", "short_code": "SVCC"},
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
    (
        "end_available_funds",
        "End Available Funds",
        "decimal",
        "Remaining funds after all distributions (tape-reported, used for waterfall reconciliation)",
    ),
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
    # Bond note rates (tape)
    ("class_a_note_rate", "Class A Note Rate", "percentage", "Class A coupon"),
    ("class_b_note_rate", "Class B Note Rate", "percentage", "Class B coupon"),
    ("class_c_note_rate", "Class C Note Rate", "percentage", "Class C coupon"),
    ("class_d_note_rate", "Class D Note Rate", "percentage", "Class D coupon"),
    ("class_e_note_rate", "Class E Note Rate", "percentage", "Class E coupon"),
    ("class_f_note_rate", "Class F Note Rate", "percentage", "Class F coupon"),
    # Bond balances reported on tape
    ("class_a_note_balance", "Class A Note Balance", "decimal", "Class A outstanding balance"),
    ("class_b_note_balance", "Class B Note Balance", "decimal", "Class B outstanding balance"),
    ("class_c_note_balance", "Class C Note Balance", "decimal", "Class C outstanding balance"),
    ("class_d_note_balance", "Class D Note Balance", "decimal", "Class D outstanding balance"),
    ("class_e_note_balance", "Class E Note Balance", "decimal", "Class E outstanding balance"),
    ("class_f_note_balance", "Class F Note Balance", "decimal", "Class F outstanding balance"),
    # Reported interest amounts from the tape (per-class). The calculated
    # counterparts live on DAG nodes (class_X_interest_amount_calc); per-class
    # validation nodes reconcile the two.
    (
        "class_a_interest_amount",
        "Class A Interest Amount",
        "decimal",
        "Class A interest reported on tape",
    ),
    (
        "class_b_interest_amount",
        "Class B Interest Amount",
        "decimal",
        "Class B interest reported on tape",
    ),
    (
        "class_c_interest_amount",
        "Class C Interest Amount",
        "decimal",
        "Class C interest reported on tape",
    ),
    (
        "class_d_interest_amount",
        "Class D Interest Amount",
        "decimal",
        "Class D interest reported on tape",
    ),
    (
        "class_e_interest_amount",
        "Class E Interest Amount",
        "decimal",
        "Class E interest reported on tape",
    ),
    (
        "class_f_interest_amount",
        "Class F Interest Amount",
        "decimal",
        "Class F interest reported on tape",
    ),
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
# Deal A: Servicer A Deal 3 — 4-class sequential waterfall (ABS Dealer)
# Source: servicer_a_example.xlsx
# ══════════════════════════════════════════════════════════════════════════════

DEAL_A_MAPPINGS = [
    # (variable_name, sheet, col, row, tape_label)
    # All on single "Sheet 1", values in column J
    ("total_available_funds", "Sheet 1", "J", 147, "Total Available Funds"),
    (
        "end_available_funds",
        "Sheet 1",
        "J",
        175,
        "Remaining Available Funds (placeholder — verify cell)",
    ),
    ("total_collections", "Sheet 1", "J", 127, "Total Collections Remitted by Servicer"),
    ("svc_fee_tape", "Sheet 1", "J", 151, "Servicing Fee"),
    ("backup_svc_fee_tape", "Sheet 1", "J", 153, "Backup Servicing Fee"),
    ("trustee_fee_tape", "Sheet 1", "J", 157, "Indenture Trustee Fee"),
    ("prin_collections", "Sheet 1", "J", 130, "Principal Collections"),
    ("int_collections", "Sheet 1", "J", 129, "Income Collections"),
    ("cur_pool_bal", "Sheet 1", "J", 64, "Eligible Loan Balance"),
    ("class_a_note_rate", "Sheet 1", "J", 231, "Class A Note Rate"),
    ("class_a_note_balance", "Sheet 1", "J", 225, "Class A Note Balance (prior)"),
    ("class_b_note_rate", "Sheet 1", "J", 249, "Class B Note Rate"),
    ("class_b_note_balance", "Sheet 1", "J", 243, "Class B Note Balance (prior)"),
    ("class_c_note_rate", "Sheet 1", "J", 267, "Class C Note Rate"),
    ("class_c_note_balance", "Sheet 1", "J", 261, "Class C Note Balance (prior)"),
    ("class_d_note_rate", "Sheet 1", "J", 285, "Class D Note Rate"),
    ("class_d_note_balance", "Sheet 1", "J", 279, "Class D Note Balance (prior)"),
]

DEAL_A_TRANCHES = [
    # (class_label, cusip, regulation_type, note_rate, original_balance)
    ("A", "SVCA3A001", "combined", Decimal("0.0657"), Decimal("151710000")),
    ("B", "SVCA3B001", "combined", Decimal("0.0752"), Decimal("69770000")),
    ("C", "SVCA3C001", "combined", Decimal("0.0845"), Decimal("77520000")),
    ("D", "SVCA3D001", "combined", Decimal("0.0900"), Decimal("90900000")),
]

DEAL_A_BALANCES = {
    # class_label → current balance (period 2025-06, from report)
    "A": Decimal("8131209.64"),
    "B": Decimal("58619746"),
    "C": Decimal("77520000"),
    "D": Decimal("90900000"),
}

DEAL_A_DIST_NODES = [
    # (key, name, node_type, formula, payment_type, px, py)
    # Row 1: input nodes
    ("total_available_funds_in", "Total Available Funds", "input_value", None, None, 100, 50),
    ("svc_fee_tape_in", "Servicing Fee (tape)", "input_value", None, None, 300, 50),
    ("trustee_fee_tape_in", "Trustee Fee (tape)", "input_value", None, None, 500, 50),
    ("backup_svc_fee_tape_in", "Backup Svc Fee (tape)", "input_value", None, None, 700, 50),
    # Row 2: fee aggregation
    (
        "total_fees",
        "Total Fees",
        "calculation",
        "svc_fee_tape + trustee_fee_tape + backup_svc_fee_tape",
        None,
        400,
        180,
    ),
    # Row 3: net distributable
    (
        "net_available",
        "Net Available for Distribution",
        "calculation",
        "total_available_funds - total_fees",
        None,
        400,
        280,
    ),
    # Row 4: interest calculations per class
    (
        "class_a_interest_amount_calc",
        "Class A Interest (calc)",
        "calculation",
        "class_a_note_balance * class_a_note_rate / 12",
        None,
        100,
        400,
    ),
    (
        "class_b_interest_amount_calc",
        "Class B Interest (calc)",
        "calculation",
        "class_b_note_balance * class_b_note_rate / 12",
        None,
        300,
        400,
    ),
    (
        "class_c_interest_amount_calc",
        "Class C Interest (calc)",
        "calculation",
        "class_c_note_balance * class_c_note_rate / 12",
        None,
        500,
        400,
    ),
    (
        "class_d_interest_amount_calc",
        "Class D Interest (calc)",
        "calculation",
        "class_d_note_balance * class_d_note_rate / 12",
        None,
        700,
        400,
    ),
    # Row 5: remaining after interest
    (
        "remaining_after_int",
        "Remaining After Interest",
        "calculation",
        "MAX(net_available - class_a_interest_amount_calc - class_b_interest_amount_calc - class_c_interest_amount_calc - class_d_interest_amount_calc, 0)",
        None,
        400,
        520,
    ),
    # Row 6: distribution nodes — sequential waterfall
    ("svc_fee_pmt", "Servicing Fee Pmt", "distribution", "svc_fee_tape", "SVC_FEE", 50, 640),
    (
        "class_a_int_pmt",
        "Class A Interest Pmt",
        "distribution",
        "MIN(net_available, class_a_interest_amount_calc)",
        "INT_PMT_A",
        175,
        640,
    ),
    (
        "class_b_int_pmt",
        "Class B Interest Pmt",
        "distribution",
        "MIN(MAX(net_available - class_a_interest_amount_calc, 0), class_b_interest_amount_calc)",
        "INT_PMT_B",
        300,
        640,
    ),
    (
        "class_c_int_pmt",
        "Class C Interest Pmt",
        "distribution",
        "MIN(MAX(net_available - class_a_interest_amount_calc - class_b_interest_amount_calc, 0), class_c_interest_amount_calc)",
        "INT_PMT_C",
        425,
        640,
    ),
    (
        "class_d_int_pmt",
        "Class D Interest Pmt",
        "distribution",
        "MIN(MAX(net_available - class_a_interest_amount_calc - class_b_interest_amount_calc - class_c_interest_amount_calc, 0), class_d_interest_amount_calc)",
        "INT_PMT_D",
        550,
        640,
    ),
    # Row 7: principal distributions — sequential A→B→C→D
    (
        "class_a_prin_pmt",
        "Class A Principal Pmt",
        "distribution",
        "MIN(remaining_after_int, class_a_note_balance)",
        "PRIN_PMT_A",
        100,
        760,
    ),
    (
        "class_b_prin_pmt",
        "Class B Principal Pmt",
        "distribution",
        "MIN(MAX(remaining_after_int - class_a_prin_pmt, 0), class_b_note_balance)",
        "PRIN_PMT_B",
        300,
        760,
    ),
    (
        "class_c_prin_pmt",
        "Class C Principal Pmt",
        "distribution",
        "MIN(MAX(remaining_after_int - class_a_prin_pmt - class_b_prin_pmt, 0), class_c_note_balance)",
        "PRIN_PMT_C",
        500,
        760,
    ),
    (
        "class_d_prin_pmt",
        "Class D Principal Pmt",
        "distribution",
        "MIN(MAX(remaining_after_int - class_a_prin_pmt - class_b_prin_pmt - class_c_prin_pmt, 0), class_d_note_balance)",
        "PRIN_PMT_D",
        700,
        760,
    ),
]

DEAL_A_VALIDATION_NODES = [
    (
        "total_distribution_check",
        "Total Distribution Check",
        "validation",
        "ABS(svc_fee_pmt + class_a_int_pmt + class_b_int_pmt + class_c_int_pmt + class_d_int_pmt + class_a_prin_pmt + class_b_prin_pmt + class_c_prin_pmt + class_d_prin_pmt)",
        "total_available_funds",
        Decimal("0.01"),
        400,
        100,
    ),
    # Per-class interest reconciliation: compare calc against tape-reported.
    (
        "class_a_interest_amount_check",
        "Class A Interest Amount Check",
        "validation",
        "class_a_interest_amount_calc",
        "class_a_interest_amount",
        Decimal("0.01"),
        50,
        100,
    ),
    (
        "class_b_interest_amount_check",
        "Class B Interest Amount Check",
        "validation",
        "class_b_interest_amount_calc",
        "class_b_interest_amount",
        Decimal("0.01"),
        175,
        100,
    ),
    (
        "class_c_interest_amount_check",
        "Class C Interest Amount Check",
        "validation",
        "class_c_interest_amount_calc",
        "class_c_interest_amount",
        Decimal("0.01"),
        300,
        100,
    ),
    (
        "class_d_interest_amount_check",
        "Class D Interest Amount Check",
        "validation",
        "class_d_interest_amount_calc",
        "class_d_interest_amount",
        Decimal("0.01"),
        525,
        100,
    ),
]

DEAL_A_EDGES = [
    # Fee inputs → total_fees
    ("svc_fee_tape_in", "total_fees"),
    ("trustee_fee_tape_in", "total_fees"),
    ("backup_svc_fee_tape_in", "total_fees"),
    # total_available + total_fees → net_available
    ("total_available_funds_in", "net_available"),
    ("total_fees", "net_available"),
    # net_available → interest payments
    ("net_available", "class_a_int_pmt"),
    ("net_available", "class_b_int_pmt"),
    ("net_available", "class_c_int_pmt"),
    ("net_available", "class_d_int_pmt"),
    # interest calcs → interest payments
    ("class_a_interest_amount_calc", "class_a_int_pmt"),
    ("class_b_interest_amount_calc", "class_b_int_pmt"),
    ("class_c_interest_amount_calc", "class_c_int_pmt"),
    ("class_d_interest_amount_calc", "class_d_int_pmt"),
    # Sequential interest dependencies (B needs A, C needs A+B, D needs A+B+C)
    ("class_a_interest_amount_calc", "class_b_int_pmt"),
    ("class_a_interest_amount_calc", "class_c_int_pmt"),
    ("class_b_interest_amount_calc", "class_c_int_pmt"),
    ("class_a_interest_amount_calc", "class_d_int_pmt"),
    ("class_b_interest_amount_calc", "class_d_int_pmt"),
    ("class_c_interest_amount_calc", "class_d_int_pmt"),
    # net_available + all int calcs → remaining_after_int
    ("net_available", "remaining_after_int"),
    ("class_a_interest_amount_calc", "remaining_after_int"),
    ("class_b_interest_amount_calc", "remaining_after_int"),
    ("class_c_interest_amount_calc", "remaining_after_int"),
    ("class_d_interest_amount_calc", "remaining_after_int"),
    # remaining → principal payments
    ("remaining_after_int", "class_a_prin_pmt"),
    ("remaining_after_int", "class_b_prin_pmt"),
    ("remaining_after_int", "class_c_prin_pmt"),
    ("remaining_after_int", "class_d_prin_pmt"),
    # Sequential principal dependencies
    ("class_a_prin_pmt", "class_b_prin_pmt"),
    ("class_a_prin_pmt", "class_c_prin_pmt"),
    ("class_b_prin_pmt", "class_c_prin_pmt"),
    ("class_a_prin_pmt", "class_d_prin_pmt"),
    ("class_b_prin_pmt", "class_d_prin_pmt"),
    ("class_c_prin_pmt", "class_d_prin_pmt"),
    # Servicing fee flow
    ("svc_fee_tape_in", "svc_fee_pmt"),
]

DEAL_A_WATERFALL_ORDER = {
    "svc_fee_pmt": 1,
    "class_a_int_pmt": 2,
    "class_b_int_pmt": 3,
    "class_c_int_pmt": 4,
    "class_d_int_pmt": 5,
    "class_a_prin_pmt": 6,
    "class_b_prin_pmt": 7,
    "class_c_prin_pmt": 8,
    "class_d_prin_pmt": 9,
}


# ══════════════════════════════════════════════════════════════════════════════
# Deals B & C: 6-class interleaved waterfall (shared DAG structure)
# Source: servicer_b_example.xlsx, servicer_c_example.xlsx
# ══════════════════════════════════════════════════════════════════════════════

DEAL_B_MAPPINGS = [
    # (variable_name, sheet, col, row, tape_label)
    # "Sheet 1" (with space) — Servicer B's report format
    ("total_available_funds", "Sheet 1", "K", 81, "Total Available Funds"),
    (
        "end_available_funds",
        "Sheet 1",
        "K",
        100,
        "Remaining Available Funds (placeholder — verify cell)",
    ),
    ("svc_fee_tape", "Sheet 1", "J", 84, "Servicing Fee"),
    ("backup_svc_fee_tape", "Sheet 1", "J", 85, "Backup Servicing Fees"),
    ("trustee_fee_tape", "Sheet 1", "J", 86, "Indenture Trustee Fees"),
    ("prin_collections", "Sheet 1", "J", 71, "Principal Collections"),
    ("int_collections", "Sheet 1", "J", 72, "Interest Collections"),
    ("liquidation_proceeds", "Sheet 1", "J", 73, "Liquidation Proceeds"),
    ("cur_pool_bal", "Sheet 1", "K", 37, "Pool Balance"),
    ("reported_oc", "Sheet 1", "K", 146, "OC Amount"),
    ("class_a_note_rate", "Sheet 1", "F", 62, "Class A Note Rate"),
    ("class_b_note_rate", "Sheet 1", "F", 63, "Class B Note Rate"),
    ("class_c_note_rate", "Sheet 1", "F", 64, "Class C Note Rate"),
    ("class_d_note_rate", "Sheet 1", "F", 65, "Class D Note Rate"),
    ("class_e_note_rate", "Sheet 1", "F", 66, "Class E Note Rate"),
    ("class_f_note_rate", "Sheet 1", "F", 67, "Class F Note Rate"),
    ("class_a_note_balance", "Sheet 1", "E", 46, "Class A Begin Balance"),
    ("class_b_note_balance", "Sheet 1", "F", 46, "Class B Begin Balance"),
    ("class_c_note_balance", "Sheet 1", "G", 46, "Class C Begin Balance"),
    ("class_d_note_balance", "Sheet 1", "H", 46, "Class D Begin Balance"),
    ("class_e_note_balance", "Sheet 1", "I", 46, "Class E Begin Balance"),
    ("class_f_note_balance", "Sheet 1", "J", 46, "Class F Begin Balance"),
]

DEAL_C_MAPPINGS = [
    # "Sheet1" (no space) — Servicer C's report format, same data different layout
    ("total_available_funds", "Sheet1", "K", 80, "Total Available Funds"),
    (
        "end_available_funds",
        "Sheet1",
        "K",
        99,
        "Remaining Available Funds (placeholder — verify cell)",
    ),
    ("svc_fee_tape", "Sheet1", "J", 83, "Servicing Fee"),
    ("backup_svc_fee_tape", "Sheet1", "J", 84, "Backup Servicing Fees"),
    ("trustee_fee_tape", "Sheet1", "J", 85, "Indenture Trustee Fees"),
    ("prin_collections", "Sheet1", "F", 70, "Principal Collections"),
    ("int_collections", "Sheet1", "H", 71, "Interest Collections"),
    ("liquidation_proceeds", "Sheet1", "I", 72, "Liquidation Proceeds"),
    ("cur_pool_bal", "Sheet1", "I", 36, "Pool Balance"),
    ("reported_oc", "Sheet1", "H", 145, "OC Amount"),
    ("class_a_note_rate", "Sheet1", "F", 61, "Class A Note Rate"),
    ("class_b_note_rate", "Sheet1", "F", 62, "Class B Note Rate"),
    ("class_c_note_rate", "Sheet1", "F", 63, "Class C Note Rate"),
    ("class_d_note_rate", "Sheet1", "F", 64, "Class D Note Rate"),
    ("class_e_note_rate", "Sheet1", "F", 65, "Class E Note Rate"),
    ("class_f_note_rate", "Sheet1", "F", 66, "Class F Note Rate"),
    ("class_a_note_balance", "Sheet1", "D", 45, "Class A Begin Balance"),
    ("class_b_note_balance", "Sheet1", "E", 45, "Class B Begin Balance"),
    ("class_c_note_balance", "Sheet1", "F", 45, "Class C Begin Balance"),
    ("class_d_note_balance", "Sheet1", "G", 45, "Class D Begin Balance"),
    ("class_e_note_balance", "Sheet1", "H", 45, "Class E Begin Balance"),
    ("class_f_note_balance", "Sheet1", "I", 45, "Class F Begin Balance"),
]

DEAL_B_TRANCHES = [
    # (class_label, cusip, regulation_type, note_rate, original_balance)
    ("A", "SVCB7A001", "combined", Decimal("0.0412"), Decimal("128650000")),
    ("B", "SVCB7B001", "combined", Decimal("0.0455"), Decimal("27900000")),
    ("C", "SVCB7C001", "combined", Decimal("0.0486"), Decimal("43400000")),
    ("D", "SVCB7D001", "combined", Decimal("0.0583"), Decimal("44180000")),
    ("E", "SVCB7E001", "combined", Decimal("0.0808"), Decimal("18600000")),
    ("F", "SVCB7F001", "combined", Decimal("0.0976"), Decimal("17820000")),
]

DEAL_C_TRANCHES = [
    ("A", "SVCC7A001", "combined", Decimal("0.0412"), Decimal("128650000")),
    ("B", "SVCC7B001", "combined", Decimal("0.0455"), Decimal("27900000")),
    ("C", "SVCC7C001", "combined", Decimal("0.0486"), Decimal("43400000")),
    ("D", "SVCC7D001", "combined", Decimal("0.0583"), Decimal("44180000")),
    ("E", "SVCC7E001", "combined", Decimal("0.0808"), Decimal("18600000")),
    ("F", "SVCC7F001", "combined", Decimal("0.0976"), Decimal("17820000")),
]

# Shared balances for B & C (same deal data, different report format)
DEAL_BC_BALANCES = {
    "A": Decimal("0"),
    "B": Decimal("0"),
    "C": Decimal("0"),
    "D": Decimal("25191696.50"),
    "E": Decimal("18600000"),
    "F": Decimal("17820000"),
}


def _build_6class_dag():
    """Shared DAG structure for 6-class interleaved waterfall (Deals B & C).

    Returns (dist_nodes, validation_nodes, edges, waterfall_order).
    """
    dist_nodes = [
        # (key, name, node_type, formula, payment_type, px, py)
        # Inputs
        ("total_available_funds_in", "Total Available Funds", "input_value", None, None, 100, 50),
        ("svc_fee_tape_in", "Servicing Fee (tape)", "input_value", None, None, 350, 50),
        ("trustee_fee_tape_in", "Trustee Fee (tape)", "input_value", None, None, 550, 50),
        ("backup_svc_fee_tape_in", "Backup Svc Fee (tape)", "input_value", None, None, 750, 50),
        # Fee aggregation
        (
            "total_fees",
            "Total Fees",
            "calculation",
            "svc_fee_tape + trustee_fee_tape + backup_svc_fee_tape",
            None,
            450,
            180,
        ),
        # Net distributable
        (
            "net_available",
            "Net Available for Distribution",
            "calculation",
            "total_available_funds - total_fees",
            None,
            400,
            280,
        ),
        # Interest calculations for all 6 classes
        (
            "class_a_interest_amount_calc",
            "Class A Interest (calc)",
            "calculation",
            "class_a_note_balance * class_a_note_rate / 12",
            None,
            50,
            400,
        ),
        (
            "class_b_interest_amount_calc",
            "Class B Interest (calc)",
            "calculation",
            "class_b_note_balance * class_b_note_rate / 12",
            None,
            200,
            400,
        ),
        (
            "class_c_interest_amount_calc",
            "Class C Interest (calc)",
            "calculation",
            "class_c_note_balance * class_c_note_rate / 12",
            None,
            350,
            400,
        ),
        (
            "class_d_interest_amount_calc",
            "Class D Interest (calc)",
            "calculation",
            "class_d_note_balance * class_d_note_rate / 12",
            None,
            500,
            400,
        ),
        (
            "class_e_interest_amount_calc",
            "Class E Interest (calc)",
            "calculation",
            "class_e_note_balance * class_e_note_rate / 12",
            None,
            650,
            400,
        ),
        (
            "class_f_interest_amount_calc",
            "Class F Interest (calc)",
            "calculation",
            "class_f_note_balance * class_f_note_rate / 12",
            None,
            800,
            400,
        ),
        # Remaining after all interest
        (
            "remaining_after_int",
            "Remaining After Interest",
            "calculation",
            "MAX(net_available - class_a_interest_amount_calc - class_b_interest_amount_calc - class_c_interest_amount_calc - class_d_interest_amount_calc - class_e_interest_amount_calc - class_f_interest_amount_calc, 0)",
            None,
            400,
            520,
        ),
        # Distribution nodes — interleaved interest then principal
        ("svc_fee_pmt", "Servicing Fee Pmt", "distribution", "svc_fee_tape", "SVC_FEE", 50, 640),
        (
            "class_a_int_pmt",
            "Class A Interest Pmt",
            "distribution",
            "MIN(net_available, class_a_interest_amount_calc)",
            "INT_PMT_A",
            150,
            640,
        ),
        (
            "class_b_int_pmt",
            "Class B Interest Pmt",
            "distribution",
            "MIN(MAX(net_available - class_a_interest_amount_calc, 0), class_b_interest_amount_calc)",
            "INT_PMT_B",
            270,
            640,
        ),
        (
            "class_c_int_pmt",
            "Class C Interest Pmt",
            "distribution",
            "MIN(MAX(net_available - class_a_interest_amount_calc - class_b_interest_amount_calc, 0), class_c_interest_amount_calc)",
            "INT_PMT_C",
            390,
            640,
        ),
        (
            "class_d_int_pmt",
            "Class D Interest Pmt",
            "distribution",
            "MIN(MAX(net_available - class_a_interest_amount_calc - class_b_interest_amount_calc - class_c_interest_amount_calc, 0), class_d_interest_amount_calc)",
            "INT_PMT_D",
            510,
            640,
        ),
        (
            "class_e_int_pmt",
            "Class E Interest Pmt",
            "distribution",
            "MIN(MAX(net_available - class_a_interest_amount_calc - class_b_interest_amount_calc - class_c_interest_amount_calc - class_d_interest_amount_calc, 0), class_e_interest_amount_calc)",
            "INT_PMT_E",
            630,
            640,
        ),
        (
            "class_f_int_pmt",
            "Class F Interest Pmt",
            "distribution",
            "MIN(MAX(net_available - class_a_interest_amount_calc - class_b_interest_amount_calc - class_c_interest_amount_calc - class_d_interest_amount_calc - class_e_interest_amount_calc, 0), class_f_interest_amount_calc)",
            "INT_PMT_F",
            750,
            640,
        ),
        # Regular principal distribution (whatever remains after interest)
        (
            "regular_prin_dist",
            "Regular Principal Distribution",
            "distribution",
            "remaining_after_int",
            "PRIN_DIST",
            400,
            760,
        ),
    ]

    validation_nodes = [
        (
            "oc_amount_check",
            "OC Amount Check",
            "validation",
            "ABS(cur_pool_bal - class_a_note_balance - class_b_note_balance - class_c_note_balance - class_d_note_balance - class_e_note_balance - class_f_note_balance)",
            "reported_oc",
            Decimal("0.01"),
            100,
            100,
        ),
        (
            "total_distribution_check",
            "Total Distribution Check",
            "validation",
            "ABS(svc_fee_pmt + class_a_int_pmt + class_b_int_pmt + class_c_int_pmt + class_d_int_pmt + class_e_int_pmt + class_f_int_pmt + regular_prin_dist)",
            "total_available_funds",
            Decimal("0.01"),
            500,
            100,
        ),
        # Per-class interest reconciliation: compare calc against tape-reported.
        (
            "class_a_interest_amount_check",
            "Class A Interest Amount Check",
            "validation",
            "class_a_interest_amount_calc",
            "class_a_interest_amount",
            Decimal("0.01"),
            50,
            200,
        ),
        (
            "class_b_interest_amount_check",
            "Class B Interest Amount Check",
            "validation",
            "class_b_interest_amount_calc",
            "class_b_interest_amount",
            Decimal("0.01"),
            170,
            200,
        ),
        (
            "class_c_interest_amount_check",
            "Class C Interest Amount Check",
            "validation",
            "class_c_interest_amount_calc",
            "class_c_interest_amount",
            Decimal("0.01"),
            290,
            200,
        ),
        (
            "class_d_interest_amount_check",
            "Class D Interest Amount Check",
            "validation",
            "class_d_interest_amount_calc",
            "class_d_interest_amount",
            Decimal("0.01"),
            410,
            200,
        ),
        (
            "class_e_interest_amount_check",
            "Class E Interest Amount Check",
            "validation",
            "class_e_interest_amount_calc",
            "class_e_interest_amount",
            Decimal("0.01"),
            530,
            200,
        ),
        (
            "class_f_interest_amount_check",
            "Class F Interest Amount Check",
            "validation",
            "class_f_interest_amount_calc",
            "class_f_interest_amount",
            Decimal("0.01"),
            650,
            200,
        ),
    ]

    edges = [
        # Fee inputs → total_fees
        ("svc_fee_tape_in", "total_fees"),
        ("trustee_fee_tape_in", "total_fees"),
        ("backup_svc_fee_tape_in", "total_fees"),
        # total_available + total_fees → net_available
        ("total_available_funds_in", "net_available"),
        ("total_fees", "net_available"),
        # net_available → interest payments
        ("net_available", "class_a_int_pmt"),
        ("net_available", "class_b_int_pmt"),
        ("net_available", "class_c_int_pmt"),
        ("net_available", "class_d_int_pmt"),
        ("net_available", "class_e_int_pmt"),
        ("net_available", "class_f_int_pmt"),
        # interest calcs → interest payments
        ("class_a_interest_amount_calc", "class_a_int_pmt"),
        ("class_b_interest_amount_calc", "class_b_int_pmt"),
        ("class_c_interest_amount_calc", "class_c_int_pmt"),
        ("class_d_interest_amount_calc", "class_d_int_pmt"),
        ("class_e_interest_amount_calc", "class_e_int_pmt"),
        ("class_f_interest_amount_calc", "class_f_int_pmt"),
        # Sequential interest dependencies
        ("class_a_interest_amount_calc", "class_b_int_pmt"),
        ("class_a_interest_amount_calc", "class_c_int_pmt"),
        ("class_b_interest_amount_calc", "class_c_int_pmt"),
        ("class_a_interest_amount_calc", "class_d_int_pmt"),
        ("class_b_interest_amount_calc", "class_d_int_pmt"),
        ("class_c_interest_amount_calc", "class_d_int_pmt"),
        ("class_a_interest_amount_calc", "class_e_int_pmt"),
        ("class_b_interest_amount_calc", "class_e_int_pmt"),
        ("class_c_interest_amount_calc", "class_e_int_pmt"),
        ("class_d_interest_amount_calc", "class_e_int_pmt"),
        ("class_a_interest_amount_calc", "class_f_int_pmt"),
        ("class_b_interest_amount_calc", "class_f_int_pmt"),
        ("class_c_interest_amount_calc", "class_f_int_pmt"),
        ("class_d_interest_amount_calc", "class_f_int_pmt"),
        ("class_e_interest_amount_calc", "class_f_int_pmt"),
        # net_available + all int calcs → remaining_after_int
        ("net_available", "remaining_after_int"),
        ("class_a_interest_amount_calc", "remaining_after_int"),
        ("class_b_interest_amount_calc", "remaining_after_int"),
        ("class_c_interest_amount_calc", "remaining_after_int"),
        ("class_d_interest_amount_calc", "remaining_after_int"),
        ("class_e_interest_amount_calc", "remaining_after_int"),
        ("class_f_interest_amount_calc", "remaining_after_int"),
        # remaining → principal
        ("remaining_after_int", "regular_prin_dist"),
        # Servicing fee flow
        ("svc_fee_tape_in", "svc_fee_pmt"),
    ]

    waterfall_order = {
        "svc_fee_pmt": 1,
        "class_a_int_pmt": 2,
        "class_b_int_pmt": 3,
        "class_c_int_pmt": 4,
        "class_d_int_pmt": 5,
        "class_e_int_pmt": 6,
        "class_f_int_pmt": 7,
        "regular_prin_dist": 8,
    }

    return dist_nodes, validation_nodes, edges, waterfall_order


# ══════════════════════════════════════════════════════════════════════════════
# Generic deal seeder (used for all 3 deals)
# ══════════════════════════════════════════════════════════════════════════════


def _seed_deal(
    db: Session,
    deal_name: str,
    servicer: Servicer,
    product_type: str,
    created_by: str,
    mappings: list[tuple],
    tranches: list[tuple],
    balances: dict[str, Decimal],
    dist_nodes: list[tuple],
    validation_nodes: list[tuple],
    edges: list[tuple[str, str]],
    waterfall_order: dict[str, int],
    variables: dict[str, VariableDefinition],
    balance_period: str = "2025-06",
) -> Deal:
    """Create a deal with full configuration (mappings, tranches, DAG, export columns)."""
    print(f"\n── {deal_name} ──")

    existing = db.query(Deal).filter(Deal.name == deal_name).first()
    if existing:
        dag_svc = DagService(db)
        dag = dag_svc.load(existing.id)
        if dag and dag["nodes"]:
            print("  = Deal already exists with DAG, skipping")
            return existing
        print(f"  = Deal exists (id={existing.id}) but has no DAG, adding config...")
        deal = existing
    else:
        deal = Deal(
            name=deal_name,
            servicer_id=servicer.id,
            product_type=product_type,
            status="active",
            created_by=created_by,
        )
        db.add(deal)
        db.flush()
        print(f"  + Deal id={deal.id}")

    # Variable mappings
    existing_mappings = (
        db.query(VariableMapping).filter(VariableMapping.deal_id == deal.id).count()
    )
    if existing_mappings == 0:
        for var_name, sheet, col, row, label in mappings:
            var = variables.get(var_name)
            if var is None:
                print(f"    ! Variable not found: {var_name}")
                continue
            db.add(
                VariableMapping(
                    deal_id=deal.id,
                    variable_id=var.id,
                    sheet_name=sheet,
                    column_letter=col,
                    row_number=row,
                    tape_label=label,
                )
            )
        db.flush()
        print(f"  + {len(mappings)} variable mappings")
    else:
        print(f"  = {existing_mappings} mappings already exist")

    # Tranches
    existing_tranches = db.query(DealTranche).filter(DealTranche.deal_id == deal.id).count()
    if existing_tranches == 0:
        for class_label, cusip, reg_type, rate, orig_bal in tranches:
            t = DealTranche(
                deal_id=deal.id,
                class_label=class_label,
                cusip=cusip,
                regulation_type=reg_type,
                note_rate=rate,
                original_balance=orig_bal,
                maturity_date="2032-01-15",
            )
            db.add(t)
            db.flush()

            bal = balances.get(class_label)
            if bal is not None:
                db.add(
                    TrancheBalance(
                        tranche_id=t.id,
                        period=balance_period,
                        balance=bal,
                        source="manual",
                    )
                )
        db.flush()
        print(f"  + {len(tranches)} tranches with balances")
    else:
        print(f"  = {existing_tranches} tranches already exist")

    # DAG
    dag_svc = DagService(db)

    node_creates: list[DagNodeCreate] = []
    for key, name, ntype, formula, payment_type, px, py in dist_nodes:
        node_creates.append(
            DagNodeCreate(
                key=key,
                name=name,
                node_type=ntype,
                stream="distribution",
                formula=formula,
                payment_type=payment_type,
                waterfall_order=waterfall_order.get(key),
                position_x=px,
                position_y=py,
            )
        )
    for key, name, ntype, formula, comp_var, tolerance, px, py in validation_nodes:
        node_creates.append(
            DagNodeCreate(
                key=key,
                name=name,
                node_type=ntype,
                stream="validation",
                formula=formula,
                comparison_variable=comp_var,
                tolerance=tolerance,
                position_x=px,
                position_y=py,
            )
        )

    edge_creates: list[DagEdgeCreate] = [
        DagEdgeCreate(source_key=src, target_key=tgt) for src, tgt in edges
    ]

    version = dag_svc.save(
        deal_id=deal.id,
        nodes=node_creates,
        edges=edge_creates,
        created_by="root",
        description="Initial waterfall setup from seed",
    )
    print(
        f"  + {len(node_creates)} nodes + {len(edge_creates)} edges saved as v{version.version_number}"
    )

    # Export columns (System A layout)
    existing_cols = db.query(ExportColumn).filter(ExportColumn.deal_id == deal.id).count()
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
        export_svc.create_column(
            deal.id, "DEAL_ID", "deal_meta", meta_field="deal_id", position=pos
        )
        pos += 1
        export_svc.create_column(
            deal.id, "PAYMENT_DATE", "run_meta", meta_field="payment_date", position=pos
        )
        pos += 1
        export_svc.create_column(
            deal.id, "PAYMENT_TYPE", "literal", literal_value="DISTRIBUTION", position=pos
        )
        pos += 1
        export_svc.create_column(deal.id, "FIELD_CODE", "literal", literal_value="", position=pos)
        pos += 1
        export_svc.create_column(
            deal.id,
            "AMOUNT",
            "distribution_node",
            node_id=anchor_node_id,
            format_type="decimal",
            decimal_places=2,
            position=pos,
        )
        pos += 1
        export_svc.create_column(
            deal.id, "RUN_ID", "run_meta", meta_field="run_code", position=pos
        )
        db.flush()
        print(f"  + 6 export columns")
    else:
        print(f"  = {existing_cols} export columns already exist")

    return deal


# ══════════════════════════════════════════════════════════════════════════════
# Drop all records
# ══════════════════════════════════════════════════════════════════════════════


def drop_all_records(db: Session) -> None:
    """Delete all records from tables in reverse dependency order."""
    print("\n── Dropping all records ──")
    tables_to_clear = [
        DealExportCell,
        DealExportRow,
        GlobalExportColumn,
        GlobalExportTemplate,
        ExportColumn,
        DagEdge,
        DagNode,
        TrancheBalance,
        DealTranche,
        VariableMapping,
        Deal,
        VariableDefinition,
        Servicer,
        User,
    ]
    for table in tables_to_clear:
        count = db.query(table).delete()
        if count > 0:
            print(f"  - Deleted {count} {table.__name__} record(s)")
    db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# Global Export Templates (3 fixed)
# ══════════════════════════════════════════════════════════════════════════════

GLOBAL_TEMPLATES = [
    {
        "name": "System A",
        "description": "Row per payment — standard format",
        "columns": [
            {
                "header_label": "DEAL_ID",
                "value_type": "deal_meta",
                "meta_field": "deal_id",
                "format_type": "text",
            },
            {
                "header_label": "PAYMENT_DATE",
                "value_type": "run_meta",
                "meta_field": "payment_date",
                "format_type": "text",
            },
            {
                "header_label": "PAYMENT_TYPE",
                "value_type": "literal",
                "literal_value": "DISTRIBUTION",
                "format_type": "text",
            },
            {
                "header_label": "FIELD_CODE",
                "value_type": "distribution_node",
                "format_type": "text",
            },
            {
                "header_label": "AMOUNT",
                "value_type": "distribution_node",
                "format_type": "decimal",
                "decimal_places": 2,
            },
            {
                "header_label": "RUN_ID",
                "value_type": "run_meta",
                "meta_field": "run_code",
                "format_type": "text",
            },
        ],
    },
    {
        "name": "System B",
        "description": "Wide format with 144A/RegS split columns",
        "columns": [
            {
                "header_label": "DEAL_ID",
                "value_type": "deal_meta",
                "meta_field": "deal_id",
                "format_type": "text",
            },
            {
                "header_label": "PAYMENT_DATE",
                "value_type": "run_meta",
                "meta_field": "payment_date",
                "format_type": "text",
            },
            {
                "header_label": "FIELD_CODE",
                "value_type": "distribution_node",
                "format_type": "text",
            },
            {
                "header_label": "AMOUNT_144A",
                "value_type": "distribution_node",
                "format_type": "decimal",
                "decimal_places": 2,
                "prorate_by": "144a",
            },
            {
                "header_label": "AMOUNT_REGS",
                "value_type": "distribution_node",
                "format_type": "decimal",
                "decimal_places": 2,
                "prorate_by": "regs",
            },
            {
                "header_label": "AMOUNT_TOTAL",
                "value_type": "distribution_node",
                "format_type": "decimal",
                "decimal_places": 2,
            },
            {
                "header_label": "RUN_ID",
                "value_type": "run_meta",
                "meta_field": "run_code",
                "format_type": "text",
            },
        ],
    },
    {
        "name": "System C",
        "description": "CUSIP-level detail format",
        "columns": [
            {
                "header_label": "DEAL_ID",
                "value_type": "deal_meta",
                "meta_field": "deal_id",
                "format_type": "text",
            },
            {
                "header_label": "PAYMENT_DATE",
                "value_type": "run_meta",
                "meta_field": "payment_date",
                "format_type": "text",
            },
            {
                "header_label": "CUSIP",
                "value_type": "literal",
                "literal_value": "",
                "format_type": "text",
            },
            {
                "header_label": "PAYMENT_TYPE",
                "value_type": "literal",
                "literal_value": "DISTRIBUTION",
                "format_type": "text",
            },
            {
                "header_label": "AMOUNT",
                "value_type": "distribution_node",
                "format_type": "decimal",
                "decimal_places": 2,
            },
            {
                "header_label": "RUN_ID",
                "value_type": "run_meta",
                "meta_field": "run_code",
                "format_type": "text",
            },
        ],
    },
]


def seed_global_templates(db: Session) -> list[GlobalExportTemplate]:
    """Create the 3 fixed global export templates with their columns."""
    print("\n── Global export templates ──")
    templates = []
    for tmpl_data in GLOBAL_TEMPLATES:
        t = GlobalExportTemplate(
            name=tmpl_data["name"],
            description=tmpl_data["description"],
        )
        db.add(t)
        db.flush()
        templates.append(t)

        for pos, col_data in enumerate(tmpl_data["columns"], start=1):
            col = GlobalExportColumn(
                template_id=t.id,
                position=pos,
                header_label=col_data["header_label"],
                value_type=col_data["value_type"],
                literal_value=col_data.get("literal_value"),
                meta_field=col_data.get("meta_field"),
                format_type=col_data.get("format_type", "text"),
                decimal_places=col_data.get("decimal_places"),
                prorate_by=col_data.get("prorate_by"),
                prorate_class_label=col_data.get("prorate_class_label"),
            )
            db.add(col)

        db.flush()
        print(f"  + {tmpl_data['name']} ({len(tmpl_data['columns'])} columns)")

    return templates


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════


def run_seed() -> None:
    db = SessionLocal()
    try:
        drop_all_records(db)
        users = seed_users(db)
        servicers = seed_servicers(db)
        variables = seed_system_variables(db)
        seed_global_templates(db)

        # Deal A: Servicer A Deal 3 — 4-class sequential waterfall
        _seed_deal(
            db,
            deal_name="Servicer A Deal 3",
            servicer=servicers["Servicer A"],
            product_type="ABS Dealer",
            created_by="jane.chen",
            mappings=DEAL_A_MAPPINGS,
            tranches=DEAL_A_TRANCHES,
            balances=DEAL_A_BALANCES,
            dist_nodes=DEAL_A_DIST_NODES,
            validation_nodes=DEAL_A_VALIDATION_NODES,
            edges=DEAL_A_EDGES,
            waterfall_order=DEAL_A_WATERFALL_ORDER,
            variables=variables,
            balance_period="2025-06",
        )

        # Deal B: Servicer B Deal 7 — 6-class interleaved waterfall
        bc_dist, bc_val, bc_edges, bc_wf = _build_6class_dag()
        _seed_deal(
            db,
            deal_name="Servicer B Deal 7",
            servicer=servicers["Servicer B"],
            product_type="ABS Auto",
            created_by="jane.chen",
            mappings=DEAL_B_MAPPINGS,
            tranches=DEAL_B_TRANCHES,
            balances=DEAL_BC_BALANCES,
            dist_nodes=bc_dist,
            validation_nodes=bc_val,
            edges=bc_edges,
            waterfall_order=bc_wf,
            variables=variables,
            balance_period="2025-06",
        )

        # Deal C: Servicer C Deal 7 — same structure as B, different report layout
        _seed_deal(
            db,
            deal_name="Servicer C Deal 7",
            servicer=servicers["Servicer C"],
            product_type="ABS Auto",
            created_by="jane.chen",
            mappings=DEAL_C_MAPPINGS,
            tranches=DEAL_C_TRANCHES,
            balances=DEAL_BC_BALANCES,
            dist_nodes=bc_dist,
            validation_nodes=bc_val,
            edges=bc_edges,
            waterfall_order=bc_wf,
            variables=variables,
            balance_period="2025-06",
        )

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
