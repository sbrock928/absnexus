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

from app.core.database import SessionLocal, engine, Base
import app.models  # noqa: F401 — registers all ORM models with Base before create_all
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
    {"name": "Servicer D", "short_code": "SVCD"},
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
    # ── Monthly pool-balance movement components (Section I of servicer's cert) ──
    ("beg_pool_balance", "Beginning Pool Balance", "decimal", "Beginning-of-period aggregate principal balance"),
    ("subsequent_receivables", "Subsequent Receivables", "decimal", "Subsequent receivables added during the collection period"),
    ("collections_outstanding", "Collections Outstanding", "decimal", "Collections on receivables outstanding at end of period"),
    ("collections_paid_off", "Collections Paid Off", "decimal", "Collections on receivables paid off during period"),
    ("receivables_liquidated", "Receivables Liquidated", "decimal", "Receivables becoming Liquidated Receivables during period"),
    ("receivables_purchased", "Receivables Purchased", "decimal", "Receivables becoming Purchased Receivables during period"),
    ("receivables_adjustments", "Receivables Adjustments", "decimal", "Other receivables adjustments"),
    # ── Extra Available Funds components ──
    ("recoveries", "Recoveries", "decimal", "Recoveries collected during period"),
    ("purchase_amounts", "Purchase Amounts", "decimal", "Purchase amounts / servicer deposits"),
    ("inv_earn_collection", "Investment Earnings (Collection)", "decimal", "Investment earnings on Collection Account"),
    ("inv_earn_reserve", "Investment Earnings (Reserve)", "decimal", "Investment earnings transferred from Reserve"),
    ("inv_earn_prefund", "Investment Earnings (Prefund)", "decimal", "Investment earnings transferred from Prefunding"),
    ("other_collection_fees", "Other Collection Fees", "decimal", "Other collections on receivables — fees"),
    ("other_amounts_received", "Other Amounts Received", "decimal", "Other amounts received"),
    # ── Reserve & Prefunding ──
    ("reserve_fund_begin_bal", "Reserve Fund Beginning Balance", "decimal", "Beginning-of-period Reserve Fund balance"),
    ("reserve_fund_end_bal", "Reserve Fund End Balance", "decimal", "End-of-period Reserve Fund balance (tape-reported)"),
    ("reserve_fund_withdrawal", "Reserve Fund Withdrawal", "decimal", "Reserve fund withdrawal amount"),
    ("reserve_fund_deposit", "Reserve Fund Deposit", "decimal", "Reserve fund deposit from prefunding / other"),
    ("prefund_end_bal", "Prefunding End Balance", "decimal", "End-of-period prefunding account balance"),
    # ── Day-count reported on the servicer certificate (E19 on Servicer B) ──
    ("days_of_interest_reported", "Days of Interest (reported)", "integer", "Days of interest for the period as shown on the servicer certificate (typically 30 under 30/360 convention)"),
    # ── Reported distributions (Section IV bottom) — for validation ──
    ("owner_trustee_fee_tape", "Owner Trustee Fee (tape)", "decimal", "Owner Trustee Fee as reported"),
    ("regular_principal_alloc_tape", "Regular Principal Allocation (tape)", "decimal", "Reported Regular Allocation of Principal"),
    ("additional_fees_tape", "Additional Fees (tape)", "decimal", "Reported additional fees distribution"),
    ("certificateholders_pmt_tape", "Certificateholders Distribution (tape)", "decimal", "Reported amount to Certificateholders"),
    ("total_distributions_tape", "Total Distributions (tape)", "decimal", "Reported total distributions"),
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
    # Mappings for the servicer_b_example.xlsx report layout (May 2025 period).
    # "Sheet 1" (with space) — Servicer B's report format.
    #
    # ── I. Monthly Period Receivables Principal Balance Calculation ──
    ("beg_pool_balance", "Sheet 1", "K", 25, "Beginning of period Aggregate Principal Balance"),
    ("subsequent_receivables", "Sheet 1", "K", 26, "Subsequent Receivables added"),
    ("collections_outstanding", "Sheet 1", "J", 29, "Collections on Receivables outstanding"),
    ("collections_paid_off", "Sheet 1", "J", 30, "Collections on Receivables paid off"),
    ("receivables_liquidated", "Sheet 1", "J", 31, "Receivables becoming Liquidated"),
    ("receivables_purchased", "Sheet 1", "J", 32, "Receivables becoming Purchased"),
    ("receivables_adjustments", "Sheet 1", "J", 33, "Other Receivables adjustments"),
    ("cur_pool_bal", "Sheet 1", "K", 37, "End of period Aggregate Principal Balance"),
    # ── II. Monthly Note Balance Calculation (beginning balances, col E–J row 46) ──
    ("class_a_note_balance", "Sheet 1", "E", 46, "Class A Begin Balance"),
    ("class_b_note_balance", "Sheet 1", "F", 46, "Class B Begin Balance"),
    ("class_c_note_balance", "Sheet 1", "G", 46, "Class C Begin Balance"),
    ("class_d_note_balance", "Sheet 1", "H", 46, "Class D Begin Balance"),
    ("class_e_note_balance", "Sheet 1", "I", 46, "Class E Begin Balance"),
    ("class_f_note_balance", "Sheet 1", "J", 46, "Class F Begin Balance"),
    # ── Day count (E19 on Servicer B's certificate — "Days of Interest for Period") ──
    ("days_of_interest_reported", "Sheet 1", "E", 19, "Days of Interest for Period"),
    # ── III. Interest Distributable Amount (per-class, 30/360) ──
    ("class_a_note_rate", "Sheet 1", "F", 62, "Class A Note Rate"),
    ("class_b_note_rate", "Sheet 1", "F", 63, "Class B Note Rate"),
    ("class_c_note_rate", "Sheet 1", "F", 64, "Class C Note Rate"),
    ("class_d_note_rate", "Sheet 1", "F", 65, "Class D Note Rate"),
    ("class_e_note_rate", "Sheet 1", "F", 66, "Class E Note Rate"),
    ("class_f_note_rate", "Sheet 1", "F", 67, "Class F Note Rate"),
    ("class_a_interest_amount", "Sheet 1", "I", 62, "Class A Interest (reported)"),
    ("class_b_interest_amount", "Sheet 1", "I", 63, "Class B Interest (reported)"),
    ("class_c_interest_amount", "Sheet 1", "I", 64, "Class C Interest (reported)"),
    ("class_d_interest_amount", "Sheet 1", "I", 65, "Class D Interest (reported)"),
    ("class_e_interest_amount", "Sheet 1", "I", 66, "Class E Interest (reported)"),
    ("class_f_interest_amount", "Sheet 1", "I", 67, "Class F Interest (reported)"),
    # ── IV. Reconciliation of Collection Account — Available Funds components ──
    ("prin_collections", "Sheet 1", "J", 71, "Principal Collections"),
    ("int_collections", "Sheet 1", "J", 72, "Interest Collections"),
    ("liquidation_proceeds", "Sheet 1", "J", 73, "Liquidation Proceeds"),
    ("recoveries", "Sheet 1", "J", 74, "Recoveries"),
    ("purchase_amounts", "Sheet 1", "J", 75, "Purchase Amounts"),
    ("inv_earn_collection", "Sheet 1", "J", 76, "Investment Earnings (Collection)"),
    ("inv_earn_reserve", "Sheet 1", "J", 77, "Investment Earnings (Reserve)"),
    ("inv_earn_prefund", "Sheet 1", "J", 78, "Investment Earnings (Prefund)"),
    ("other_collection_fees", "Sheet 1", "J", 79, "Other Collection on Receivables Fees"),
    ("other_amounts_received", "Sheet 1", "J", 80, "Other Amounts Received"),
    ("total_available_funds", "Sheet 1", "K", 81, "Total Available Funds"),
    # ── IV. Distributions (fees + per-class interest + allocations, reported) ──
    ("svc_fee_tape", "Sheet 1", "J", 84, "Servicing Fee"),
    ("backup_svc_fee_tape", "Sheet 1", "J", 85, "Backup Servicing Fees"),
    ("trustee_fee_tape", "Sheet 1", "J", 86, "Indenture Trustee Fees"),
    ("owner_trustee_fee_tape", "Sheet 1", "J", 87, "Owner Trustee Fee"),
    ("regular_principal_alloc_tape", "Sheet 1", "J", 101, "Regular Allocation of Principal"),
    ("additional_fees_tape", "Sheet 1", "J", 103, "Additional fees"),
    ("certificateholders_pmt_tape", "Sheet 1", "J", 104, "To the Certificateholders"),
    ("total_distributions_tape", "Sheet 1", "K", 105, "Total Distributions"),
    # ── VI. Reserve Fund ──
    ("reserve_fund_begin_bal", "Sheet 1", "K", 124, "Reserve Fund Beginning Balance"),
    ("reserve_fund_deposit", "Sheet 1", "J", 126, "Reserve Fund Deposit"),
    ("reserve_fund_withdrawal", "Sheet 1", "J", 130, "Reserve Fund Withdrawal"),
    ("reserve_fund_end_bal", "Sheet 1", "K", 132, "Reserve Fund End Balance"),
    # ── VII. Overcollateralization ──
    ("prefund_end_bal", "Sheet 1", "J", 144, "Prefunding Account End Balance"),
    ("reported_oc", "Sheet 1", "K", 146, "OC Amount"),
    # end_available_funds is a placeholder for the tool's built-in waterfall reconciliation.
    # In Servicer B's format, Total Distributions ({61}) == Total Available Funds ({39}),
    # so map it to the Total Distributions cell for end-to-end cashflow checking.
    ("end_available_funds", "Sheet 1", "K", 105, "Total Distributions (= Available Funds out)"),
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

