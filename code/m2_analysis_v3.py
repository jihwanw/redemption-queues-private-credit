"""m2_analysis_v3.py — rebuild of the manuscript's descriptive analyses from results/offer_master_v3.json (offer-keyed, evidence-backed).
Part 1: sample summary; request rates pre/post by INVESTOR WINDOW (offer expiry) and, for comparison, by results-filing date (the submitted paper's basis);
2026 gate incidence with final (corrected) figures; consecutive-offer transitions with unfilled carry-over and the new-request floor; H3 contrast
(growth in gross requests after a prorated offer vs after a fully filled offer) with permutation p-value. Output: results/m2_analysis_v3.json."""
import json, itertools, math
from pathlib import Path
from datetime import datetime
import numpy as np
BASE = Path(__file__).resolve().parent.parent; R = BASE / "results"
M = json.load(open(R / "offer_master_v3.json"))["offers"]
done = sorted([o for o in M if o.get("tendered") is not None], key=lambda o: (o["fund"], o["expiry"]))   # includes zero-tender results
sched = lambda o: o.get("scheduled_expiry") or o["expiry"]   # DATING CONVENTION: an offer belongs to the cycle of its scheduled expiry; OTIC's December-2025 offer (scheduled 2025-12-31, extended to 2026-01-08) is a 2025-cycle offer throughout
NEWS = "2026-03-24"   # first public proration disclosure: ASIF SC TO-I/A of 24 March 2026 (requests 11.6% of shares; 43.1% pro rata)
out = {"meta": {"built": datetime.now().strftime("%Y-%m-%d %H:%M"), "source": "offer_master_v3.json", "news_date": NEWS}}
# --- sample summary
out["sample"] = {"offers_with_results": len(done), "funds": sorted({o["fund"] for o in done}), "first_expiry": done[0]["expiry"] if done else None, "last_expiry": max(o["expiry"] for o in done),
                 "prorated_offers": sum(1 for o in done if o.get("rationed")), "fully_filled_offers": sum(1 for o in done if o.get("fill_rate") == 1.0),
                 "offers_with_filing_denominator": sum(1 for o in done if o.get("shares_outstanding_basis")), "result_filings_linked": sum(len(o["result_filings"]) for o in done), "commencement_filings": len(M)}
# --- request rates: investor-window basis vs filing-date basis
def rate(o):   # exact rate (percent of the cap denominator), so that one rounding step is applied downstream
    if o.get("shares_outstanding_basis") and o.get("tendered") is not None: return 100 * o["tendered"] / o["shares_outstanding_basis"]
    return o.get("tendered_pct_basis")
pre_w = [rate(o) for o in done if sched(o) < "2026-01-01" and rate(o) is not None]; post_w = [rate(o) for o in done if sched(o) >= "2026-01-01" and rate(o) is not None]
pre_f = [rate(o) for o in done if o["final_filing"] < "2026-01-15" and rate(o) is not None]; post_f = [rate(o) for o in done if o["final_filing"] >= "2026-01-15" and rate(o) is not None]
h1 = [rate(o) for o in done if "2026-01-01" <= sched(o) <= "2026-06-30" and rate(o) is not None]
out["request_rates_pct_of_shares"] = {"investor_window_basis": {"pre2026_mean": round(np.mean(pre_w), 2), "pre2026_n": len(pre_w), "2026_mean": round(np.mean(post_w), 2), "2026_n": len(post_w), "2026H1_mean": round(np.mean(h1), 2), "2026H1_n": len(h1)},
                                      "filing_date_basis_as_submitted": {"pre_mean": round(np.mean(pre_f), 2), "pre_n": len(pre_f), "post_mean": round(np.mean(post_f), 2), "post_n": len(post_f)},
                                      "note": "rate = shares tendered / (cap shares ÷ cap percent), both from the offer's own SC TO-I, for offers whose cap is stated in shares; for OCIC/OTIC 2023–25, whose caps are stated in dollars, cap shares = dollar cap ÷ the net offering price stated in the same filing and the denominator is that ÷ 5 percent; for OCIC/OTIC 2026 the rate is the percent stated in the result filing (OTIC March 2026: shares outstanding at 31 December 2025 adjusted for the January tender). Offers are dated by the cycle of their scheduled expiry.", "dating_convention": "scheduled expiry (cycle); OTIC 2025-12-31 offer extended to 2026-01-08 counted in 2025"}
