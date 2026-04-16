"""Waterfall comparison PDF — generates a print-friendly HTML document."""
from datetime import datetime


def render_waterfall_html(data: dict) -> str:
    """Render waterfall comparison data as a standalone HTML page.

    The user opens this in a browser and prints to PDF (Ctrl+P).
    """
    steps_html = ""
    for s in data["steps"]:
        amount = _fmt_money(s["amount"])
        tape = _fmt_money(s["tape_value"]) if s["tape_value"] else "—"
        diff = _fmt_money(s["difference"]) if s["difference"] else "—"

        if s["matched"] is True:
            status = '<span style="color: #16a34a; font-weight: 600;">MATCH</span>'
            row_bg = ""
        elif s["matched"] is False:
            status = '<span style="color: #dc2626; font-weight: 600;">MISMATCH</span>'
            row_bg = ' style="background: #fef2f2;"'
        else:
            status = '<span style="color: #9ca3af;">—</span>'
            row_bg = ""

        steps_html += f"""
        <tr{row_bg}>
            <td style="text-align: center;">{s["step"]}</td>
            <td>{s["node_name"]}</td>
            <td style="font-family: monospace; text-align: right;">{amount}</td>
            <td style="font-family: monospace; text-align: right;">{tape}</td>
            <td style="font-family: monospace; text-align: right;">{diff}</td>
            <td style="text-align: center;">{status}</td>
        </tr>"""

    comp_count = data.get("comparison_count", 0)
    comp_matched = data.get("comparison_matched", 0)
    all_ok = data.get("all_compared", False)
    reconciled = data.get("reconciled")

    if all_ok and reconciled:
        overall = '<span style="color: #16a34a; font-weight: 700; font-size: 16px;">ALL MATCHED</span>'
    elif reconciled is False or (comp_count > 0 and not all_ok):
        overall = '<span style="color: #dc2626; font-weight: 700; font-size: 16px;">DISCREPANCIES FOUND</span>'
    else:
        overall = '<span style="color: #6b7280; font-weight: 600; font-size: 16px;">PARTIAL COMPARISON</span>'

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Waterfall Comparison — {data.get("deal_name", "")} — {data.get("report_period", "")}</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 13px; color: #1f2937; margin: 0; padding: 24px; }}
    h1 {{ font-size: 20px; margin: 0 0 4px; }}
    .subtitle {{ color: #6b7280; font-size: 13px; margin-bottom: 20px; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
    th {{ background: #f9fafb; text-align: left; padding: 8px 10px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.4px; color: #6b7280; border-bottom: 2px solid #e5e7eb; }}
    td {{ padding: 8px 10px; border-bottom: 1px solid #e5e7eb; }}
    .summary {{ display: flex; gap: 24px; margin-bottom: 20px; }}
    .stat {{ }}
    .stat-label {{ font-size: 11px; color: #6b7280; text-transform: uppercase; }}
    .stat-value {{ font-size: 18px; font-weight: 600; font-family: monospace; }}
    .footer {{ margin-top: 24px; font-size: 11px; color: #9ca3af; border-top: 1px solid #e5e7eb; padding-top: 12px; }}
    @media print {{
        body {{ padding: 12px; }}
        .no-print {{ display: none; }}
    }}
</style>
</head>
<body>
<h1>Waterfall Comparison Report</h1>
<div class="subtitle">
    {data.get("deal_name", "")} &middot; {data.get("report_period", "")} &middot; {data.get("run_code", "")}
</div>

<div class="summary">
    <div class="stat">
        <div class="stat-label">Starting Balance</div>
        <div class="stat-value">{_fmt_money(data.get("starting_balance", "0"))}</div>
    </div>
    <div class="stat">
        <div class="stat-label">Distributions</div>
        <div class="stat-value">{data.get("step_count", 0)}</div>
    </div>
    <div class="stat">
        <div class="stat-label">Compared</div>
        <div class="stat-value">{comp_matched} / {comp_count}</div>
    </div>
    <div class="stat">
        <div class="stat-label">Status</div>
        <div>{overall}</div>
    </div>
</div>

<table>
    <thead>
        <tr>
            <th style="width: 40px; text-align: center;">#</th>
            <th>Distribution</th>
            <th style="text-align: right;">Our Calculation</th>
            <th style="text-align: right;">Tape Value</th>
            <th style="text-align: right;">Difference</th>
            <th style="text-align: center; width: 90px;">Status</th>
        </tr>
    </thead>
    <tbody>
        {steps_html}
    </tbody>
</table>

<div class="summary">
    <div class="stat">
        <div class="stat-label">Final Remainder</div>
        <div class="stat-value">{_fmt_money(data.get("final_calculated_remainder", "0"))}</div>
    </div>
    <div class="stat">
        <div class="stat-label">Tape Ending Balance</div>
        <div class="stat-value">{_fmt_money(data.get("tape_ending_balance")) if data.get("tape_ending_balance") else "—"}</div>
    </div>
    <div class="stat">
        <div class="stat-label">Reconciliation</div>
        <div class="stat-value">{"PASS" if reconciled else ("FAIL" if reconciled is False else "N/A")}</div>
    </div>
</div>

<div class="footer">
    Generated {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")} &middot; ABSNexus Waterfall Comparison
</div>

<div class="no-print" style="margin-top: 16px;">
    <button onclick="window.print()" style="padding: 8px 16px; font-size: 13px; cursor: pointer;">
        Print / Save as PDF
    </button>
</div>
</body>
</html>"""


def _fmt_money(val: str | None) -> str:
    if val is None:
        return "—"
    try:
        n = float(val)
        return f"${n:,.2f}"
    except (ValueError, TypeError):
        return str(val)