# Shared balances for B & C (same deal data, different report format).
# These are the **Beginning-of-period Note Balances** for the May 2025 period
# from servicer_b_example.xlsx: Classes A–C fully paid off, D partially paid down,
# E & F still at original balance.
DEAL_BC_BALANCES = {
    "A": Decimal("0"),
    "B": Decimal("0"),
    "C": Decimal("0"),
    "D": Decimal("25191696.50"),
    "E": Decimal("18600000"),
    "F": Decimal("17820000"),
}


# ══════════════════════════════════════════════════════════════════════════════
# Deal D: Servicer D Deal 1 — 5-class senior-to-junior waterfall (ABS Auto)
# Source: servicer_d_dec_2025.xlsx + servicer_d_jan_2026.xlsx
#
# Notable differences from Deal B:
#   • 5 classes (A–E) instead of 6.
#   • Only Class A amortizes (B–E are overcollateralized, non-amortizing).
#   • Servicing fee is MONTHLY (4%/12 × beg pool), not days-based.
#   • Long initial period (Oct 16 → Dec 12 = 56 days 30/360) seeded via a
#     stub prior run anchored to the closing date.
# ══════════════════════════════════════════════════════════════════════════════

DEAL_D_MAPPINGS = [
    # (variable_name, sheet, col, row, tape_label)
    # Sheet name is "Sheet1" (no space) — Servicer D's report format.

    # ── I. Pool balance movement ──
    ("beg_pool_balance",          "Sheet1", "K", 23, "Beginning of period Aggregate Principal Balance"),
    ("subsequent_receivables",    "Sheet1", "K", 24, "Subsequent Receivables added during the collection period"),
    ("collections_outstanding",   "Sheet1", "J", 27, "Collections on Receivables outstanding at end of period"),
    ("collections_paid_off",      "Sheet1", "J", 28, "Collections on Receivables paid off during period"),
    ("receivables_liquidated",    "Sheet1", "J", 29, "Receivables becoming Liquidated Receivables"),
    ("receivables_purchased",     "Sheet1", "J", 30, "Receivables becoming Purchased Receivables"),
    ("receivables_adjustments",   "Sheet1", "J", 31, "Other Receivables adjustments"),
    ("cur_pool_bal",              "Sheet1", "K", 35, "End of period Aggregate Principal Balance"),

    # ── II. Note balances (beginning, per class, row 44) ──
    ("class_a_note_balance", "Sheet1", "E", 44, "Class A Begin Balance"),
    ("class_b_note_balance", "Sheet1", "F", 44, "Class B Begin Balance"),
    ("class_c_note_balance", "Sheet1", "G", 44, "Class C Begin Balance"),
    ("class_d_note_balance", "Sheet1", "H", 44, "Class D Begin Balance"),
    ("class_e_note_balance", "Sheet1", "I", 44, "Class E Begin Balance"),

    # ── Day count (E17 on Servicer D's certificate) ──
    ("days_of_interest_reported", "Sheet1", "E", 17, "Days of Interest for Period"),

    # ── III. Interest (rate from F column, amount from I column, rows 59–63) ──
    ("class_a_note_rate", "Sheet1", "F", 59, "Class A Note Rate"),
    ("class_b_note_rate", "Sheet1", "F", 60, "Class B Note Rate"),
    ("class_c_note_rate", "Sheet1", "F", 61, "Class C Note Rate"),
    ("class_d_note_rate", "Sheet1", "F", 62, "Class D Note Rate"),
    ("class_e_note_rate", "Sheet1", "F", 63, "Class E Note Rate"),
    ("class_a_interest_amount", "Sheet1", "J", 85, "Class A Interest Distributable"),
    ("class_b_interest_amount", "Sheet1", "J", 87, "Class B Interest Distributable"),
    ("class_c_interest_amount", "Sheet1", "J", 89, "Class C Interest Distributable"),
    ("class_d_interest_amount", "Sheet1", "J", 91, "Class D Interest Distributable"),
    ("class_e_interest_amount", "Sheet1", "J", 93, "Class E Interest Distributable"),

    # ── IV. Fees + distributions ──
    ("svc_fee_tape",                "Sheet1", "J", 81,  "Servicing Fee"),
    ("backup_svc_fee_tape",         "Sheet1", "J", 82,  "Backup Servicing Fees"),
    ("trustee_fee_tape",            "Sheet1", "J", 83,  "Indenture Trustee Fees"),
    ("regular_principal_alloc_tape", "Sheet1", "J", 96, "Regular Allocation of Principal"),
    ("total_available_funds",       "Sheet1", "K", 78,  "Total Available Funds"),
    ("total_distributions_tape",    "Sheet1", "K", 100, "Total Distributions"),

    # ── VI. Reserve Fund ──
    ("reserve_fund_begin_bal",  "Sheet1", "K", 119, "Reserve Fund Beginning Balance"),
    ("reserve_fund_deposit",    "Sheet1", "J", 121, "Reserve Fund Deposit from Prefunding"),
    ("reserve_fund_withdrawal", "Sheet1", "J", 125, "Reserve Fund Withdrawal"),
    ("reserve_fund_end_bal",    "Sheet1", "K", 127, "Reserve Fund End Balance"),

    # ── VII. OC ──
    ("reported_oc", "Sheet1", "K", 153, "Overcollateralization Amount"),

    # end_available_funds — Total Distributions should equal Total Available Funds.
    ("end_available_funds", "Sheet1", "K", 100, "Total Distributions (= Available Funds out)"),
]