# --- 2026 gate incidence (all offers expiring in 2026 with results)
out["gate_incidence_2026"] = [{"fund": o["fund"], "expiry": o["expiry"], "final_filing": o["final_filing"], "tendered": o["tendered"], "accepted": o["accepted"], "fill_rate": o.get("fill_rate"), "oversub": o.get("oversub"), "prorated": bool(o.get("rationed")), "upsized": bool(o.get("upsized")), "cap_pct": o["cap_pct"], "cap_shares": o.get("cap_shares"), "requested_pct_of_shares": rate(o)} for o in done if sched(o) >= "2026-01-01"]
# --- consecutive-offer transitions (per fund, by expiry order), floors, H3
trans = []
for fund in sorted({o["fund"] for o in done}):
    seq = [o for o in done if o["fund"] == fund]
    for a, b in zip(seq, seq[1:]):
        if a["expiry"] < "2025-09-01": continue
        unfilled = (a["tendered"] - a["accepted"]) if a.get("accepted") is not None else None
        floor = b["tendered"] - unfilled if unfilled is not None else None
        cyc = lambda o: (lambda d: f"{d.year}Q{(d.month-1)//3+1}")(datetime.strptime(o.get("scheduled_expiry") or o["expiry"], "%Y-%m-%d") - __import__("datetime").timedelta(days=15))
        trans.append({"fund": fund, "from_cycle": cyc(a), "to_cycle": cyc(b), "from_expiry": a["expiry"], "to_expiry": b["expiry"], "from_tendered": a["tendered"], "to_tendered": b["tendered"], "growth_pct": round(100 * (b["tendered"] / a["tendered"] - 1), 1), "log_growth": round(math.log(b["tendered"] / a["tendered"]), 4),
                      "prev_prorated": bool(a.get("rationed")), "prev_oversub": a.get("oversub"), "prev_unfilled": unfilled, "new_request_floor": floor, "max_resubmission_share_pct": round(100 * unfilled / b["tendered"], 1) if unfilled else 0.0,
                      "to_prorated": bool(b.get("rationed")), "to_oversub": b.get("oversub"), "news_exposure_of_to_window": ("post" if b["commencement"] >= NEWS else ("straddle" if b["expiry"] > NEWS else "pre"))})
out["transitions"] = trans
def h3(rows, label):
    t = [r["log_growth"] for r in rows if r["prev_prorated"]]; c = [r["log_growth"] for r in rows if not r["prev_prorated"]]
    if not t or not c: return {"label": label, "n_treated": len(t), "n_control": len(c), "contrast": None}
    obs = np.mean(t) - np.mean(c); allv = t + c; k = len(t); cnt = 0; tot = 0
    for idx in itertools.combinations(range(len(allv)), k):
        tt = [allv[i] for i in idx]; cc = [allv[i] for i in range(len(allv)) if i not in idx]; tot += 1
        if np.mean(tt) - np.mean(cc) >= obs - 1e-12: cnt += 1
    return {"label": label, "n_treated": k, "n_control": len(c), "treated_funds": [r["fund"] + ":" + r["to_expiry"][:7] for r in rows if r["prev_prorated"]], "control_funds": [r["fund"] + ":" + r["to_expiry"][:7] for r in rows if not r["prev_prorated"]], "mean_log_growth_treated": round(float(np.mean(t)), 4), "mean_log_growth_control": round(float(np.mean(c)), 4), "contrast": round(float(obs), 4), "perm_p_one_sided": round(cnt / tot, 4), "n_perm": tot}
# first 2026 offer -> second 2026 offer for every fund (eligible set includes FPCF Feb->May and GCRED Feb->May)
first_second = []
for f in sorted({r["fund"] for r in trans}):
    seq = [r for r in trans if r["fund"] == f and r["from_cycle"] >= "2026Q1"]
    if seq: first_second.append(seq[0])
out["h3_first_to_second_2026_offer"] = h3(first_second, "growth from each fund's first 2026 offer to its second; treated = first 2026 offer rationed")
march_june = [r for r in first_second if "2026-02-15" <= r["from_expiry"] <= "2026-04-05"]
out["h3_march_to_june_subset"] = h3(march_june, "subset with first 2026-cycle offer expiring mid-February to early April 2026 (the pre-registered comparison's window)")
all26 = [r for r in trans if r["from_cycle"] >= "2026Q1"]
out["h3_all_2026_transitions"] = h3(all26, "all consecutive transitions whose earlier offer belongs to a 2026 cycle (scheduled expiry in 2026); OTIC's December-2025 offer, extended to 8 January 2026, is a 2025-cycle offer, so its January->March transition is not in this set")
all26_actual = [r for r in trans if r["from_expiry"] >= "2026-01-01"]
out["h3_all_transitions_from_offers_with_actual_expiry_2026"] = h3(all26_actual, "robustness: all consecutive transitions whose earlier offer actually expired in 2026 (adds OTIC January->March, a filled-to-rationed transition)")
json.dump(out, open(R / "m2_analysis_v3.json", "w"), indent=1)
print(json.dumps(out["sample"])); print(json.dumps(out["request_rates_pct_of_shares"], indent=1))
print(f"\n{'fund':6}{'from':11}{'to':11}{'from_tend':>13}{'to_tend':>13}{'growth%':>8}{'prev_pror':>10}{'prev_ovs':>9}{'unfilled_prev':>14}{'floor':>13}{'resub_max%':>11}  news")
for r in trans: print(f"{r['fund']:6}{r['from_expiry']:11}{r['to_expiry']:11}{r['from_tendered']:>13,.0f}{r['to_tendered']:>13,.0f}{r['growth_pct']:>8.1f}{str(r['prev_prorated']):>10}{(r['prev_oversub'] or 1):>9.2f}{(r['prev_unfilled'] or 0):>14,.0f}{(r['new_request_floor'] or 0):>13,.0f}{r['max_resubmission_share_pct']:>11.1f}  {r['news_exposure_of_to_window']}")
print("\nH3 first->second:", json.dumps(out["h3_first_to_second_2026_offer"])); print("H3 march->june:", json.dumps(out["h3_march_to_june_subset"])); print("H3 all:", json.dumps(out["h3_all_2026_transitions"]))
