"""balance_sheet_summary_v3.py — fund-quarter summary (percent of net assets) from balance_sheet_v3.json, with a consistency check of cash repurchases against the
tender master (accepted shares × NAV per share, settled in the following quarter). Output: results/balance_sheet_summary_v3.json."""
import json
from pathlib import Path
R = Path(__file__).resolve().parent.parent / "results"; B = json.load(open(R / "balance_sheet_v3.json"))["panel"]; M = json.load(open(R / "offer_master_v3.json"))["offers"]
rows = []
for fund, qs in B.items():
    for q, v in qs.items():
        if q < "2024-03-31": continue
        g = lambda k: (v.get(k) or {}).get("val"); na = g("net_assets")
        if not na: continue
        rp = g("repurchases_paid") if g("repurchases_paid") is not None else g("repurchases_value"); iss = g("issuance_proceeds"); ip = g("investment_purchases"); ipr = g("investment_proceeds")
        pct = lambda x: (100 * x / na) if x is not None else None
        rows.append(dict(fund=fund, quarter_end=q, net_assets=na, repurchases_paid=rp, repurchases_source=(v.get("repurchases_paid") or v.get("repurchases_value") or {}).get("concept"), issuance=iss, net_equity_flow=(iss - rp) if (iss is not None and rp is not None) else None,
                         investment_purchases=ip, investment_proceeds=ipr, net_investment=(ip - ipr) if (ip is not None and ipr is not None) else None, cash=g("cash"), debt=g("debt"), undrawn=g("undrawn_capacity"),
                         repurchases_pct_na=pct(rp), issuance_pct_na=pct(iss), net_equity_flow_pct_na=pct((iss - rp) if (iss is not None and rp is not None) else None), investment_purchases_pct_na=pct(ip), investment_proceeds_pct_na=pct(ipr), cash_pct_na=pct(g("cash")), debt_to_na=(g("debt") / na) if g("debt") else None, undrawn_pct_na=pct(g("undrawn_capacity"))))
json.dump({"rows": rows}, open(R / "balance_sheet_summary_v3.json", "w"), indent=1)
print(f"{'fund':6}{'qend':11}{'rep%NA':>7}{'iss%NA':>7}{'netflow%':>9}{'purch%NA':>9}{'disp%NA':>8}{'netinv%':>8}{'cash%':>6}{'debt/NA':>8}{'undrawn%':>9}")
for r in rows:
    if r["quarter_end"] >= "2025-06-30": print(f"{r['fund']:6}{r['quarter_end']:11}{(r['repurchases_pct_na'] if r['repurchases_pct_na'] is not None else float('nan')):>7.1f}{(r['issuance_pct_na'] if r['issuance_pct_na'] is not None else float('nan')):>7.1f}{(r['net_equity_flow_pct_na'] if r['net_equity_flow_pct_na'] is not None else float('nan')):>9.1f}{(r['investment_purchases_pct_na'] if r['investment_purchases_pct_na'] is not None else float('nan')):>9.1f}{(r['investment_proceeds_pct_na'] if r['investment_proceeds_pct_na'] is not None else float('nan')):>8.1f}{((r['investment_purchases_pct_na'] or 0)-(r['investment_proceeds_pct_na'] or 0)) if r['investment_purchases_pct_na'] is not None and r['investment_proceeds_pct_na'] is not None else float('nan'):>8.1f}{(r['cash_pct_na'] if r['cash_pct_na'] is not None else float('nan')):>6.1f}{(r['debt_to_na'] if r['debt_to_na'] is not None else float('nan')):>8.2f}{(r['undrawn_pct_na'] if r['undrawn_pct_na'] is not None else float('nan')):>9.1f}")
