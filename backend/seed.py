"""Seed the database with users, servicers, variables, and 3 demo deals.

Run once after first startup:
    python seed.py
"""

import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import engine, Base, SessionLocal
from app.models import *  # noqa: F401,F403
from app.dag.service import DagService
from app.schemas.dag import DagNodeCreate, DagEdgeCreate


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # ── Users ──
    users_data = [
        ("admin", "Admin", "admin"),
        ("analyst1", "Jane Chen", "analyst"),
        ("analyst2", "Mike Park", "analyst"),
    ]
    try:
        current_user = os.getlogin()
    except OSError:
        current_user = os.environ.get("USERNAME", os.environ.get("USER", "dev"))
    users_data.append((current_user, current_user.title(), "analytics"))

    for username, display, role in users_data:
        if not db.query(User).filter(User.username == username).first():
            db.add(User(username=username, display_name=display, role=role))
            print(f"  + User: {username} ({role})")
    db.flush()

    analytics_user = db.query(User).filter(User.role == "analytics").first()
    created_by = analytics_user.username if analytics_user else "system"

    # ── Servicers ──
    servicers_map: dict[str, Servicer] = {}
    for name, code in [
        ("Servicer A", "SVCA"),
        ("Servicer B", "SVCB"),
        ("Servicer C", "SVCC"),
        ("Wells Fargo", "WF"),
        ("Nationstar", "NSM"),
        ("Freddie Mac", "FMAC"),
    ]:
        existing = db.query(Servicer).filter(Servicer.short_code == code).first()
        if not existing:
            existing = Servicer(name=name, short_code=code)
            db.add(existing)
            db.flush()
            print(f"  + Servicer: {name} ({code})")
        servicers_map[code] = existing

    # ── System Variables ──
    sys_vars: dict[str, VariableDefinition] = {}
    system_var_defs = [
        ("beg_pool_bal", "Beginning Pool Balance", "decimal"),
        ("end_pool_bal", "End Pool Balance", "decimal"),
        ("total_principal", "Total Monthly Principal", "decimal"),
        ("total_collections", "Total Collections", "decimal"),
        ("int_collections", "Interest Collections", "decimal"),
        ("prin_collections", "Principal Collections", "decimal"),
        ("svc_fee", "Servicing Fee", "decimal"),
        ("svc_fee_rate", "Servicing Fee Rate", "percentage"),
        ("trustee_fee", "Trustee Fee", "decimal"),
        ("backup_svc_fee", "Backup Servicer Fee", "decimal"),
        ("pool_factor", "Pool Factor", "decimal"),
        ("oc_amount", "Overcollateralization Amount", "decimal"),
        ("oc_target_pct", "Target OC Percentage", "percentage"),
        ("reserve_fund_bal", "Reserve Fund Balance", "decimal"),
        ("reserve_fund_req", "Reserve Fund Required", "decimal"),
        ("months_seasoned", "Months Seasoned", "integer"),
        ("days_in_period", "Days in Collection Period", "integer"),
        ("days_of_interest", "Days of Interest", "integer"),
        ("orig_pool_bal", "Original Pool Balance", "decimal"),
        ("investment_earnings", "Investment Earnings", "decimal"),
    ]
    for name, display, dtype in system_var_defs:
        existing = db.query(VariableDefinition).filter(
            VariableDefinition.name == name, VariableDefinition.scope == "system"
        ).first()
        if not existing:
            existing = VariableDefinition(
                name=name, display_name=display, data_type=dtype, scope="system"
            )
            db.add(existing)
            db.flush()
            print(f"  + Variable: {name}")
        sys_vars[name] = existing

    # ── Helper to create a deal-scoped variable ──
    def make_deal_var(deal: Deal, name: str, display: str, dtype: str = "decimal") -> VariableDefinition:
        existing = db.query(VariableDefinition).filter(
            VariableDefinition.name == name,
            VariableDefinition.scope == "deal",
            VariableDefinition.deal_id == deal.id,
        ).first()
        if not existing:
            existing = VariableDefinition(
                name=name, display_name=display, data_type=dtype,
                scope="deal", deal_id=deal.id,
            )
            db.add(existing)
            db.flush()
        return existing

    # ================================================================
    # DEAL 1: Servicer A Deal 3  (ABS Auto, 4 classes, single sheet)
    # ================================================================
    print("\n  Setting up Deal 1: Servicer A Deal 3...")
    svca = servicers_map["SVCA"]
    deal1 = db.query(Deal).filter(Deal.name == "SVCA 2022-3").first()
    if not deal1:
        deal1 = Deal(name="SVCA 2022-3", servicer_id=svca.id, product_type="ABS Auto",
                     status="active", created_by=created_by)
        db.add(deal1)
        db.flush()

    # Deal-specific variables for Servicer A
    d1_vars = {
        "eligible_contract_bal": make_deal_var(deal1, "eligible_contract_bal", "Eligible Contract Balance"),
        "eligible_loan_bal": make_deal_var(deal1, "eligible_loan_bal", "Eligible Loan Balance"),
        "class_a_collateral": make_deal_var(deal1, "class_a_collateral", "Class A Collateral Amount"),
        "net_dealer_collections": make_deal_var(deal1, "net_dealer_collections", "Net Dealer Collections"),
        "total_available_funds": make_deal_var(deal1, "total_available_funds", "Total Available Funds"),
        "class_a_interest": make_deal_var(deal1, "class_a_interest", "Class A Interest Distributable"),
        "class_b_interest": make_deal_var(deal1, "class_b_interest", "Class B Interest Distributable"),
        "class_c_interest": make_deal_var(deal1, "class_c_interest", "Class C Interest Distributable"),
        "class_d_interest": make_deal_var(deal1, "class_d_interest", "Class D Interest Distributable"),
        "class_a_principal": make_deal_var(deal1, "class_a_principal", "Class A Principal Distributable"),
        "class_b_principal": make_deal_var(deal1, "class_b_principal", "Class B Principal Distributable"),
        "reserve_acct_bal": make_deal_var(deal1, "reserve_acct_bal", "Reserve Account Balance"),
    }

    # Cell mappings for Servicer A (single sheet "Sheet 1", values in col J)
    d1_mappings = [
        (sys_vars["beg_pool_bal"], "Sheet 1", "J", 18, "Outstanding Balance of Dealer Contracts"),
        (d1_vars["eligible_contract_bal"], "Sheet 1", "J", 24, "Eligible Dealer Contracts Balance"),
        (d1_vars["eligible_loan_bal"], "Sheet 1", "J", 36, "Eligible Dealer Loans Balance"),
        (d1_vars["class_a_collateral"], "Sheet 1", "J", 86, "Class A Collateral Amount"),
        (sys_vars["total_collections"], "Sheet 1", "J", 127, "Total Collections Remitted"),
        (sys_vars["int_collections"], "Sheet 1", "J", 129, "Income Collections"),
        (sys_vars["prin_collections"], "Sheet 1", "J", 130, "Principal Collections"),
        (d1_vars["net_dealer_collections"], "Sheet 1", "J", 133, "Net Dealer Collections"),
        (d1_vars["total_available_funds"], "Sheet 1", "J", 147, "Total Available Funds"),
        (sys_vars["svc_fee"], "Sheet 1", "J", 151, "Servicing Fee"),
        (sys_vars["backup_svc_fee"], "Sheet 1", "J", 153, "Backup Servicing Fee"),
        (sys_vars["trustee_fee"], "Sheet 1", "J", 157, "Indenture Trustee Fee"),
        (d1_vars["class_a_interest"], "Sheet 1", "J", 159, "Class A Interest Distributable"),
        (d1_vars["class_b_interest"], "Sheet 1", "J", 163, "Class B Interest Distributable"),
        (d1_vars["class_c_interest"], "Sheet 1", "J", 167, "Class C Interest Distributable"),
        (d1_vars["class_d_interest"], "Sheet 1", "J", 171, "Class D Interest Distributable"),
        (d1_vars["class_a_principal"], "Sheet 1", "J", 175, "Class A Principal Distributable"),
        (d1_vars["class_b_principal"], "Sheet 1", "J", 177, "Class B Principal Distributable"),
        (d1_vars["reserve_acct_bal"], "Sheet 1", "J", 197, "Reserve Account Balance"),
        (sys_vars["investment_earnings"], "Sheet 1", "J", 139, "Investment Earnings"),
    ]
    for var, sheet, col, row, tape_label in d1_mappings:
        if not db.query(VariableMapping).filter(
            VariableMapping.deal_id == deal1.id, VariableMapping.variable_id == var.id
        ).first():
            db.add(VariableMapping(
                deal_id=deal1.id, variable_id=var.id,
                sheet_name=sheet, column_letter=col, row_number=row, tape_label=tape_label,
            ))
    db.flush()

    # Tranches for Deal 1: A, B, C, D
    for label, rate, orig in [
        ("A", "0.0", "151710000"), ("B", "0.0", "69770000"),
        ("C", "0.0", "77520000"), ("D", "0.0", "90900000"),
    ]:
        if not db.query(DealTranche).filter(
            DealTranche.deal_id == deal1.id, DealTranche.class_label == label
        ).first():
            db.add(DealTranche(
                deal_id=deal1.id, class_label=label, regulation_type="combined",
                note_rate=Decimal(rate), original_balance=Decimal(orig),
            ))
    db.flush()

    # ================================================================
    # DEAL 2: Servicer B Deal 7 (ABS Auto, 6 classes, numeric cells)
    # ================================================================
    print("  Setting up Deal 2: Servicer B Deal 7...")
    svcb = servicers_map["SVCB"]
    deal2 = db.query(Deal).filter(Deal.name == "SVCB 2022-7").first()
    if not deal2:
        deal2 = Deal(name="SVCB 2022-7", servicer_id=svcb.id, product_type="ABS Auto",
                     status="active", created_by=created_by)
        db.add(deal2)
        db.flush()

    # Deal-specific variables for Servicer B
    d2_vars = {
        "class_d_int_dist": make_deal_var(deal2, "class_d_int_dist", "Class D Interest Distributable"),
        "class_e_int_dist": make_deal_var(deal2, "class_e_int_dist", "Class E Interest Distributable"),
        "class_f_int_dist": make_deal_var(deal2, "class_f_int_dist", "Class F Interest Distributable"),
        "regular_alloc_prin": make_deal_var(deal2, "regular_alloc_prin", "Regular Allocation of Principal"),
        "total_distributions": make_deal_var(deal2, "total_distributions", "Total Distributions"),
        "req_pmt_amount": make_deal_var(deal2, "req_pmt_amount", "Required Payment Amount"),
        "liquidation_proceeds": make_deal_var(deal2, "liquidation_proceeds", "Liquidation Proceeds"),
        "recoveries": make_deal_var(deal2, "recoveries", "Recoveries"),
    }

    # Cell mappings for Servicer B ("Sheet 1", mix of J and K cols)
    d2_mappings = [
        (sys_vars["beg_pool_bal"], "Sheet 1", "K", 25, "Beginning Aggregate Principal Balance"),
        (sys_vars["end_pool_bal"], "Sheet 1", "K", 37, "End of period Aggregate Principal Balance"),
        (sys_vars["total_principal"], "Sheet 1", "K", 35, "Total Monthly Principal Amounts"),
        (sys_vars["pool_factor"], "Sheet 1", "K", 39, "Pool Factor"),
        (sys_vars["months_seasoned"], "Sheet 1", "E", 21, "Months Seasoned"),
        (sys_vars["days_of_interest"], "Sheet 1", "E", 19, "Days of Interest for Period"),
        (sys_vars["days_in_period"], "Sheet 1", "E", 20, "Days in Collection Period"),
        (sys_vars["orig_pool_bal"], "Sheet 1", "K", 21, "Original Pool Balance"),
        (sys_vars["prin_collections"], "Sheet 1", "J", 71, "Principal Collections (net)"),
        (sys_vars["int_collections"], "Sheet 1", "J", 72, "Interest Collections"),
        (d2_vars["liquidation_proceeds"], "Sheet 1", "J", 73, "Liquidation Proceeds"),
        (d2_vars["recoveries"], "Sheet 1", "J", 74, "Recoveries"),
        (sys_vars["total_collections"], "Sheet 1", "K", 81, "Total Available Funds"),
        (sys_vars["svc_fee"], "Sheet 1", "J", 84, "Servicing Fee"),
        (sys_vars["backup_svc_fee"], "Sheet 1", "J", 85, "Backup Servicing Fees"),
        (sys_vars["trustee_fee"], "Sheet 1", "J", 86, "Indenture Trustee Fees"),
        (d2_vars["class_d_int_dist"], "Sheet 1", "J", 94, "Class D Interest Distributable"),
        (d2_vars["class_e_int_dist"], "Sheet 1", "J", 96, "Class E Interest Distributable"),
        (d2_vars["class_f_int_dist"], "Sheet 1", "J", 98, "Class F Interest Distributable"),
        (d2_vars["regular_alloc_prin"], "Sheet 1", "J", 101, "Regular Allocation of Principal"),
        (d2_vars["total_distributions"], "Sheet 1", "K", 105, "Total Distributions"),
        (d2_vars["req_pmt_amount"], "Sheet 1", "K", 106, "Required Payment Amount"),
        (sys_vars["oc_amount"], "Sheet 1", "K", 146, "Overcollateralization Amount"),
        (sys_vars["oc_target_pct"], "Sheet 1", "K", 147, "Overcollateralization %"),
        (sys_vars["reserve_fund_bal"], "Sheet 1", "K", 132, "End of period Reserve Fund"),
        (sys_vars["reserve_fund_req"], "Sheet 1", "K", 122, "Reserve Fund Required Amount"),
        (sys_vars["investment_earnings"], "Sheet 1", "J", 76, "Investment Earnings - Collection Account"),
    ]
    for var, sheet, col, row, tape_label in d2_mappings:
        if not db.query(VariableMapping).filter(
            VariableMapping.deal_id == deal2.id, VariableMapping.variable_id == var.id
        ).first():
            db.add(VariableMapping(
                deal_id=deal2.id, variable_id=var.id,
                sheet_name=sheet, column_letter=col, row_number=row, tape_label=tape_label,
            ))
    db.flush()

    # Tranches for Deal 2: A through F
    for label, rate, orig in [
        ("A", "0.0412", "128650000"), ("B", "0.0455", "27900000"),
        ("C", "0.0486", "43400000"), ("D", "0.0583", "44180000"),
        ("E", "0.0808", "18600000"), ("F", "0.0976", "17820000"),
    ]:
        if not db.query(DealTranche).filter(
            DealTranche.deal_id == deal2.id, DealTranche.class_label == label
        ).first():
            t = DealTranche(
                deal_id=deal2.id, class_label=label, regulation_type="combined",
                note_rate=Decimal(rate), original_balance=Decimal(orig),
            )
            db.add(t)
            db.flush()
            # Seed a current balance snapshot
            balances = {"A": "0", "B": "0", "C": "0", "D": "21832659.49",
                        "E": "18600000", "F": "17820000"}
            db.add(TrancheBalance(
                tranche_id=t.id, period="2025-06",
                balance=Decimal(balances[label]), source="manual",
            ))
    db.flush()

    # ================================================================
    # DEAL 3: Servicer C Deal 7 (copy of B but text-formatted cells)
    # ================================================================
    print("  Setting up Deal 3: Servicer C Deal 7...")
    svcc = servicers_map["SVCC"]
    deal3 = db.query(Deal).filter(Deal.name == "SVCC 2022-7").first()
    if not deal3:
        deal3 = Deal(name="SVCC 2022-7", servicer_id=svcc.id, product_type="ABS Auto",
                     status="draft", created_by=created_by)
        db.add(deal3)
        db.flush()

    # Servicer C uses same structure as B but cells are text-formatted (rows shifted by -1)
    d3_mappings = [
        (sys_vars["beg_pool_bal"], "Sheet1", "I", 24, "Beginning Aggregate Principal Balance"),
        (sys_vars["end_pool_bal"], "Sheet1", "I", 36, "End of period Aggregate Principal Balance"),
        (sys_vars["total_principal"], "Sheet1", "J", 34, "Total Monthly Principal Amounts"),
        (sys_vars["pool_factor"], "Sheet1", "K", 38, "Pool Factor"),
        (sys_vars["months_seasoned"], "Sheet1", "D", 20, "Months Seasoned"),
        (sys_vars["total_collections"], "Sheet1", "K", 80, "Total Available Funds"),
        (sys_vars["svc_fee"], "Sheet1", "H", 83, "Servicing Fee"),
        (sys_vars["oc_amount"], "Sheet1", "K", 145, "Overcollateralization Amount"),
        (sys_vars["reserve_fund_bal"], "Sheet1", "K", 131, "End of period Reserve Fund"),
    ]
    for var, sheet, col, row, tape_label in d3_mappings:
        if not db.query(VariableMapping).filter(
            VariableMapping.deal_id == deal3.id, VariableMapping.variable_id == var.id
        ).first():
            db.add(VariableMapping(
                deal_id=deal3.id, variable_id=var.id,
                sheet_name=sheet, column_letter=col, row_number=row, tape_label=tape_label,
            ))
    db.flush()

    # Tranches for Deal 3 (same structure as Deal 2)
    for label, rate, orig in [
        ("A", "0.0412", "128650000"), ("B", "0.0455", "27900000"),
        ("C", "0.0486", "43400000"), ("D", "0.0583", "44180000"),
        ("E", "0.0808", "18600000"), ("F", "0.0976", "17820000"),
    ]:
        if not db.query(DealTranche).filter(
            DealTranche.deal_id == deal3.id, DealTranche.class_label == label
        ).first():
            db.add(DealTranche(
                deal_id=deal3.id, class_label=label, regulation_type="combined",
                note_rate=Decimal(rate), original_balance=Decimal(orig),
            ))
    db.flush()

    # ================================================================
    # DAGs — build a simple waterfall DAG for Deal 2 (the most complete data)
    # ================================================================
    print("  Setting up DAG for SVCB 2022-7...")
    dag_svc = DagService(db)
    if not dag_svc.load(deal2.id):
        nodes = [
            # Input nodes (tape values)
            DagNodeCreate(key="total_available_funds", name="Total Available Funds",
                          node_type="input_value", stream="distribution", input_source="tape",
                          position_x=100, position_y=50),
            DagNodeCreate(key="svc_fee_tape", name="Servicing Fee (tape)",
                          node_type="input_value", stream="distribution", input_source="tape",
                          position_x=400, position_y=50),
            DagNodeCreate(key="trustee_fee_tape", name="Trustee Fee (tape)",
                          node_type="input_value", stream="distribution", input_source="tape",
                          position_x=700, position_y=50),
            DagNodeCreate(key="backup_svc_fee_tape", name="Backup Svc Fee (tape)",
                          node_type="input_value", stream="distribution", input_source="tape",
                          position_x=400, position_y=150),

            # Calculation nodes
            DagNodeCreate(key="total_fees", name="Total Fees",
                          node_type="calculation", stream="distribution",
                          formula="svc_fee_tape + trustee_fee_tape + backup_svc_fee_tape",
                          description="Sum of all senior fees",
                          position_x=400, position_y=250),
            DagNodeCreate(key="net_available", name="Net Available for Distribution",
                          node_type="calculation", stream="distribution",
                          formula="total_available_funds - total_fees",
                          description="Available funds after fees",
                          position_x=250, position_y=350),
            DagNodeCreate(key="class_d_int_calc", name="Class D Interest (calc)",
                          node_type="calculation", stream="distribution",
                          formula="class_d_balance * class_d_note_rate / 12",
                          description="Monthly Class D interest from tranche data",
                          position_x=100, position_y=450),
            DagNodeCreate(key="class_e_int_calc", name="Class E Interest (calc)",
                          node_type="calculation", stream="distribution",
                          formula="class_e_balance * class_e_note_rate / 12",
                          position_x=400, position_y=450),
            DagNodeCreate(key="class_f_int_calc", name="Class F Interest (calc)",
                          node_type="calculation", stream="distribution",
                          formula="class_f_balance * class_f_note_rate / 12",
                          position_x=700, position_y=450),
            DagNodeCreate(key="remaining_after_int", name="Remaining After Interest",
                          node_type="calculation", stream="distribution",
                          formula="MAX(net_available - class_d_int_calc - class_e_int_calc - class_f_int_calc, 0)",
                          position_x=400, position_y=550),

            # Distribution nodes (these go on the export)
            DagNodeCreate(key="dist_svc_fee", name="Servicing Fee Pmt",
                          node_type="distribution", stream="distribution",
                          formula="svc_fee_tape", payment_type="fee", export_field="SVC_FEE",
                          position_x=100, position_y=650),
            DagNodeCreate(key="dist_d_int", name="Class D Interest Pmt",
                          node_type="distribution", stream="distribution",
                          formula="MIN(net_available, class_d_int_calc)",
                          payment_type="interest", export_field="INT_PMT_D",
                          position_x=300, position_y=650),
            DagNodeCreate(key="dist_e_int", name="Class E Interest Pmt",
                          node_type="distribution", stream="distribution",
                          formula="MIN(MAX(net_available - class_d_int_calc, 0), class_e_int_calc)",
                          payment_type="interest", export_field="INT_PMT_E",
                          position_x=500, position_y=650),
            DagNodeCreate(key="dist_f_int", name="Class F Interest Pmt",
                          node_type="distribution", stream="distribution",
                          formula="MIN(MAX(net_available - class_d_int_calc - class_e_int_calc, 0), class_f_int_calc)",
                          payment_type="interest", export_field="INT_PMT_F",
                          position_x=700, position_y=650),
            DagNodeCreate(key="dist_prin", name="Principal Distribution",
                          node_type="distribution", stream="distribution",
                          formula="remaining_after_int",
                          payment_type="principal", export_field="PRIN_PMT_D",
                          position_x=400, position_y=750),

            # Validation nodes
            DagNodeCreate(key="val_oc_check", name="OC Amount Check",
                          node_type="validation", stream="validation",
                          formula="ABS(end_pool_bal - class_d_balance - class_e_balance - class_f_balance)",
                          tolerance=Decimal("0.01"), tolerance_type="absolute",
                          comparison_variable="oc_amount",
                          position_x=100, position_y=900),
            DagNodeCreate(key="val_dist_check", name="Total Distribution Check",
                          node_type="validation", stream="validation",
                          formula="ABS(dist_svc_fee + dist_d_int + dist_e_int + dist_f_int + dist_prin)",
                          tolerance=Decimal("0.01"), tolerance_type="absolute",
                          comparison_variable="total_distributions",
                          position_x=400, position_y=900),
        ]

        edges = [
            # Fees flow
            DagEdgeCreate(source_key="svc_fee_tape", target_key="total_fees"),
            DagEdgeCreate(source_key="trustee_fee_tape", target_key="total_fees"),
            DagEdgeCreate(source_key="backup_svc_fee_tape", target_key="total_fees"),
            # Net available
            DagEdgeCreate(source_key="total_available_funds", target_key="net_available"),
            DagEdgeCreate(source_key="total_fees", target_key="net_available"),
            # Interest calcs -> remaining
            DagEdgeCreate(source_key="net_available", target_key="remaining_after_int"),
            DagEdgeCreate(source_key="class_d_int_calc", target_key="remaining_after_int"),
            DagEdgeCreate(source_key="class_e_int_calc", target_key="remaining_after_int"),
            DagEdgeCreate(source_key="class_f_int_calc", target_key="remaining_after_int"),
            # Distributions
            DagEdgeCreate(source_key="svc_fee_tape", target_key="dist_svc_fee"),
            DagEdgeCreate(source_key="net_available", target_key="dist_d_int"),
            DagEdgeCreate(source_key="class_d_int_calc", target_key="dist_d_int"),
            DagEdgeCreate(source_key="net_available", target_key="dist_e_int"),
            DagEdgeCreate(source_key="class_d_int_calc", target_key="dist_e_int"),
            DagEdgeCreate(source_key="class_e_int_calc", target_key="dist_e_int"),
            DagEdgeCreate(source_key="net_available", target_key="dist_f_int"),
            DagEdgeCreate(source_key="class_d_int_calc", target_key="dist_f_int"),
            DagEdgeCreate(source_key="class_e_int_calc", target_key="dist_f_int"),
            DagEdgeCreate(source_key="class_f_int_calc", target_key="dist_f_int"),
            DagEdgeCreate(source_key="remaining_after_int", target_key="dist_prin"),
        ]

        dag_svc.save(deal2.id, nodes, edges, created_by, "Initial waterfall setup from seed")
        print("    + DAG v1: 17 nodes, 20 edges")

    # ================================================================
    # Export Templates (3 payment system formats)
    # ================================================================
    print("\n  Setting up export templates...")
    if not db.query(ExportTemplate).filter(ExportTemplate.name == "System A").first():
        t = ExportTemplate(name="System A", description="Row-per-payment CSV for primary payment system", format_type="row_per_payment")
        db.add(t)
        db.flush()
        for i, col in enumerate(["DEAL_ID", "PAYMENT_DATE", "PAYMENT_TYPE", "CLASS", "FIELD_CODE", "AMOUNT", "RUN_ID"]):
            db.add(ExportTemplateColumn(template_id=t.id, column_name=col, column_order=i))
        print("    + Template: System A (row-per-payment, 7 columns)")

    if not db.query(ExportTemplate).filter(ExportTemplate.name == "System B").first():
        t = ExportTemplate(name="System B", description="Wide format with 144A/RegS prorate for secondary system", format_type="wide_format")
        db.add(t)
        db.flush()
        for i, col in enumerate(["DEAL_ID", "PAYMENT_DATE", "INT_PMT_A", "INT_PMT_B", "PRIN_PMT_A", "PRIN_PMT_B", "SVC_FEE", "TRUSTEE_FEE", "TOTAL"]):
            db.add(ExportTemplateColumn(template_id=t.id, column_name=col, column_order=i))
        print("    + Template: System B (wide format, 9 columns)")

    if not db.query(ExportTemplate).filter(ExportTemplate.name == "System C").first():
        t = ExportTemplate(name="System C", description="CUSIP-level detail for custodian reporting", format_type="cusip_level")
        db.add(t)
        db.flush()
        for i, col in enumerate(["CUSIP", "DEAL_ID", "CLASS", "PAYMENT_DATE", "PAYMENT_TYPE", "AMOUNT"]):
            db.add(ExportTemplateColumn(template_id=t.id, column_name=col, column_order=i))
        print("    + Template: System C (CUSIP-level, 6 columns)")

    db.flush()

    db.commit()
    db.close()

    print(f"\nSeed complete. 3 deals + 3 export templates configured:")
    print(f"  SVCA 2022-3  — Servicer A, 4 classes, 20 mappings")
    print(f"  SVCB 2022-7  — Servicer B, 6 classes, 27 mappings, DAG with waterfall")
    print(f"  SVCC 2022-7  — Servicer C, 6 classes, 9 mappings (text-formatted tape)")
    print(f"  System A     — row-per-payment (7 cols)")
    print(f"  System B     — wide format with prorate (9 cols)")
    print(f"  System C     — CUSIP-level (6 cols)")


if __name__ == "__main__":
    print("Seeding ABSNexus database...\n")
    seed()
