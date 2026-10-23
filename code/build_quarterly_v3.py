"""build_quarterly_v3.py — fund-quarter panel from m2_tender_panel_v3.json.
Rules: quarter = calendar quarter of (offer expiry date − 15 days) when the expiry is parsed (early-January expiries are the Q4 cycle), else of the filing date − 45 days.
When several filings fall in one fund-quarter, keep the LAST filing that reports a tendered count (corrected re-filings and final results supersede
interim estimates); a filing with only an approximate count is used only if no exact count exists for that quarter.
Derived: fill_rate = accepted/tendered; unfilled = tendered − accepted; unfilled_prev = previous quarter's unfilled; new_floor = tendered − unfilled_prev
(lower bound on new requests under full resubmission of unfilled shares); oversub = tendered/accepted."""
import json, re
from pathlib import Path
from datetime import datetime, timedelta
BASE = Path(__file__).resolve().parent.parent; v3 = json.load(open(BASE / "results" / "m2_tender_panel_v3.json"))
def quarter(d): return f"{d.year}Q{(d.month - 1) // 3 + 1}"
rows = []
for k, v in v3.items():
    fund, fdate, acc = k.split("_"); fd = datetime.strptime(fdate, "%Y-%m-%d")
    qd = (datetime.strptime(v["expiry"], "%Y-%m-%d") - timedelta(days=15)) if v["expiry"] else fd - timedelta(days=45)   # expiry minus 15 days: early-January expiries belong to the Q4 cycle
    rows.append(dict(fund=fund, filing_date=fdate, accession=acc, expiry=v["expiry"], quarter=quarter(qd), tendered=v["tendered"], approx=v["tendered_approx"], accepted=v["accepted"], full_fill=v["full_fill"], by_payment=v.get("full_fill_by_payment", False), prorated=v["prorated"], upsized=v["upsized"], pct_requested=v["pct_requested"], pct_fulfilled=v["pct_fulfilled"]))
best = {}
for r in sorted(rows, key=lambda r: r["filing_date"]):
    if r["tendered"] is None: continue
    key = (r["fund"], r["quarter"]); cur = best.get(key)
    if cur is None or (cur["approx"] and not r["approx"]) or (cur["approx"] == r["approx"]): best[key] = r
out = []
for fund in sorted({r["fund"] for r in rows}):
    qs = sorted(q for (f, q) in best if f == fund); prev = None
    for q in qs:
        r = dict(best[(fund, q)]); t, a = r["tendered"], r["accepted"]
        r["fill_rate"] = round(a / t, 4) if (t and a) else None; r["oversub"] = round(t / a, 3) if (t and a) else None
        r["unfilled"] = round(t - a, 2) if (t is not None and a is not None) else None
        r["unfilled_prev"] = prev["unfilled"] if prev else None
        r["new_floor"] = round(t - prev["unfilled"], 2) if (prev and prev["unfilled"] is not None) else None
        r["gated_quarters_so_far"] = (prev["gated_quarters_so_far"] if prev else 0) + (1 if (r["fill_rate"] is not None and r["fill_rate"] < 0.999) else 0)
        out.append(r); prev = r
json.dump({"meta": {"built": datetime.now().strftime("%Y-%m-%d %H:%M"), "source": "m2_tender_panel_v3.json (independent re-extraction from cached filings)", "rules": __doc__}, "rows": out}, open(BASE / "results" / "m2_quarterly_v3.json", "w"), indent=1)
print(f"fund-quarters: {len(out)}")
print(f"{'fund':6}{'quarter':8}{'filed':11}{'tendered':>14}{'accepted':>14}{'fill':>7}{'oversub':>8}{'unfilled_prev':>14}{'new_floor':>13}{'gatedQ':>7}  flags")
for r in out:
    if r["quarter"] >= "2025Q4": print(f"{r['fund']:6}{r['quarter']:8}{r['filing_date']:11}{r['tendered']:>14,.0f}{(r['accepted'] or 0):>14,.0f}{(r['fill_rate'] if r['fill_rate'] is not None else float('nan')):>7.2f}{(r['oversub'] if r['oversub'] else float('nan')):>8.2f}{(r['unfilled_prev'] if r['unfilled_prev'] is not None else float('nan')):>14,.0f}{(r['new_floor'] if r['new_floor'] is not None else float('nan')):>13,.0f}{r['gated_quarters_so_far']:>7}  {'approx ' if r['approx'] else ''}{'prorated ' if r['prorated'] else ''}{'upsized ' if r['upsized'] else ''}{'paid-all ' if r['by_payment'] else ''}")