DEAL_D_TRANCHES = [
    # (class_label, cusip, regulation_type, note_rate, original_balance)
    ("A", "SVCD1A001", "combined", Decimal("0.0442"), Decimal("259350000")),
    ("B", "SVCD1B001", "combined", Decimal("0.0455"), Decimal("55250000")),
    ("C", "SVCD1C001", "combined", Decimal("0.0483"), Decimal("100750000")),
    ("D", "SVCD1D001", "combined", Decimal("0.0525"), Decimal("90020000")),
    ("E", "SVCD1E001", "combined", Decimal("0.0702"), Decimal("43880000")),
]

# First-period beginning balances (= originals, since Dec 2025 is the first run)
DEAL_D_BALANCES = {
    "A": Decimal("259350000"),
    "B": Decimal("55250000"),
    "C": Decimal("100750000"),
    "D": Decimal("90020000"),
    "E": Decimal("43880000"),
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
# Deal B comprehensive DAG — models the full servicer_b_example.xlsx calculation
# including pool balance reconciliation, 30/360 interest, full waterfall,
# reserve fund, and overcollateralization.
#
# Reserved names injected by the DagExecutor that this DAG relies on:
#   period_days_in_period_30_360   (from report_period + distribution rules)
#   deal_cutoff_pool_balance       (Committed Pool Balance)
#   deal_servicing_fee_pct         (annual rate; converted via 30/360)
#   deal_trustee_fee_monthly       (flat monthly amount)
#   deal_target_oc_pct             (15.50%)
#   deal_target_oc_floor_pct       (2.50% of cutoff pool)
#   deal_reserve_required_pct      (1.00%)
# ══════════════════════════════════════════════════════════════════════════════


def _build_servicer_b_comprehensive_dag():
    """DAG that models the full servicer_b_example.xlsx calculation.

    Organized by the Roman-numeral sections in the servicer's certificate:
      I.   Pool balance movement (7 inputs → end-of-period balance)
      II.  Interest calculation per class (30/360)
      III. Fee calculations (deal-constant-driven)
      IV.  Full distribution waterfall (21 line items, condensed)
      V.   Reserve Fund reconciliation
      VI.  Overcollateralization target + actual
      VII. Comprehensive validations
    """
    # ── Layout helpers (column centers per x-coord) ──
    COLS = {"a": 50, "b": 200, "c": 350, "d": 500, "e": 650, "f": 800, "mid": 425}

    dist_nodes: list[tuple] = []
    val_nodes: list[tuple] = []
    edges: list[tuple[str, str]] = []
    wf_order: dict[str, int] = {}

    # ──────────────────────────────────────────────────────────────
    # I. POOL BALANCE MOVEMENT
    # ──────────────────────────────────────────────────────────────
    pool_inputs = [
        ("beg_pool_balance_in", "Beginning Pool Balance", "beg_pool_balance"),
        ("subsequent_receivables_in", "Subsequent Receivables", "subsequent_receivables"),
        ("collections_outstanding_in", "Collections Outstanding", "collections_outstanding"),
        ("collections_paid_off_in", "Collections Paid Off", "collections_paid_off"),
        ("receivables_liquidated_in", "Receivables Liquidated", "receivables_liquidated"),
        ("receivables_purchased_in", "Receivables Purchased", "receivables_purchased"),
        ("receivables_adjustments_in", "Receivables Adjustments", "receivables_adjustments"),
        ("cur_pool_bal_in", "End Pool Balance (reported)", "cur_pool_bal"),
    ]
    for i, (key, name, _var) in enumerate(pool_inputs):
        dist_nodes.append((key, name, "input_value", None, None, COLS["a"] + (i % 4) * 150, 40 + (i // 4) * 60))

    dist_nodes.append((
        "total_monthly_principal",
        "Total Monthly Principal Amounts",
        "calculation",
        "collections_outstanding + collections_paid_off + receivables_liquidated + receivables_purchased + receivables_adjustments",
        None, COLS["mid"], 180,
    ))
    dist_nodes.append((
        "end_pool_balance_calc",
        "End Pool Balance (calc)",
        "calculation",
        "beg_pool_balance + subsequent_receivables - total_monthly_principal",
        None, COLS["mid"], 250,
    ))

    edges += [
        ("collections_outstanding_in", "total_monthly_principal"),
        ("collections_paid_off_in", "total_monthly_principal"),
        ("receivables_liquidated_in", "total_monthly_principal"),
        ("receivables_purchased_in", "total_monthly_principal"),
        ("receivables_adjustments_in", "total_monthly_principal"),
        ("beg_pool_balance_in", "end_pool_balance_calc"),
        ("subsequent_receivables_in", "end_pool_balance_calc"),
        ("total_monthly_principal", "end_pool_balance_calc"),
    ]

    # ──────────────────────────────────────────────────────────────
    # II. INTEREST CALCULATION PER CLASS (30/360)
    # Formula: balance × rate × days_30_360 / 360
    # ──────────────────────────────────────────────────────────────
    classes = ["a", "b", "c", "d", "e", "f"]
    for i, cls in enumerate(classes):
        x = COLS["a"] + i * 140
        key_bal = f"class_{cls}_note_balance_in"
        key_rate = f"class_{cls}_note_rate_in"
        key_int = f"class_{cls}_interest_calc"
        dist_nodes.append((key_bal, f"Class {cls.upper()} Begin Balance", "input_value", None, None, x, 360))
        dist_nodes.append((key_rate, f"Class {cls.upper()} Note Rate", "input_value", None, None, x, 420))
        dist_nodes.append((
            key_int,
            f"Class {cls.upper()} Interest (30/360 calc)",
            "calculation",
            f"class_{cls}_note_balance * class_{cls}_note_rate * period_days_in_period_30_360 / 360",
            None, x, 500,
        ))
        edges += [(key_bal, key_int), (key_rate, key_int)]

    # ──────────────────────────────────────────────────────────────
    # III. FEE CALCULATIONS (driven by deal constants)
    #   Servicing fee = pct × beginning pool × days / 360
    #   Trustee fee   = flat monthly amount
    #   Backup fee    = flat $2,500 for Deal B (per contract)
    # ──────────────────────────────────────────────────────────────
    dist_nodes.append((
        "svc_fee_calc",
        "Servicing Fee (calc)",
        "calculation",
        "deal_servicing_fee_pct * beg_pool_balance * period_days_in_period_30_360 / 360",
        None, COLS["a"], 620,
    ))
    dist_nodes.append((
        "trustee_fee_calc",
        "Trustee Fee (calc)",
        "calculation",
        "deal_trustee_fee_monthly",
        None, COLS["c"], 620,
    ))
    dist_nodes.append((
        "backup_svc_fee_calc",
        "Backup Servicing Fee (calc)",
        "calculation",
        "2500",
        None, COLS["b"], 620,
    ))
    edges += [("beg_pool_balance_in", "svc_fee_calc")]

    # ──────────────────────────────────────────────────────────────
    # IV. DISTRIBUTION WATERFALL
    # Condensed version of the 21-step Section IV waterfall:
    #   (1) Servicing Fee
    #   (2) Backup Servicing
    #   (3) Trustee Fee
    #   (4–9) Per-class interest (A→F)
    #   (10) Regular Principal Allocation (= whatever remains)
    # We use tape-reported fee values for actual payment (so "fee waivers"
    # like Deal B's $46k servicing-fee waiver flow through correctly), and
    # keep the computed values for validation.
    # ──────────────────────────────────────────────────────────────
    dist_nodes += [
        ("total_available_funds_in", "Total Available Funds", "input_value", None, None, COLS["mid"], 720),
        ("svc_fee_tape_in", "Servicing Fee (tape)", "input_value", None, None, COLS["a"], 720),
        ("backup_svc_fee_tape_in", "Backup Servicing Fee (tape)", "input_value", None, None, COLS["b"], 720),
        ("trustee_fee_tape_in", "Trustee Fee (tape)", "input_value", None, None, COLS["c"], 720),
    ]

    # Distributions are tape passthroughs — each one just pulls the amount
    # reported on the servicer's certificate. The Waterfall UI computes the
    # running balance (remaining-after-each-step) automatically from the
    # ordered distribution amounts; we don't manually cascade `MIN/MAX` in
    # each formula. Reconciliation against our independent verification
    # happens via each distribution's `comparison_variable`, which points at
    # the matching calc node (wired in `_populate_deal_b_metadata`).
    dist_nodes += [
        ("svc_fee_pmt", "Servicing Fee Pmt", "distribution", "svc_fee_tape", "SVC_FEE", COLS["a"], 820),
        ("backup_svc_fee_pmt", "Backup Servicing Fee Pmt", "distribution", "backup_svc_fee_tape", "BACKUP_FEE", COLS["b"], 820),
        ("trustee_fee_pmt", "Trustee Fee Pmt", "distribution", "trustee_fee_tape", "TRUSTEE_FEE", COLS["c"], 820),
    ]
    wf_order["svc_fee_pmt"] = 1
    wf_order["backup_svc_fee_pmt"] = 2
    wf_order["trustee_fee_pmt"] = 3
    edges += [
        ("svc_fee_tape_in", "svc_fee_pmt"),
        ("backup_svc_fee_tape_in", "backup_svc_fee_pmt"),
        ("trustee_fee_tape_in", "trustee_fee_pmt"),
    ]

    for i, cls in enumerate(classes):
        key = f"class_{cls}_int_pmt"
        wf_order[key] = 4 + i
        x = COLS["a"] + i * 140
        dist_nodes.append((
            key,
            f"Class {cls.upper()} Interest Pmt",
            "distribution",
            f"class_{cls}_interest_amount",
            f"INT_PMT_{cls.upper()}", x, 920,
        ))

    # Regular Principal Allocation — tape-reported residual.
    wf_order["regular_prin_alloc"] = 10
    dist_nodes.append((
        "regular_prin_alloc",
        "Regular Principal Allocation",
        "distribution",
        "regular_principal_alloc_tape",
        "PRIN_ALLOC", COLS["mid"], 1020,
    ))

    # ──────────────────────────────────────────────────────────────
    # V. RESERVE FUND RECONCILIATION
    # Required Amount = reserve_required_pct × cutoff_pool_balance
    # End Balance = Beg + Deposit + InvEarnings - Withdrawal
    # Deficiency = MAX(required - ending, 0)
    # ──────────────────────────────────────────────────────────────
    dist_nodes += [
        ("reserve_fund_begin_bal_in", "Reserve Fund Beginning Balance", "input_value", None, None, COLS["a"], 1120),
        ("reserve_fund_deposit_in", "Reserve Fund Deposit", "input_value", None, None, COLS["b"], 1120),
        ("reserve_fund_withdrawal_in", "Reserve Fund Withdrawal", "input_value", None, None, COLS["c"], 1120),
        ("inv_earn_reserve_in", "Investment Earnings (Reserve)", "input_value", None, None, COLS["d"], 1120),
    ]
    dist_nodes.append((
        "reserve_required_amt",
        "Reserve Required Amount",
        "calculation",
        "deal_reserve_required_pct * deal_cutoff_pool_balance",
        None, COLS["e"], 1120,
    ))
    dist_nodes.append((
        "reserve_fund_end_calc",
        "Reserve Fund End Balance (calc)",
        "calculation",
        "reserve_fund_begin_bal + reserve_fund_deposit - reserve_fund_withdrawal",
        None, COLS["b"], 1200,
    ))
    dist_nodes.append((
        "reserve_fund_deficiency",
        "Reserve Fund Deficiency",
        "calculation",
        "MAX(reserve_required_amt - reserve_fund_end_calc, 0)",
        None, COLS["e"], 1200,
    ))
    edges += [
        ("reserve_fund_begin_bal_in", "reserve_fund_end_calc"),
        ("reserve_fund_deposit_in", "reserve_fund_end_calc"),
        ("reserve_fund_withdrawal_in", "reserve_fund_end_calc"),
        ("reserve_required_amt", "reserve_fund_deficiency"),
        ("reserve_fund_end_calc", "reserve_fund_deficiency"),
    ]

    # ──────────────────────────────────────────────────────────────
    # VI. OVERCOLLATERALIZATION
    # Target = MAX(target_oc_pct × end_pool, target_oc_floor_pct × cutoff_pool)
    # Actual = end_pool + prefund_end - total_end_note_balance
    # ──────────────────────────────────────────────────────────────
    dist_nodes.append((
        "prefund_end_bal_in", "Prefunding End Balance", "input_value", None, None, COLS["a"], 1300,
    ))
    dist_nodes.append((
        "target_oc_amount",
        "Target OC Amount",
        "calculation",
        "MAX(deal_target_oc_pct * end_pool_balance_calc, deal_target_oc_floor_pct * deal_cutoff_pool_balance)",
        None, COLS["b"], 1300,
    ))
    # Total end note balance = beginning balances - the one regular-allocation payment.
    # (In this simplified model, regular_prin_alloc is applied to Class D — the
    # first non-zero class in the waterfall. A fully realistic model would pro-rate
    # across the lowest-outstanding class per the indenture; here we keep it
    # tractable for demo purposes.)
    dist_nodes.append((
        "total_end_note_balance",
        "Total End Note Balance",
        "calculation",
        "class_a_note_balance + class_b_note_balance + class_c_note_balance + class_d_note_balance + class_e_note_balance + class_f_note_balance - regular_prin_alloc",
        None, COLS["c"], 1300,
    ))
    dist_nodes.append((
        "oc_amount_calc",
        "OC Amount (calc)",
        "calculation",
        "end_pool_balance_calc + prefund_end_bal - total_end_note_balance",
        None, COLS["d"], 1300,
    ))
    edges += [
        ("end_pool_balance_calc", "target_oc_amount"),
        ("end_pool_balance_calc", "oc_amount_calc"),
        ("prefund_end_bal_in", "oc_amount_calc"),
        ("regular_prin_alloc", "total_end_note_balance"),
        ("total_end_note_balance", "oc_amount_calc"),
    ]

    # ──────────────────────────────────────────────────────────────
    # VII. VALIDATIONS
    # Each validation compares a calculated figure against a tape-reported one,
    # within a small absolute tolerance. The DagExecutor surfaces pass/fail on
    # the ExecutionStep record so the UI can highlight any breaks.
    # ──────────────────────────────────────────────────────────────
    TOL = Decimal("0.50")  # $0.50 absolute tolerance (rounding in the tape)

    # Days of interest — ties the tool's 30/360 day count to the servicer's
    # own "Days of Interest for Period" field (E19 on Servicer B). This is a
    # tight check (0 days tolerance) because the 30/360 rule is deterministic.
    val_nodes.append((
        "days_of_interest_check",
        "Days of Interest Check",
        "validation",
        "period_days_in_period_30_360",
        "days_of_interest_reported", Decimal("0"), COLS["a"], 1360,
    ))

    # End pool balance calc vs reported
    val_nodes.append((
        "end_pool_balance_check",
        "End Pool Balance Check",
        "validation",
        "end_pool_balance_calc",
        "cur_pool_bal", TOL, COLS["a"], 1420,
    ))
    # Per-class interest: calc vs reported
    for i, cls in enumerate(classes):
        val_nodes.append((
            f"class_{cls}_interest_check",
            f"Class {cls.upper()} Interest Check",
            "validation",
            f"class_{cls}_interest_calc",
            f"class_{cls}_interest_amount",
            TOL, COLS["a"] + i * 120, 1480,
        ))
    # Fee calcs vs reported (servicing fee may be waived, so use generous tolerance)
    val_nodes.append((
        "svc_fee_check",
        "Servicing Fee Check (pre-waiver)",
        "validation",
        "svc_fee_calc",
        "svc_fee_tape",
        Decimal("50000"), COLS["a"], 1540,  # allow waiver up to $50k
    ))
    val_nodes.append((
        "trustee_fee_check",
        "Trustee Fee Check",
        "validation",
        "trustee_fee_calc",
        "trustee_fee_tape",
        TOL, COLS["b"], 1540,
    ))
    val_nodes.append((
        "backup_svc_fee_check",
        "Backup Servicing Fee Check",
        "validation",
        "backup_svc_fee_calc",
        "backup_svc_fee_tape",
        TOL, COLS["c"], 1540,
    ))
    # Regular principal allocation calc vs reported
    val_nodes.append((
        "regular_prin_alloc_check",
        "Regular Principal Allocation Check",
        "validation",
        "regular_prin_alloc",
        "regular_principal_alloc_tape",
        TOL, COLS["d"], 1540,
    ))
    # Reserve fund end balance
    val_nodes.append((
        "reserve_fund_end_check",
        "Reserve Fund End Balance Check",
        "validation",
        "reserve_fund_end_calc",
        "reserve_fund_end_bal",
        TOL, COLS["a"], 1600,
    ))
    # OC amount
    val_nodes.append((
        "oc_amount_check",
        "OC Amount Check",
        "validation",
        "oc_amount_calc",
        "reported_oc",
        TOL, COLS["b"], 1600,
    ))
    # Total distribution cashflow reconciliation:
    # sum of all waterfall payments should equal Total Available Funds.
    val_nodes.append((
        "total_distribution_check",
        "Total Distribution Reconciliation",
        "validation",
        "svc_fee_pmt + backup_svc_fee_pmt + trustee_fee_pmt + class_a_int_pmt + class_b_int_pmt + class_c_int_pmt + class_d_int_pmt + class_e_int_pmt + class_f_int_pmt + regular_prin_alloc",
        "total_available_funds",
        TOL, COLS["c"], 1600,
    ))

    return dist_nodes, val_nodes, edges, wf_order


# ══════════════════════════════════════════════════════════════════════════════
# Servicer D Deal 1 — comprehensive DAG (5 classes, only A amortizes)
# ══════════════════════════════════════════════════════════════════════════════


def _build_servicer_d_comprehensive_dag():
    """DAG modelling servicer_d_dec_2025.xlsx + servicer_d_jan_2026.xlsx.

    Sections follow the tape's own structure:
      I.   Pool balance movement
      II.  Per-class interest (30/360)
      III. Monthly fees (NOT days-based — 4%/12 for svc, 0.015%/12 for backup)
      IV.  Distribution waterfall (tape passthroughs)
      V.   Reserve fund reconciliation
      VI.  Overcollateralization
      VII. Validations — standard + month-to-month rollforward checks
    """
    COLS = {"a": 50, "b": 200, "c": 350, "d": 500, "e": 650, "mid": 350}

    dist_nodes: list[tuple] = []
    val_nodes: list[tuple] = []
    edges: list[tuple[str, str]] = []
    wf_order: dict[str, int] = {}

    classes = ["a", "b", "c", "d", "e"]

    # ── I. Pool balance movement ──
    pool_inputs = [
        ("beg_pool_balance_in",          "Beginning Pool Balance"),
        ("subsequent_receivables_in",    "Subsequent Receivables"),
        ("collections_outstanding_in",   "Collections Outstanding"),
        ("collections_paid_off_in",      "Collections Paid Off"),
        ("receivables_liquidated_in",    "Receivables Liquidated"),
        ("receivables_purchased_in",     "Receivables Purchased"),
        ("receivables_adjustments_in",   "Receivables Adjustments"),
        ("cur_pool_bal_in",              "End Pool Balance (reported)"),
    ]
    for i, (key, name) in enumerate(pool_inputs):
        dist_nodes.append((key, name, "input_value", None, None,
                           COLS["a"] + (i % 4) * 150, 40 + (i // 4) * 60))

    dist_nodes.append((
        "total_monthly_principal_calc",
        "Total Monthly Principal (calc)",
        "calculation",
        "collections_outstanding + collections_paid_off + receivables_liquidated + receivables_purchased + receivables_adjustments",
        None, COLS["mid"], 180,
    ))
    dist_nodes.append((
        "end_pool_balance_calc",
        "End Pool Balance (calc)",
        "calculation",
        "beg_pool_balance + subsequent_receivables - total_monthly_principal_calc",
        None, COLS["mid"], 250,
    ))
    edges += [
        ("collections_outstanding_in", "total_monthly_principal_calc"),
        ("collections_paid_off_in",    "total_monthly_principal_calc"),
        ("receivables_liquidated_in",  "total_monthly_principal_calc"),
        ("receivables_purchased_in",   "total_monthly_principal_calc"),
        ("receivables_adjustments_in", "total_monthly_principal_calc"),
        ("beg_pool_balance_in",        "end_pool_balance_calc"),
        ("subsequent_receivables_in",  "end_pool_balance_calc"),
        ("total_monthly_principal_calc", "end_pool_balance_calc"),
    ]

    # ── II. Per-class interest (30/360) ──
    for i, cls in enumerate(classes):
        x = COLS["a"] + i * 140
        key_bal = f"class_{cls}_note_balance_in"
        key_rate = f"class_{cls}_note_rate_in"
        key_int = f"class_{cls}_interest_calc"
        dist_nodes.append((key_bal, f"Class {cls.upper()} Begin Balance", "input_value", None, None, x, 360))
        dist_nodes.append((key_rate, f"Class {cls.upper()} Note Rate", "input_value", None, None, x, 420))
        dist_nodes.append((
            key_int,
            f"Class {cls.upper()} Interest (30/360 calc)",
            "calculation",
            f"class_{cls}_note_balance * class_{cls}_note_rate * period_days_in_period_30_360 / 360",
            None, x, 500,
        ))
        edges += [(key_bal, key_int), (key_rate, key_int)]

    # ── III. Fees (monthly, not days-based) ──
    dist_nodes.append((
        "svc_fee_calc",
        "Servicing Fee (calc)",
        "calculation",
        "beg_pool_balance * deal_servicing_fee_pct / 12",
        None, COLS["a"], 620,
    ))
    dist_nodes.append((
        "backup_svc_fee_calc",
        "Backup Servicing Fee (calc)",
        "calculation",
        "beg_pool_balance * deal_backup_servicing_fee_pct / 12",
        None, COLS["b"], 620,
    ))
    dist_nodes.append((
        "trustee_fee_calc",
        "Trustee Fee (calc)",
        "calculation",
        "deal_trustee_fee_monthly",
        None, COLS["c"], 620,
    ))
    edges += [
        ("beg_pool_balance_in", "svc_fee_calc"),
        ("beg_pool_balance_in", "backup_svc_fee_calc"),
    ]

    # ── IV. Distribution waterfall ──
    dist_nodes += [
        ("total_available_funds_in",     "Total Available Funds", "input_value", None, None, COLS["mid"], 720),
        ("svc_fee_tape_in",              "Servicing Fee (tape)", "input_value", None, None, COLS["a"], 720),
        ("backup_svc_fee_tape_in",       "Backup Servicing Fee (tape)", "input_value", None, None, COLS["b"], 720),
        ("trustee_fee_tape_in",          "Trustee Fee (tape)", "input_value", None, None, COLS["c"], 720),
        ("regular_principal_alloc_tape_in", "Regular Principal Alloc (tape)", "input_value", None, None, COLS["d"], 720),
    ]

    # Tape passthrough distributions.
    dist_nodes += [
        ("svc_fee_pmt",        "Servicing Fee Pmt",        "distribution", "svc_fee_tape",        "SVC_FEE",    COLS["a"], 820),
        ("backup_svc_fee_pmt", "Backup Servicing Fee Pmt", "distribution", "backup_svc_fee_tape", "BACKUP_FEE", COLS["b"], 820),
        ("trustee_fee_pmt",    "Trustee Fee Pmt",          "distribution", "trustee_fee_tape",    "TRUSTEE_FEE",COLS["c"], 820),
    ]
    wf_order["svc_fee_pmt"] = 1
    wf_order["backup_svc_fee_pmt"] = 2
    wf_order["trustee_fee_pmt"] = 3
    edges += [
        ("svc_fee_tape_in",        "svc_fee_pmt"),
        ("backup_svc_fee_tape_in", "backup_svc_fee_pmt"),
        ("trustee_fee_tape_in",    "trustee_fee_pmt"),
    ]

    for i, cls in enumerate(classes):
        key = f"class_{cls}_int_pmt"
        wf_order[key] = 4 + i
        x = COLS["a"] + i * 140
        dist_nodes.append((
            key,
            f"Class {cls.upper()} Interest Pmt",
            "distribution",
            f"class_{cls}_interest_amount",
            f"INT_PMT_{cls.upper()}", x, 920,
        ))

    # Regular principal allocation — tape-reported residual (only class A amortizes).
    wf_order["regular_prin_alloc"] = 9
    dist_nodes.append((
        "regular_prin_alloc",
        "Regular Principal Allocation",
        "distribution",
        "regular_principal_alloc_tape",
        "PRIN_ALLOC", COLS["mid"], 1020,
    ))
    edges += [("regular_principal_alloc_tape_in", "regular_prin_alloc")]

    # ── V. Reserve fund ──
    dist_nodes += [
        ("reserve_fund_begin_bal_in",  "Reserve Fund Beginning Balance", "input_value", None, None, COLS["a"], 1120),
        ("reserve_fund_deposit_in",    "Reserve Fund Deposit",           "input_value", None, None, COLS["b"], 1120),
        ("reserve_fund_withdrawal_in", "Reserve Fund Withdrawal",        "input_value", None, None, COLS["c"], 1120),
    ]
    dist_nodes.append((
        "reserve_required_amt",
        "Reserve Required Amount",
        "calculation",
        "deal_reserve_required_pct * deal_cutoff_pool_balance",
        None, COLS["d"], 1120,
    ))
    dist_nodes.append((
        "reserve_fund_end_calc",
        "Reserve Fund End Balance (calc)",
        "calculation",
        "reserve_fund_begin_bal + reserve_fund_deposit - reserve_fund_withdrawal",
        None, COLS["b"], 1200,
    ))
    edges += [
        ("reserve_fund_begin_bal_in",  "reserve_fund_end_calc"),
        ("reserve_fund_deposit_in",    "reserve_fund_end_calc"),
        ("reserve_fund_withdrawal_in", "reserve_fund_end_calc"),
    ]

    # ── VI. Overcollateralization ──
    # Total end note balance = sum of each class's ending. Only class A amortizes
    # (down by regular_prin_alloc); B–E are non-amortizing (end = beg).
    dist_nodes.append((
        "class_a_end_note_balance_calc",
        "Class A End Note Balance (calc)",
        "calculation",
        "class_a_note_balance - regular_prin_alloc",
        None, COLS["a"], 1280,
    ))
    for cls in ["b", "c", "d", "e"]:
        dist_nodes.append((
            f"class_{cls}_end_note_balance_calc",
            f"Class {cls.upper()} End Note Balance (calc)",
            "calculation",
            f"class_{cls}_note_balance",  # non-amortizing
            None, COLS["a"] + (ord(cls) - ord("a")) * 140, 1280,
        ))
    edges += [("regular_prin_alloc", "class_a_end_note_balance_calc")]

    dist_nodes.append((
        "total_end_note_balance_calc",
        "Total End Note Balance",
        "calculation",
        "class_a_end_note_balance_calc + class_b_end_note_balance_calc + class_c_end_note_balance_calc + class_d_end_note_balance_calc + class_e_end_note_balance_calc",
        None, COLS["c"], 1360,
    ))
    for cls in classes:
        edges += [(f"class_{cls}_end_note_balance_calc", "total_end_note_balance_calc")]

    dist_nodes.append((
        "target_oc_amount",
        "Target OC Amount",
        "calculation",
        "MAX(deal_target_oc_pct * end_pool_balance_calc, deal_target_oc_floor_pct * deal_cutoff_pool_balance)",
        None, COLS["b"], 1360,
    ))
    dist_nodes.append((
        "oc_amount_calc",
        "OC Amount (calc)",
        "calculation",
        "end_pool_balance_calc - total_end_note_balance_calc",
        None, COLS["d"], 1360,
    ))
    edges += [
        ("end_pool_balance_calc",     "target_oc_amount"),
        ("end_pool_balance_calc",     "oc_amount_calc"),
        ("total_end_note_balance_calc", "oc_amount_calc"),
    ]

    # ── VII. Validations ──
    TOL = Decimal("0.50")

    # Days of interest — tight check against tape's E17.
    val_nodes.append((
        "days_of_interest_check",
        "Days of Interest Check",
        "validation",
        "period_days_in_period_30_360",
        "days_of_interest_reported", Decimal("0"), COLS["a"], 1440,
    ))

    # Per-class interest: calc vs tape.
    for i, cls in enumerate(classes):
        val_nodes.append((
            f"class_{cls}_interest_check",
            f"Class {cls.upper()} Interest Check",
            "validation",
            f"class_{cls}_interest_calc",
            f"class_{cls}_interest_amount",
            TOL, COLS["a"] + i * 120, 1500,
        ))

    # Fees (tight — no waivers expected).
    val_nodes.append((
        "svc_fee_check",
        "Servicing Fee Check",
        "validation",
        "svc_fee_calc",
        "svc_fee_tape",
        TOL, COLS["a"], 1560,
    ))
    val_nodes.append((
        "backup_svc_fee_check",
        "Backup Servicing Fee Check",
        "validation",
        "backup_svc_fee_calc",
        "backup_svc_fee_tape",
        TOL, COLS["b"], 1560,
    ))
    val_nodes.append((
        "trustee_fee_check",
        "Trustee Fee Check",
        "validation",
        "trustee_fee_calc",
        "trustee_fee_tape",
        TOL, COLS["c"], 1560,
    ))

    # Pool + OC.
    val_nodes.append((
        "end_pool_balance_check",
        "End Pool Balance Check",
        "validation",
        "end_pool_balance_calc",
        "cur_pool_bal", TOL, COLS["a"], 1620,
    ))
    val_nodes.append((
        "oc_amount_check",
        "OC Amount Check",
        "validation",
        "oc_amount_calc",
        "reported_oc", TOL, COLS["b"], 1620,
    ))

    # Total cashflow reconciliation.
    val_nodes.append((
        "total_distribution_check",
        "Total Distribution Reconciliation",
        "validation",
        "svc_fee_pmt + backup_svc_fee_pmt + trustee_fee_pmt + class_a_int_pmt + class_b_int_pmt + class_c_int_pmt + class_d_int_pmt + class_e_int_pmt + regular_prin_alloc",
        "total_available_funds", TOL, COLS["c"], 1620,
    ))

    # ── Rollforward checks ──
    # These are the heart of this deal — they compare each month's tape-reported
    # beginning balance to the prior run's computed ending. On the first run,
    # the "_prior" values come from default_prior_value on the calc nodes
    # (seeded in _populate_deal_d_metadata).
    rollforward_tol = Decimal("1.00")  # $1 tolerance for rounding
    val_nodes.append((
        "rollforward_pool_balance_check",
        "Rollforward: Pool Balance",
        "validation",
        "PRIOR(end_pool_balance_calc)",
        "beg_pool_balance", rollforward_tol, COLS["a"], 1700,
    ))
    for i, cls in enumerate(classes):
        val_nodes.append((
            f"rollforward_class_{cls}_balance_check",
            f"Rollforward: Class {cls.upper()} Balance",
            "validation",
            f"PRIOR(class_{cls}_end_note_balance_calc)",
            f"class_{cls}_note_balance",
            rollforward_tol, COLS["a"] + i * 120, 1760,
        ))
    val_nodes.append((
        "rollforward_reserve_check",
        "Rollforward: Reserve Fund",
        "validation",
        "PRIOR(reserve_fund_end_calc)",
        "reserve_fund_begin_bal", rollforward_tol, COLS["a"], 1820,
    ))

    return dist_nodes, val_nodes, edges, wf_order


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
# Deal B metadata — static fields, deal constants, trust accounts
#
# Values sourced from servicer_b_example.xlsx (Servicer B Deal 7).
# ══════════════════════════════════════════════════════════════════════════════


def _populate_deal_b_metadata(db: Session, deal: Deal) -> None:
    from datetime import date
    from app.models.deal import DealAccount
    from app.models.processing import ProcessingRun

    print("  ── Deal B metadata ──")

    # Static deal info
    deal.issuer_name = "Servicer B Deal 7"
    deal.deal_key = "SVCB7"
    deal.reg_ab = True
    deal.equity_cusips_involved = False
    deal.closing_date = date(2022, 8, 11)  # Initial Purchase Closing Date
    deal.initial_cutoff_date = date(2022, 8, 3)  # Initial Purchase Cutoff
    deal.initial_distribution_date = date(2022, 9, 13)  # First payment date
    deal.cutoff_pool_balance = Decimal("310000114.34")  # Committed Pool Balance
    deal.distribution_day_of_month = 13
    deal.determination_business_days_before = 4

    # Deal-level numeric constants (auto-injected into DAG context)
    deal.servicing_fee_pct = Decimal("0.04")  # 4.00% annual (30/360)
    deal.backup_servicing_fee_pct = None  # Deal B uses a flat $2,500 instead
    deal.trustee_fee_monthly = Decimal("750")
    deal.target_oc_pct = Decimal("0.155")  # 15.50% of current pool
    deal.target_oc_floor_pct = Decimal("0.025")  # 2.50% of cutoff pool
    deal.target_oc_floor_amount = None  # Deal B uses % floor, not $ floor
    deal.reserve_required_pct = Decimal("0.01")  # 1.00% of Committed Pool Balance

    db.flush()
    print("  + static fields, distribution-date rules, and 7 deal constants populated")

    # Wire up "compare against" on each distribution. These point at CALC
    # nodes — each distribution (which is a tape passthrough) is reconciled
    # against our independent recalculation:
    #   - svc_fee_pmt (tape)  vs  svc_fee_calc (rate × beg_pool × days / 360)
    #   - class_d_int_pmt (tape)  vs  class_d_interest_calc (bal × rate × days / 360)
    #   - ...and so on.
    # When diff > tolerance, the discrepancy surfaces in the Waterfall UI
    # (e.g. the $46,903.09 servicing-fee waiver on Servicer B's May 2025 period).
    from app.models.dag import DagNode

    distribution_compare_targets = {
        "svc_fee_pmt": "svc_fee_calc",
        "backup_svc_fee_pmt": "backup_svc_fee_calc",
        "trustee_fee_pmt": "trustee_fee_calc",
        "class_a_int_pmt": "class_a_interest_calc",
        "class_b_int_pmt": "class_b_interest_calc",
        "class_c_int_pmt": "class_c_interest_calc",
        "class_d_int_pmt": "class_d_interest_calc",
        "class_e_int_pmt": "class_e_interest_calc",
        "class_f_int_pmt": "class_f_interest_calc",
        # Regular principal allocation has no per-contract calc (it's the
        # residual after everything else). Leave it unset — the waterfall
        # display still shows the tape-paid amount and running remainder.
    }
    wired = 0
    for node_key, compare_key in distribution_compare_targets.items():
        node = (
            db.query(DagNode)
            .filter(DagNode.deal_id == deal.id, DagNode.key == node_key)
            .first()
        )
        if node is not None and not node.comparison_variable:
            node.comparison_variable = compare_key
            wired += 1
    if wired:
        db.flush()
        print(f"  + {wired} waterfall compare-against targets wired")

    # Trust accounts — Servicer B Deal 7 maintains the standard 4 indenture
    # accounts plus a prefunding account during the revolving period.
    existing = db.query(DealAccount).filter(DealAccount.deal_id == deal.id).count()
    if existing == 0:
        accounts = [
            ("Main", "SVCB7-MAIN-0001"),
            ("Collection", "SVCB7-COLL-0002"),
            ("Note Payment", "SVCB7-NOTE-0003"),
            ("Reserve", "SVCB7-RSRV-0004"),
            ("Prefunding", "SVCB7-PREF-0005"),
        ]
        for pos, (label, number) in enumerate(accounts, start=1):
            db.add(DealAccount(deal_id=deal.id, label=label, account_number=number, position=pos))
        db.flush()
        print(f"  + {len(accounts)} trust accounts")
    else:
        print(f"  = {existing} trust accounts already exist")

    # Stub "prior" run anchor — Servicer B's example tape is the June 2025
    # distribution for the May 2025 collection period. The DagExecutor needs
    # a prior run to compute `period_days_in_period_30_360` correctly (30 days
    # since the previous distribution). We seed a minimal completed run for
    # April→May 2025 with just the distribution_date populated.
    existing_prior = (
        db.query(ProcessingRun)
        .filter(ProcessingRun.deal_id == deal.id, ProcessingRun.report_period == "2025-05")
        .first()
    )
    if existing_prior is None:
        prior = ProcessingRun(
            deal_id=deal.id,
            report_period="2025-05",
            status="completed",
            created_by="root",
            distribution_date=date(2025, 5, 13),
            determination_date=date(2025, 5, 7),
            days_in_period_actual=30,
            days_in_period_30_360=30,
        )
        db.add(prior)
        db.flush()
        print("  + prior run stub for 2025-05 (anchors June 2025 run to 30-day period)")


def _populate_deal_d_metadata(db: Session, deal: Deal) -> None:
    """Deal D static fields, numeric constants, compare targets,
    default priors (for first-month rollforward), and prior-run stub."""
    from datetime import date
    from app.models.deal import DealAccount
    from app.models.dag import DagNode
    from app.models.processing import ProcessingRun

    print("  ── Deal D metadata ──")

    # Static fields
    deal.issuer_name = "Servicer D Deal 1"
    deal.deal_key = "SVCD1"
    deal.reg_ab = True
    deal.equity_cusips_involved = False
    deal.closing_date = date(2025, 10, 16)
    deal.initial_cutoff_date = date(2025, 10, 7)
    deal.initial_distribution_date = date(2025, 10, 16)
    deal.cutoff_pool_balance = Decimal("650002906.58")  # total committed (initial + subsequent)
    deal.distribution_day_of_month = 12
    deal.determination_business_days_before = 4

    # Waterfall config
    deal.waterfall_starting_var = "total_available_funds"
    deal.waterfall_ending_var = "end_available_funds"
    deal.waterfall_tolerance = Decimal("0.50")

    # Deal-level numeric constants (auto-injected into DAG context).
    # Servicer D bills fees MONTHLY (annual pct / 12), NOT days-based.
    deal.servicing_fee_pct = Decimal("0.04")            # 4.00% annual
    deal.backup_servicing_fee_pct = Decimal("0.00015")  # 0.015% annual
    deal.trustee_fee_monthly = Decimal("750")
    deal.target_oc_pct = Decimal("0.223")               # 22.30% of current pool
    deal.target_oc_floor_pct = Decimal("0.025")         # 2.50% of committed pool
    deal.target_oc_floor_amount = None
    deal.reserve_required_pct = Decimal("0.01")         # 1.00% of committed pool

    db.flush()
    print("  + static fields + 6 deal constants populated")

    # Distribution compare targets — each tape passthrough points at its calc node.
    distribution_compare_targets = {
        "svc_fee_pmt":        "svc_fee_calc",
        "backup_svc_fee_pmt": "backup_svc_fee_calc",
        "trustee_fee_pmt":    "trustee_fee_calc",
        "class_a_int_pmt":    "class_a_interest_calc",
        "class_b_int_pmt":    "class_b_interest_calc",
        "class_c_int_pmt":    "class_c_interest_calc",
        "class_d_int_pmt":    "class_d_interest_calc",
        "class_e_int_pmt":    "class_e_interest_calc",
        # regular_prin_alloc intentionally unset (no independent calc — it's
        # a tape-reported residual).
    }
    wired = 0
    for node_key, compare_key in distribution_compare_targets.items():
        node = (
            db.query(DagNode)
            .filter(DagNode.deal_id == deal.id, DagNode.key == node_key)
            .first()
        )
        if node is not None and not node.comparison_variable:
            node.comparison_variable = compare_key
            wired += 1
    if wired:
        db.flush()
        print(f"  + {wired} waterfall compare-against targets wired")

    # Default prior values — bootstrap the first-month rollforward validations.
    # On the first run (Dec 2025), PriorMonthService pulls these as
    # `<node_key>_prior` into the DAG context. On subsequent runs, actual
    # prior execution results override them.
    default_priors = {
        "end_pool_balance_calc":           Decimal("455000312.51"),   # initial cutoff balance
        "class_a_end_note_balance_calc":   Decimal("259350000"),
        "class_b_end_note_balance_calc":   Decimal("55250000"),
        "class_c_end_note_balance_calc":   Decimal("100750000"),
        "class_d_end_note_balance_calc":   Decimal("90020000"),
        "class_e_end_note_balance_calc":   Decimal("43880000"),
        "reserve_fund_end_calc":           Decimal("4550003.13"),     # Dec's tape-reported beginning
    }
    defaulted = 0
    for node_key, val in default_priors.items():
        node = (
            db.query(DagNode)
            .filter(DagNode.deal_id == deal.id, DagNode.key == node_key)
            .first()
        )
        if node is not None and node.default_prior_value is None:
            node.default_prior_value = val
            defaulted += 1
    if defaulted:
        db.flush()
        print(f"  + {defaulted} default_prior_value bootstraps")

    # Trust accounts
    existing = db.query(DealAccount).filter(DealAccount.deal_id == deal.id).count()
    if existing == 0:
        accounts = [
            ("Main",       "SVCD1-MAIN-0001"),
            ("Collection", "SVCD1-COLL-0002"),
            ("Note Payment", "SVCD1-NOTE-0003"),
            ("Reserve",    "SVCD1-RSRV-0004"),
            ("Prefunding", "SVCD1-PREF-0005"),
        ]
        for pos, (label, number) in enumerate(accounts, start=1):
            db.add(DealAccount(deal_id=deal.id, label=label, account_number=number, position=pos))
        db.flush()
        print(f"  + {len(accounts)} trust accounts")

    # Prior-run stub — anchors the Dec 2025 run's 30/360 day count to the
    # 2025-10-16 closing date (giving 56 days for the initial period).
    existing_prior = (
        db.query(ProcessingRun)
        .filter(ProcessingRun.deal_id == deal.id, ProcessingRun.report_period == "2025-11")
        .first()
    )
    if existing_prior is None:
        prior = ProcessingRun(
            deal_id=deal.id,
            report_period="2025-11",
            status="completed",
            created_by="root",
            distribution_date=date(2025, 10, 16),
            determination_date=date(2025, 10, 16),
            days_in_period_actual=0,
            days_in_period_30_360=0,
        )
        db.add(prior)
        db.flush()
        print("  + prior run stub for 2025-11 (anchors Dec 2025 run to 56-day initial period)")


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════


def run_seed() -> None:
    Base.metadata.create_all(engine)
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

        # Deal B: Servicer B Deal 7 — comprehensive model of servicer_b_example.xlsx
        sb_dist, sb_val, sb_edges, sb_wf = _build_servicer_b_comprehensive_dag()
        deal_b = _seed_deal(
            db,
            deal_name="Servicer B Deal 7",
            servicer=servicers["Servicer B"],
            product_type="ABS Auto",
            created_by="jane.chen",
            mappings=DEAL_B_MAPPINGS,
            tranches=DEAL_B_TRANCHES,
            balances=DEAL_BC_BALANCES,
            dist_nodes=sb_dist,
            validation_nodes=sb_val,
            edges=sb_edges,
            waterfall_order=sb_wf,
            variables=variables,
            balance_period="2025-05",  # May 2025 is the sample report period
        )
        _populate_deal_b_metadata(db, deal_b)

        # Deal C: Servicer C Deal 7 — reuses the simpler 6-class DAG.
        # (Deal B is the comprehensive example; Deal C keeps a lighter model
        # to demonstrate that multiple DAG shapes coexist per servicer.)
        bc_dist, bc_val, bc_edges, bc_wf = _build_6class_dag()
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

        # Deal D: Servicer D Deal 1 — 5-class senior-to-junior waterfall.
        # Used to demonstrate month-to-month rollforward (Dec 2025 → Jan 2026).
        sd_dist, sd_val, sd_edges, sd_wf = _build_servicer_d_comprehensive_dag()
        deal_d = _seed_deal(
            db,
            deal_name="Servicer D Deal 1",
            servicer=servicers["Servicer D"],
            product_type="ABS Auto",
            created_by="jane.chen",
            mappings=DEAL_D_MAPPINGS,
            tranches=DEAL_D_TRANCHES,
            balances=DEAL_D_BALANCES,
            dist_nodes=sd_dist,
            validation_nodes=sd_val,
            edges=sd_edges,
            waterfall_order=sd_wf,
            variables=variables,
            balance_period="2025-11",
        )
        _populate_deal_d_metadata(db, deal_d)

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
