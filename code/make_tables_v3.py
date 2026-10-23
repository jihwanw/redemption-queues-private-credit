"""make_tables_v3.py — every table and prose number of the JFS manuscript from the v3 results JSONs only. Writes paper/tex/tables_v3/T_*.tex (standalone) and numbers_v3.tex."""
import json, subprocess, math, re
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
BASE = Path(__file__).resolve().parent.parent; R = BASE / "results"; OUT = BASE / "paper" / "tex" / "tables_v3"; OUT.mkdir(exist_ok=True)
J = lambda p: json.load(open(R / p))
M = J("offer_master_v3.json")["offers"]; A = J("m2_analysis_v3.json"); G = J("m2_regressions_v3.json"); BS = J("balance_sheet_summary_v3.json")["rows"]; RE = J("reit_history_v3.json"); R1 = J("m2_revision_results.json"); R2 = J("m2_revision2_results.json")
def r(x, d=1): return "" if x is None else str(Decimal(str(x)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)) if d else f"{int(Decimal(str(x)).quantize(Decimal(1), rounding=ROUND_HALF_UP)):,}"
def c(x): return "" if x is None else f"{x:,.0f}"
def w(name, body, cols=None):
    """One standalone PDF per table. Every table is set in the same font (\\footnotesize of a 12pt class = 10pt) and is laid out to fit
    its slot without scaling (portrait <= 469pt, landscape <= 630pt), so fonts are identical across tables; widths are checked after
    compilation by check_widths()."""
    (OUT / f"T_{name}.tex").write_text("\\documentclass[12pt]{standalone}\n\\usepackage{booktabs,array}\n\\setlength{\\tabcolsep}{4pt}\n\\renewcommand{\\arraystretch}{1.08}\n\\begin{document}\\footnotesize\n" + body + "\n\\end{document}\n")
def H(text, align="c"):
    """multi-line header cell without extra packages: a nested tabular; lines separated by '|'"""
    return "\\begin{tabular}[b]{@{}" + align + "@{}}" + text.replace("|", "\\\\") + "\\end{tabular}"
LANDSCAPE = {"transitions", "balance", "marks", "marks_largest"}
done = sorted([o for o in M if o.get("tendered") is not None], key=lambda o: (o["fund"], o["expiry"]))
def xrate(o):   # exact request rate: tendered / (cap shares / cap percent); the stored 2-dp field is not re-rounded
    if o.get("shares_outstanding_basis") and o.get("tendered") is not None: return 100 * o["tendered"] / o["shares_outstanding_basis"]
    return o.get("tendered_pct_basis")
FUNDN = {"BCRED": "Blackstone Private Credit Fund", "OCIC": "Blue Owl Credit Income Corp.", "OTIC": "Blue Owl Technology Income Corp.", "ADS": "Apollo Debt Solutions BDC", "HLEND": "HPS Corporate Lending Fund", "ASIF": "Ares Strategic Income Fund", "OSCF": "Oaktree Strategic Credit Fund", "FPCF": "Fidelity Private Credit Fund", "GCRED": "Golub Capital Private Credit Fund", "PCAP": "Nuveen Churchill Private Capital Income Fund"}
# T1 sample: per fund offers, first/last expiry, prorated count, mean request rate pre-2026 and 2026
rows = []
for f in sorted(FUNDN):
    o = [x for x in done if x["fund"] == f]; sch = lambda x: x.get("scheduled_expiry") or x["expiry"]; pre = [xrate(x) for x in o if sch(x) < "2026-01-01" and xrate(x) is not None]; post = [xrate(x) for x in o if sch(x) >= "2026-01-01" and xrate(x) is not None]
    rows.append(f"{f} & {len(o)} & {o[0]['expiry'][:7]} & {o[-1]['expiry'][:7]} & {sum(1 for x in o if x.get('prorated') and x.get('fill_rate',1)<0.999)} & {r(sum(pre)/len(pre),2) if pre else ''} & {r(sum(post)/len(post),2) if post else ''} \\\\")
w("sample", "\\begin{tabular}{lrllrrr}\\toprule\n" + " & ".join(["Fund", "Offers", H("First|expiry"), H("Last|expiry"), "Prorated", H("Requests,|2023--25 cycles|(\\% of shares)$^{a}$"), H("Requests,|2026 cycles|(\\% of shares)$^{a}$")]) + " \\\\ \\midrule\n" + "\n".join(rows) + f"\n\\midrule\nAll & {len(done)} & & & {A['sample']['prorated_offers']} & {r(A['request_rates_pct_of_shares']['investor_window_basis']['pre2026_mean'],2)} & {r(A['request_rates_pct_of_shares']['investor_window_basis']['2026_mean'],2)} \\\\\n\\bottomrule\\end{{tabular}}")
# T2 gate incidence 2026 (all 2026 offers with results)
gi = sorted(A["gate_incidence_2026"], key=lambda x: (x["expiry"], x["fund"]))
w("gates2026", "\\begin{tabular}{llrrrrl}\\toprule\n" + " & ".join(["Fund", H("Offer|expiry"), "Tendered", "Accepted", H("Fill|rate"), H("Requests|(\\% of shares)$^{a}$"), "Outcome"]) + " \\\\ \\midrule\n" + "\n".join(f"{x['fund']} & {x['expiry']} & {c(x['tendered'])} & {c(x['accepted'])} & {r(x['fill_rate'],2)} & {r(x['requested_pct_of_shares'],1)} & {'prorated (' + r(x['oversub'],2) + '$\\\\times$)' if x['prorated'] else ('upsized, filled' if x['upsized'] else 'filled')} \\\\" for x in gi) + "\n\\bottomrule\\end{tabular}")
# T3 transitions with floors
tr = [t for t in A["transitions"] if t["from_expiry"] >= "2025-11-01"]
w("transitions", "\\begin{tabular}{lllrrrrrr}\\toprule\n" + " & ".join(["Fund", H("From|(expiry)"), H("To|(expiry)"), H("Gross|requests,|from"), H("Gross|requests,|to"), H("Growth|(\\%)"), H("Previous|unfilled"), H("Lower bound on|requests not|carried forward"), H("Maximum|resubmission|share (\\%)")]) + " \\\\ \\midrule\n" + "\n".join(f"{t['fund']} & {t['from_expiry']}{'$^{p}$' if t['prev_prorated'] else ''} & {t['to_expiry']} & {c(t['from_tendered'])} & {c(t['to_tendered'])} & {r(t['growth_pct'],1)} & {c(t['prev_unfilled']) if t['prev_unfilled'] else '0'} & {c(t['new_request_floor'])} & {r(t['max_resubmission_share_pct'],1)} \\\\" for t in tr) + "\n\\bottomrule\\end{tabular}")
# T4 H3 contrasts
h = [("First to second 2026-cycle offer, all ten funds", A["h3_first_to_second_2026_offer"]), ("Same, first offer expiring mid-February to early April (pre-registered window)", A["h3_march_to_june_subset"]), ("All consecutive transitions from a 2026-cycle offer", A["h3_all_2026_transitions"])]
w("h3", "\\begin{tabular}{p{4.6cm}rrrrrr}\\toprule\n" + " & ".join(["Comparison", H("Treated|$n$"), H("Control|$n$"), H("Mean log|growth,|treated"), H("Mean log|growth,|control"), "Contrast", H("Permutation|$p$|(one-sided)")]) + " \\\\ \\midrule\n" + "\n".join(f"{lab} & {x['n_treated']} & {x['n_control']} & {r(x['mean_log_growth_treated'],3)} & {r(x['mean_log_growth_control'],3)} & {r(x['contrast'],3)} & {r(x['perm_p_one_sided'],3)} \\\\" for lab, x in h) + "\n\\bottomrule\\end{tabular}")
# T5 regressions
def coefrow(spec, k, label):
    v = G["specs"][spec]["coef"].get(k); return f"{label} & {r(v['b'],3)} & ({r(v['se_cluster'],3)}) & {r(v['t_cluster'],2)} & {r(v.get('wcb_p'),3)} & {r(v.get('p_cluster_t_Gminus1'),3)} \\\\" if v else ""
body = ["\\begin{tabular}{p{7.2cm}rrrrr}\\toprule", " & ".join(["Specification / regressor", "Coefficient", H("(cluster|SE)"), "$t$", H("WCB|$p$"), H("$p$|($t_{G-1}$)")]) + " \\\\ \\midrule"]
for spec, title in (("A_fundFE", "(A) Fund fixed effects"), ("B_fundFE_headroom", "(B) Fund fixed effects + predetermined headroom interactions"), ("C_fund_quarterFE_headroom", "(C) Fund and investor-quarter fixed effects"), ("C_alt_calendar_headroom", "(C$^\\prime$) As (C), headroom from the last offer that actually expired in 2025"), ("C2_fund_quarterFE_disclosure", "(C$^{\\prime\\prime}$) Fund and investor-quarter fixed effects, headroom interacted with disclosure exposure"), ("D_allten_fund_quarterFE_cycle", "(D) All ten funds, no twin discount: fund and investor-quarter fixed effects, headroom $\\times$ 2026 cycle"), ("D2_allten_fund_quarterFE_disclosure", "(D$^{\\prime\\prime}$) All ten funds, no twin discount: headroom interacted with disclosure exposure")):
    body.append(f"\\multicolumn{{6}}{{@{{}}p{{16.2cm}}@{{}}}}{{\\emph{{{title}}} ($N$={G['specs'][spec]['n']}, $R^2$={r(G['specs'][spec]['r2'],3)})}} \\\\")
    for k, lab in (("twin_disc", "Listed-twin discount (pp)"), ("straddle", "Window straddling 24 March 2026 (both are low-headroom funds)"), ("post", "Window opened after 24 March 2026"), ("lowheadroom:post", "Low headroom $\\times$ post"), ("lowheadroom:post2026", "Low headroom $\\times$ 2026 cycle"), ("lowheadroom_cal:post2026", "Low headroom (calendar-2025 baseline) $\\times$ 2026 cycle"), ("lowheadroom:straddle", "Window straddling 24 March (OCIC and OTIC, both low headroom; conditional coefficient)")): 
        rr = coefrow(spec, k, lab)
        if rr: body.append(rr)
body.append("\\bottomrule\\end{tabular}"); w("regressions", "\n".join(body))
# T6 balance sheet (2025Q4–2026Q2, prorated-at-some-point funds first)
order = ["BCRED", "OCIC", "OTIC", "ASIF", "HLEND", "ADS", "GCRED", "OSCF", "FPCF", "PCAP"]
bs = [x for x in BS if "2025-12-31" <= x["quarter_end"] <= "2026-06-30"]; bs.sort(key=lambda x: (order.index(x["fund"]), x["quarter_end"]))
w("balance", "\\begin{tabular}{llrrrrrrrr}\\toprule\n" + " & ".join(["Fund", H("Quarter|end"), H("Repurchases|paid"), H("Subscrip-|tions"), H("Net equity|flow"), H("Investment|purchases"), H("Dispositions|\\& repayments"), "Cash", H("Debt/|NA"), H("Undrawn|capacity")]) + " \\\\ \\midrule\n" + "\n".join(f"{x['fund']} & {x['quarter_end']} & {r(x['repurchases_pct_na'],1)} & {r(x['issuance_pct_na'],1)} & {r(x['net_equity_flow_pct_na'],1)} & {r(x['investment_purchases_pct_na'],1)} & {r(x['investment_proceeds_pct_na'],1)} & {r(x['cash_pct_na'],1)} & {r(x['debt_to_na'],2)} & {r(x['undrawn_pct_na'],1)} \\\\" for x in bs) + "\n\\bottomrule\\end{tabular}")
# T7 twin discounts by availability quarter (from v2 records; ingredients verified 2026-10-16)
TD = J("twin_discounts_v3.json"); per = TD["per_twin_disc_by_avail_q"]; qs = sorted({q for t in per.values() for q in t}); tw = sorted(per)
w("discounts", "\\begin{tabular}{l" + "r" * len(tw) + "r}\\toprule\nQuarter in which the 10-Q/10-K became available & " + " & ".join(tw) + " & Mean \\\\ \\midrule\n" + "\n".join(f"{q} & " + " & ".join(r(per[t].get(q), 1) for t in tw) + f" & {r(TD['avg_disc_by_avail_q'].get(q),1)} \\\\" for q in qs if q >= "2024Q1") + "\n\\bottomrule\\end{tabular}")
# T8 matched-twin event study (event_study_v3.json; corrected first-disclosure dates)
ES = J("event_study_v3.json")
w("events", "\\begin{tabular}{lllrr}\\toprule\n" + " & ".join(["Listed twin", H("Non-traded|fund(s)", "l"), H("First proration|disclosure", "l"), H("CAR [0,+1]|\\% ($t$)"), H("CAR [0,+5]|\\% ($t$)")]) + " \\\\ \\midrule\n" + "\n".join(f"{e['twin']} & {e['sibling']} & {e['event_date']} & {r(e['car_0_1']['car_pct'],2)} ({r(e['car_0_1']['t'],2)}) & {r(e['car_0_5']['car_pct'],2)} ({r(e['car_0_5']['t'],2)}) \\\\" for e in ES["events"]) + f"\n\\midrule\nMean of the four events & & & {r(ES['mean_car_0_1']['mean_pct'],2)} ({r(ES['mean_car_0_1']['t'],2)}) & \\\\\n\\bottomrule\\end{{tabular}}")
# T9 BREIT
w("breit", "\\begin{tabular}{lrrrl}\\toprule\n" + " & ".join(["Month", H("Fulfilled|(\\% of NAV)"), H("Fulfilled|(\\% of requests)"), H("Requests|(\\% of NAV)"), H("Interval from|disclosed rounding", "l")]) + " \\\\ \\midrule\n" + "\n".join(f"{k} & {r(v['fulfilled_nav_pct'],1)} & {r(v['fulfill_of_requests_pct'],0)} & {r(v['requests_nav_pct'],1)} & [{math.floor(v['requests_nav_pct_interval'][0]*10)/10:.1f}, {math.ceil(v['requests_nav_pct_interval'][1]*10)/10:.1f}] \\\\" for k, v in sorted(RE["monthly"].items())) + "\n\\bottomrule\\end{tabular}")
# numbers macros
rr = A["request_rates_pct_of_shares"]["investor_window_basis"]; h1 = A["h3_first_to_second_2026_offer"]; h2 = A["h3_all_2026_transitions"]; h12 = A["h3_march_to_june_subset"]; gA = G["specs"]["A_fundFE"]["coef"]; gC = G["specs"]["C_fund_quarterFE_headroom"]["coef"]
def flt(t, f): return next(x for x in A["transitions"] if x["fund"] == f and x["to_expiry"][:7] == t)
nums = {"NOffers": str(A["sample"]["offers_with_results"]), "NProrated": str(A["sample"]["prorated_offers"]), "NFilled": str(A["sample"]["fully_filled_offers"]), "NCommence": str(A["sample"]["commencement_filings"]), "NResultFilings": str(A["sample"]["result_filings_linked"]),
        "RatePre": r(rr["pre2026_mean"], 2), "RatePreN": str(rr["pre2026_n"]), "RateTwentySix": r(rr["2026_mean"], 1), "RateTwentySixN": str(rr["2026_n"]),
        "HThreeContrast": r(h1["contrast"], 2), "HThreeP": r(h1["perm_p_one_sided"], 3), "HThreeTreated": str(h1["n_treated"]), "HThreeControl": str(h1["n_control"]), "HThreeAllContrast": r(h2["contrast"], 2), "HThreeAllP": r(h2["perm_p_one_sided"], 2), "HThreeMJContrast": r(h12["contrast"], 2), "HThreeMJP": r(h12["perm_p_one_sided"], 2), "HThreeMJTreated": str(h12["n_treated"]), "HThreeMJControl": str(h12["n_control"]), "HThreeAllTreated": str(h2["n_treated"]), "HThreeAllControl": str(h2["n_control"]), "NewsDate": "24 March 2026",
        "TwinDiscA": r(gA["twin_disc"]["b"], 3), "TwinDiscAx": r(G["specs"]["A_fundFE_excl_first_offers"]["coef"]["twin_disc"]["b"], 3), "TwinDiscAxt": r(G["specs"]["A_fundFE_excl_first_offers"]["coef"]["twin_disc"]["t_cluster"], 2), "NRegX": str(G["specs"]["A_fundFE_excl_first_offers"]["n"]), "NZeroTender": str(sum(1 for o in done if o.get("zero_tender"))), "HeadroomCalt": r(G["specs"]["C_alt_calendar_headroom"]["coef"]["lowheadroom_cal:post2026"]["b"], 2), "HeadroomCpost": r(G["specs"]["C2_fund_quarterFE_disclosure"]["coef"]["lowheadroom:post"]["b"], 2), "HeadroomD": r(G["specs"]["D_allten_fund_quarterFE_cycle"]["coef"]["lowheadroom:post2026"]["b"], 2), "HeadroomDt": r(G["specs"]["D_allten_fund_quarterFE_cycle"]["coef"]["lowheadroom:post2026"]["t_cluster"], 2), "HeadroomDpost": r(G["specs"]["D2_allten_fund_quarterFE_disclosure"]["coef"]["lowheadroom:post"]["b"], 2), "HeadroomDpostT": r(G["specs"]["D2_allten_fund_quarterFE_disclosure"]["coef"]["lowheadroom:post"]["t_cluster"], 2), "NRegTen": str(G["specs"]["D_allten_fund_quarterFE_cycle"]["n"]), "LowHeadroomTenFunds": ", ".join(G["low_headroom_funds_all_ten"]), "HeadroomCpostT": r(G["specs"]["C2_fund_quarterFE_disclosure"]["coef"]["lowheadroom:post"]["t_cluster"], 2), "HeadroomCstraddle": r(G["specs"]["C2_fund_quarterFE_disclosure"]["coef"]["lowheadroom:straddle"]["b"], 2), "HeadroomCstraddleT": r(G["specs"]["C2_fund_quarterFE_disclosure"]["coef"]["lowheadroom:straddle"]["t_cluster"], 2), "HeadroomCaltT": r(G["specs"]["C_alt_calendar_headroom"]["coef"]["lowheadroom_cal:post2026"]["t_cluster"], 2), "StraddleA": r(gA["straddle"]["b"], 2), "StraddleAt": r(gA["straddle"]["t_cluster"], 2), "HThreeAllActualContrast": r(A["h3_all_transitions_from_offers_with_actual_expiry_2026"]["contrast"], 2), "HThreeAllActualP": r(A["h3_all_transitions_from_offers_with_actual_expiry_2026"]["perm_p_one_sided"], 2), "HThreeAllActualN": str(A["h3_all_transitions_from_offers_with_actual_expiry_2026"]["n_treated"] + A["h3_all_transitions_from_offers_with_actual_expiry_2026"]["n_control"]), "TwinDiscAabs": r(abs(gA["twin_disc"]["b"]), 3), "HeadroomCse": r(gC["lowheadroom:post2026"]["se_cluster"], 2), "HeadroomCLo": r(gC["lowheadroom:post2026"]["b"] - 2.571 * gC["lowheadroom:post2026"]["se_cluster"], 2), "HeadroomCHi": r(gC["lowheadroom:post2026"]["b"] + 2.571 * gC["lowheadroom:post2026"]["se_cluster"], 2), "HeadroomCLoNormal": r(gC["lowheadroom:post2026"]["b"] - 1.96 * gC["lowheadroom:post2026"]["se_cluster"], 2), "HeadroomCHiNormal": r(gC["lowheadroom:post2026"]["b"] + 1.96 * gC["lowheadroom:post2026"]["se_cluster"], 2), "TCritFive": "2.571", "TwinDiscAt": r(gA["twin_disc"]["t_cluster"], 2), "TwinDiscC": r(gC["twin_disc"]["b"], 3), "TwinDiscCt": r(gC["twin_disc"]["t_cluster"], 2), "PostA": r(gA["post"]["b"], 2), "PostAt": r(gA["post"]["t_cluster"], 1), "HeadroomC": r(gC["lowheadroom:post2026"]["b"], 2), "HeadroomCt": r(gC["lowheadroom:post2026"]["t_cluster"], 2), "WCBFloor": r(gA["twin_disc"]["wcb_p_floor"], 3), "NRegOffers": str(G["n_offers"]),
        "ADSFloorShare": r(100 * flt("2026-06", "ADS")["new_request_floor"] / flt("2026-06", "ADS")["from_tendered"], 0), "HLENDFloorShare": r(100 * flt("2026-06", "HLEND")["new_request_floor"] / flt("2026-06", "HLEND")["from_tendered"], 0), "OCICResubMax": r(flt("2026-06", "OCIC")["max_resubmission_share_pct"], 0), "OTICResubMax": r(flt("2026-06", "OTIC")["max_resubmission_share_pct"], 0)}
_rb = {x["quarter_end"]: x["repurchases_paid"] for x in BS if x["fund"] == "BCRED" and x.get("repurchases_paid") is not None}; nums["RepBCREDQoneBn"] = f"{_rb['2026-03-31'] / 1e9:.3f}"; nums["RepBCREDQtwoBn"] = f"{_rb['2026-06-30'] / 1e9:.3f}"
FF = J("filing_facts_v3.json"); BSr = {(x["fund"], x["quarter_end"]): x for x in BS}
def tr_(f, to): return flt(to, f)
for t in A["transitions"]:
    if t["to_expiry"] >= "2025-12-01": nums[f"G{t['fund']}{t['to_expiry'][:7].replace('-', '')}"] = r(100 * (t["to_tendered"] / t["from_tendered"] - 1), 0)   # one rounding from the raw tenders
for o in done:
    _ex = o.get("scheduled_expiry") or o["expiry"]   # macro names follow the scheduled cycle date (OTIC's December offer was extended to 8 January)
    if _ex >= "2025-09-01" and xrate(o) is not None: nums[f"Req{o['fund']}{_ex[:7].replace('-', '')}"] = r(xrate(o), 1)
    if _ex >= "2026-01-01" and o.get("oversub"): nums[f"Ovs{o['fund']}{_ex[:7].replace('-', '')}"] = r(o["oversub"], 2)
for (f, q), x in BSr.items():
    if q in ("2025-06-30", "2026-06-30", "2026-03-31"):
        tag = f"{f}{q[:7].replace('-', '')}"
        for k, lab in (("issuance_pct_na", "Iss"), ("repurchases_pct_na", "Rep"), ("investment_purchases_pct_na", "Pur"), ("investment_proceeds_pct_na", "Dis"), ("cash_pct_na", "Cash"), ("undrawn_pct_na", "Undr"), ("net_equity_flow_pct_na", "Net")):
            if x.get(k) is not None: nums[f"{lab}{tag}"] = r(x[k], 1)
        if x.get("debt_to_na") is not None: nums[f"Lev{tag}"] = r(x["debt_to_na"], 2)
_first = [t for t in A["transitions"] if t["to_cycle"] == "2026Q1"]; nums["GFirstMin"] = r(min(t["growth_pct"] for t in _first), 0); nums["GFirstMax"] = r(max(t["growth_pct"] for t in _first), 0); nums["GFirstMinFund"] = min(_first, key=lambda t: t["growth_pct"])["fund"]; nums["GFirstMaxFund"] = max(_first, key=lambda t: t["growth_pct"])["fund"]; nums["NFirstRationedHOne"] = str(len({t["fund"] for t in A["transitions"] if t["to_cycle"] in ("2026Q1", "2026Q2") and t["to_prorated"]} | {o["fund"] for o in done if o.get("rationed") and "2026-01-01" <= o["expiry"] <= "2026-06-30"}))
nums["BREITPeakReq"] = r(max(v["requests_nav_pct"] for v in RE["monthly"].values()), 1); nums["BREITPeakMonth"] = max(RE["monthly"].items(), key=lambda kv: kv[1]["requests_nav_pct"])[0]
nums["BREITDecLo"] = f"{math.floor(RE['monthly']['2022-12']['requests_nav_pct_interval'][0]*10)/10:.1f}"; nums["BREITDecHi"] = f"{math.ceil(RE['monthly']['2022-12']['requests_nav_pct_interval'][1]*10)/10:.1f}"
h = FF["HLEND_8K_20260727"]; nums.update({"CoxPrice": f"{h['cox_price']:.2f}", "CoxShares": f"{h['cox_shares']:,}", "CoxNAVMay": f"{h['nav_may31']:.2f}", "CoxNAVJun": f"{h['nav_jun30']:.2f}", "CoxDisc": str(h["discount_pct_stated"]), "CoxBCREDPrice": f"{FF['BCRED_8K_20260930']['cox_price']:.2f}", "CoxBCREDDisc": str(FF["BCRED_8K_20260930"]["discount_pct_stated"])})
b = FF["BCRED_SCTOIA_20260302"]; nums.update({"BCREDUpsize": str(b["cap_upsized_pct"]), "BCREDEmployees": str(b["employees_invested_mn"]), "BCREDFirm": str(b["firm_invested_mn"]), "BCREDInsiderPct": str(b["insider_share_pct"]), "BCREDLiqDec": str(b["liquidity_dec31_bn"])})
b2 = FF["BCRED_8K_20260730"]; nums.update({"BCREDRepay": str(b2["repayments_q2_bn"]), "BCREDSubsQtwo": str(b2["subscriptions_q2_bn"]), "BCREDAcceptedQtwo": str(b2["repurchases_accepted_q2_bn"]), "BCREDCoverage": str(b2["coverage_pct"]), "BCREDInflowsQone": str(FF["BCRED_8K_20260429"]["gross_inflows_q1_bn"]), "BCREDAvailLiq": str(FF["BCRED_8K_20260723"]["available_liquidity_bn"])})
o_ = FF["OSCF_SCTOIA_20260327"]; nums.update({"OSCFReq": str(o_["requests_pct_of_shares"]), "OSCFUpsize": str(o_["cap_increase_pct"]), "OSCFSponsor": str(o_["sponsor_purchase_pct"]), "ASIFEstReq": str(FF["ASIF_SCTOIA_20260324"]["requests_pct_of_shares_estimate"])})
nums["CoxQueueShare"] = r(100 * h["cox_shares"] / flt("2026-06", "HLEND")["to_tendered"], 1)
for q, v in TD["avg_disc_by_avail_q"].items(): nums[f"DiscAvg{q}"] = r(v, 1)
for t in A["transitions"]:
    if t["prev_prorated"] and t["prev_unfilled"]:
        tag = f"{t['fund']}{t['to_expiry'][:7].replace('-', '')}"; nums[f"FloorShare{tag}"] = r(100 * t["new_request_floor"] / t["from_tendered"], 0); nums[f"Resub{tag}"] = r(t["max_resubmission_share_pct"], 0); nums[f"Floor{tag}"] = f"{t['new_request_floor']/1e6:.1f}"
# event-study intervals: two-day CAR +/- 1.96 * sd_resid * sqrt(2) per event; pooled mean +/- 1.96 * sqrt(sum se_i^2)/n
_se = {e["twin"]: 100 * e["sd_resid"] * (2 ** 0.5) for e in ES["events"]}
for e in ES["events"]: nums[f"ESLo{e['twin']}"] = r(e["car_0_1"]["car_pct"] - 1.96 * _se[e["twin"]], 1); nums[f"ESHi{e['twin']}"] = r(e["car_0_1"]["car_pct"] + 1.96 * _se[e["twin"]], 1)
_sem = (sum(v ** 2 for v in _se.values()) ** 0.5) / len(_se); nums["ESMeanLo"] = r(ES["mean_car_0_1"]["mean_pct"] - 1.96 * _sem, 1); nums["ESMeanHi"] = r(ES["mean_car_0_1"]["mean_pct"] + 1.96 * _sem, 1); nums["ESWorstLo"] = r(min(e["car_0_1"]["car_pct"] - 1.96 * _se[e["twin"]] for e in ES["events"]), 1)
# cash range over 2026 quarter-ends at funds whose statements tag cash; Oaktree's disposition rise; OTIC calendar-baseline headroom; maximum results lag
_c26 = [x["cash_pct_na"] for x in BS if x["quarter_end"] >= "2026-01-01" and x.get("cash_pct_na") is not None]
nums["CashMinTwentySix"] = r(min(_c26), 1); nums["CashMaxTwentySix"] = r(max(_c26), 1); nums["NCashFundsTwentySix"] = str(len({x["fund"] for x in BS if x["quarter_end"] >= "2026-01-01" and x.get("cash_pct_na") is not None}))
nums["HeadroomOTICcal"] = r(G["headroom_calendar_expiry"]["OTIC"], 1)
_ot = [o for o in done if o["fund"] == "OTIC" and o.get("scheduled_expiry") == "2026-03-31"]; nums["OTICMarCapEquiv"] = r(100 * _ot[0]["accepted"] / _ot[0]["shares_outstanding_basis"], 1) if _ot and _ot[0].get("shares_outstanding_basis") else "[RESULTS-GAP]"
# result-filing timing relative to the fund's next commencement (before / same day / after), and the 2025-cycle baseline's publication relative to the fund's first 2026-cycle window
_cnt = {"before": 0, "same": 0, "after": 0}
for f_ in sorted({o["fund"] for o in M}):
    seq = sorted([o for o in M if o["fund"] == f_], key=lambda o: o["commencement"])
    for a_, b_ in zip(seq, seq[1:]):
        if a_.get("final_filing"): _cnt["before" if a_["final_filing"] < b_["commencement"] else ("same" if a_["final_filing"] == b_["commencement"] else "after")] += 1
WORDS = {0: "none", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
nums["NResultPairs"] = str(sum(_cnt.values())); 
_samefunds = set()
for f_ in sorted({o["fund"] for o in M}):
    seq = sorted([o for o in M if o["fund"] == f_], key=lambda o: o["commencement"])
    for a_, b_ in zip(seq, seq[1:]):
        if a_.get("final_filing") and a_["final_filing"] == b_["commencement"]: _samefunds.add(f_)
nums["NResultSameFunds"] = str(len(_samefunds))
# first disclosures of requests at or above the cap (filled by enlargement), and how the first 2026-cycle windows relate to them
_ab = sorted((o["final_filing"], o["fund"]) for o in done if o.get("tendered_pct_basis") and o["tendered_pct_basis"] >= 5.0)
nums["FirstAboveCapDate"] = _ab[0][0]; nums["FirstAboveCapFund"] = _ab[0][1]
_f26 = {}
for f_ in sorted({o["fund"] for o in done}):
    seq = sorted([o for o in done if o["fund"] == f_ and (o.get("scheduled_expiry") or o["expiry"]) >= "2026-01-01"], key=lambda o: o.get("scheduled_expiry") or o["expiry"]); _f26[f_] = seq[0]
nums["NFirstWindowsClosedAfterAboveCap"] = str(sum(1 for o in _f26.values() if o["expiry"] > _ab[0][0])); nums["NFirstWindowsOpenedAfterAboveCap"] = str(sum(1 for o in _f26.values() if o["commencement"] > _ab[0][0]))
nums["NFirstWindowsClosedAfterBlueOwlDec"] = str(sum(1 for o in _f26.values() if o["expiry"] > "2026-01-29"))
_l25 = {}
for f_ in sorted({o["fund"] for o in done}):
    seq = sorted([o for o in done if o["fund"] == f_ and (o.get("scheduled_expiry") or o["expiry"]) < "2026-01-01"], key=lambda o: o.get("scheduled_expiry") or o["expiry"]); _l25[f_] = seq[-1]
nums["NFundsRateRoseFirst"] = str(sum(1 for f_ in _f26 if xrate(_f26[f_]) > xrate(_l25[f_]))); nums["RateFellFirstFunds"] = ", ".join(f_ for f_ in _f26 if xrate(_f26[f_]) <= xrate(_l25[f_])) or "none"
nums["ReqGCREDLastTwentyFive"] = r(xrate(_l25["GCRED"]), 2); nums["ReqGCREDFirstTwentySix"] = r(xrate(_f26["GCRED"]), 2)
nums["NResultBefore"] = str(_cnt["before"]); nums["NResultSame"] = str(_cnt["same"]); nums["NResultAfter"] = str(_cnt["after"])
_bl = {"before": [], "same": [], "after": []}
for f_ in sorted({o["fund"] for o in done}):
    seq = sorted([o for o in done if o["fund"] == f_], key=lambda o: o.get("scheduled_expiry") or o["expiry"]); l25 = [o for o in seq if (o.get("scheduled_expiry") or o["expiry"]) < "2026-01-01"][-1]; f26 = [o for o in seq if (o.get("scheduled_expiry") or o["expiry"]) >= "2026-01-01"][0]
    _bl["before" if l25["final_filing"] < f26["commencement"] else ("same" if l25["final_filing"] == f26["commencement"] else "after")].append(f_)
nums["NBaseBefore"] = str(len(_bl["before"])); nums["NBaseSame"] = str(len(_bl["same"])); nums["NBaseAfter"] = str(len(_bl["after"]))
nums["NEnlargedByOutcome"] = str(sum(1 for o in done if o.get("enlarged_by_outcome")))
nums["BCREDSubsQoneBn"] = f"{J('filing_facts_v3.json')['BCRED_SCTOIA_20260302']['subscriptions_q1_bn']:.0f}"; nums["WCBDraws"] = str(G["specs"]["A_fundFE"]["coef"]["twin_disc"]["wcb_n_draws"])
FF = J("filing_facts_v3.json"); nums["BCREDPaidJanBn"] = f"{FF['BCRED_SCTOIA_20260202']['paid_usd'] / 1e9:.3f}"; nums["BCREDPaidAprBn"] = f"{FF['BCRED_SCTOIA_20260501']['paid_usd'] / 1e9:.3f}"; nums["ASIFEstFill"] = r(FF["ASIF_SCTOIA_20260324"]["pro_rata_pct"], 1)
_a1 = [o for o in done if o["fund"] == "ASIF" and o["commencement"] == "2023-11-21"]; nums["ASIFFirstTendered"] = c(_a1[0]["tendered"]) if _a1 else "[RESULTS-GAP]"
_iss = [x["issuance"] for x in BS if x["fund"] == "BCRED" and x["quarter_end"] == "2026-06-30" and x.get("issuance") is not None]; nums["IssBCREDQtwoBn"] = r(_iss[0] / 1e9, 2) if _iss else "[RESULTS-GAP: BCRED 2026Q2 issuance]"
_iss1 = [x["issuance"] for x in BS if x["fund"] == "BCRED" and x["quarter_end"] == "2026-03-31" and x.get("issuance") is not None]; nums["IssBCREDQoneBn"] = r(_iss1[0] / 1e9, 2) if _iss1 else "[RESULTS-GAP: BCRED 2026Q1 issuance]"
nums["BREITOctFulfillNAV"] = r(RE["monthly"]["2022-10"]["fulfilled_nav_pct"], 1)
import datetime as _dt
_lags = [(_dt.date.fromisoformat(o["final_filing"]) - _dt.date.fromisoformat(o["expiry"])).days for o in done if o.get("final_filing")]; nums["LagMin"] = str(min(_lags)); nums["LagMax"] = str(max(_lags))
nums["ESMeanCAR"] = r(ES["mean_car_0_1"]["mean_pct"], 2); nums["ESMeanT"] = r(ES["mean_car_0_1"]["t"], 2); nums["ESN"] = str(ES["mean_car_0_1"]["n_events"]); nums["ESNegTwoDay"] = str(sum(1 for e in ES["events"] if e["car_0_1"]["car_pct"] < 0))
for e in ES["events"]: nums[f"CAR{e['twin']}"] = r(e["car_0_1"]["car_pct"], 2); nums[f"CARfive{e['twin']}"] = r(e["car_0_5"]["car_pct"], 2); nums[f"CARt{e['twin']}"] = r(e["car_0_1"]["t"], 2)
nums["CARfiveMin"] = r(min(e["car_0_5"]["car_pct"] for e in ES["events"]), 2); nums["CARfiveMax"] = r(max(e["car_0_5"]["car_pct"] for e in ES["events"]), 2)
for (f, q), x in BSr.items():
    if q == "2025-06-30":
        tag = f"{f}2025Q2"
        for k, lab in (("issuance_pct_na", "Iss"), ("investment_purchases_pct_na", "Pur"), ("investment_proceeds_pct_na", "Dis"), ("undrawn_pct_na", "Undr")):
            if x.get(k) is not None: nums[f"{lab}{tag}"] = r(x[k], 1)
        if x.get("debt_to_na") is not None: nums[f"Lev{tag}"] = r(x["debt_to_na"], 2)
nums["OTICDisQ1"] = r(BSr[("OTIC", "2026-03-31")]["investment_proceeds_pct_na"], 1); nums["OTICRepQ1"] = r(BSr[("OTIC", "2026-03-31")]["repurchases_pct_na"], 1)
import statistics as _st
for f_ in sorted({x["fund"] for x in BS}):
    d25 = [x["investment_proceeds_pct_na"] for x in BS if x["fund"] == f_ and "2025-03-31" <= x["quarter_end"] <= "2025-12-31" and x["investment_proceeds_pct_na"] is not None]
    d26 = [x["investment_proceeds_pct_na"] for x in BS if x["fund"] == f_ and x["quarter_end"] >= "2026-03-31" and x["investment_proceeds_pct_na"] is not None]
    p25 = [x["investment_purchases_pct_na"] for x in BS if x["fund"] == f_ and "2025-03-31" <= x["quarter_end"] <= "2025-12-31" and x["investment_purchases_pct_na"] is not None]
    p26 = [x["investment_purchases_pct_na"] for x in BS if x["fund"] == f_ and x["quarter_end"] >= "2026-03-31" and x["investment_purchases_pct_na"] is not None]
    if d25 and d26: nums[f"DisMean25{f_}"] = r(_st.mean(d25), 1); nums[f"DisMean26{f_}"] = r(_st.mean(d26), 1); nums[f"DisMax25{f_}"] = r(max(d25), 1); nums[f"DisRise{f_}"] = r(_st.mean(d26) - _st.mean(d25), 1)
    if p25 and p26: nums[f"PurMean25{f_}"] = r(_st.mean(p25), 1); nums[f"PurMean26{f_}"] = r(_st.mean(p26), 1)
nums["NFundsPurchHalved"] = str(sum(1 for f_ in {x["fund"] for x in BS} if f"PurMean25{f_}" in nums and float(nums[f"PurMean26{f_}"]) <= 0.5 * float(nums[f"PurMean25{f_}"])))
# in-domain variant for H4: set aside the settlement quarters of offers filled above the cap (OTIC 2026Q1 after its enlarged December offer; BCRED 2026Q2 after its 7% March offer)
# 2026 settlement quarters of offers accepted above their original cap: Blue Owl's two December-2025 offers (notes paid January 2026 -> 2026Q1), Blackstone's and Oaktree's March-2026 offers (paid April/May -> 2026Q2); Ares's enlarged December offer was paid on 29 December 2025 (2025Q4)
_excl = {("OTIC", "2026-03-31"), ("OCIC", "2026-03-31"), ("BCRED", "2026-06-30"), ("OSCF", "2026-06-30")}; _cnt_in = 0
for f_ in sorted({x["fund"] for x in BS}):
    p25 = [x["investment_purchases_pct_na"] for x in BS if x["fund"] == f_ and "2025-03-31" <= x["quarter_end"] <= "2025-12-31" and x["investment_purchases_pct_na"] is not None]
    p26 = [x["investment_purchases_pct_na"] for x in BS if x["fund"] == f_ and x["quarter_end"] >= "2026-03-31" and x["investment_purchases_pct_na"] is not None and (f_, x["quarter_end"]) not in _excl]
    if p25 and p26 and _st.mean(p26) <= 0.5 * _st.mean(p25): _cnt_in += 1
nums["NFundsPurchHalvedInDomain"] = str(_cnt_in)
for f_, v in G["headroom"].items():
    if v is not None: nums[f"Headroom{f_}"] = r(v, 1)
for o in done:
    if (o.get("scheduled_expiry") or o["expiry"]) >= "2026-01-01" and o.get("fill_rate") is not None: nums[f"Fill{o['fund']}{(o.get('scheduled_expiry') or o['expiry'])[:7].replace('-', '')}"] = r(100 * o["fill_rate"], 0)
nums["BCREDPaidMarch"] = f"{FF['BCRED_SCTOIA_20260501']['paid_usd']/1e9:.1f}"
na = [x["net_assets"] for x in BS if x["quarter_end"] == "2026-06-30"]; nums["TotalNetAssets"] = r(sum(na) / 1e9, 0); nums["TotalNetAssetsN"] = str(len(na))


# ---- Definitions (one row list -> short form in Section 3.2, full form in Appendix C; same numbering and order) -----------------
DEFS = [
 ("D1", "Gross requests ($T$)", "Shares ``validly tendered and not withdrawn prior to the expiration of the Offer'', summed across share classes.",
  "Shares a holder asked the fund to repurchase in one quarterly tender offer; the quantity the run theories call redemption requests. Operationally the number of shares ``validly tendered and not withdrawn prior to the expiration of the Offer'' reported in the final SC TO-I/A result filing, summed across share classes where listed separately.",
  "Result filing (SC TO-I/A), Rule 13e-4; Section~\\ref{sec:definitions}", "Tables~\\ref{tab:sample}, \\ref{tab:gates}, \\ref{tab:transitions}; equations~(\\ref{eq:decomp})--(\\ref{eq:specC})"),
 ("D2", "Accepted shares ($A$)", "Shares ``accepted for purchase''; $A=T$ when the filing states that all tendered shares were purchased.",
  "Shares the fund repurchased in the offer. Operationally the number ``accepted for purchase'' in the result filing; set equal to $T$ when the filing states that the fund accepted ``100\\% of the Shares'' or purchased ``all validly tendered'' shares or paid the net asset value of all shares tendered.",
  "Result filing (SC TO-I/A); Section~\\ref{sec:definitions}", "Tables~\\ref{tab:gates}, \\ref{tab:transitions}; equation~(\\ref{eq:decomp})"),
 ("D3", "Rationed offer", "An offer with $A<T$; its oversubscription is $T/A$.",
  "An offer in which the fund repurchased fewer shares than were tendered and allocated pro rata. Operationally $A<T$ in the result filing (author rule); oversubscription $T/A$. Offers enlarged above the original cap and then filled in full are not rationed.",
  "Author rule on D1--D2", "Tables~\\ref{tab:gates}, \\ref{tab:transitions}, \\ref{tab:h3}"),
 ("D4", "Request rate", "$T$ divided by the fund's own denominator: cap in shares $\\div$ cap in percent (Blue Owl exceptions stated).",
  "Requests as a share of the shares eligible for the cap. Operationally $T$ divided by the share count the fund used to set its cap (cap in shares $\\div$ cap in percent, from the offer's own filing); for Blue Owl's 2023--25 offers the dollar cap $\\div$ the net offering price in the same document $\\div$ 5\\%; for Blue Owl's 2026 offers the percentage stated in the result filing (OTIC March 2026: shares outstanding net of the January tender).",
  "Offer and result filings; author rule, Section~\\ref{sec:definitions}", "Tables~\\ref{tab:sample}, \\ref{tab:gates}; Figure~\\ref{fig:requests}"),
 ("D5", "Unfilled shares ($U_n$)", "$T_n-A_n$: the shares tendered in window $n$ that the fund did not repurchase.",
  "The part of a window's requests that lapsed unfilled and may be re-tendered. Operationally $U_n=T_n-A_n$ from the result filing (equation~\\ref{eq:decomp}).",
  "D1--D2; equation~(\\ref{eq:decomp})", "Table~\\ref{tab:transitions}; Section~\\ref{sec:stockflow}"),
 ("D6", "Lower bound on requests not carried forward ($L_{n+1}$; ``the floor'')", "$\\max\\{0,\\,T_{n+1}-U_n\\}$: the fewest shares in window $n+1$ that cannot be resubmissions of window $n$'s unfilled shares.",
  "A bound, not an estimate, on the requests in window $n+1$ that were not carried from window $n$. Operationally $L_{n+1}=\\max\\{0,T_{n+1}-U_n\\}$ (equation~\\ref{eq:decomp}); valid for any resubmission rate; a bound on first-time requests only if no unfilled request from an earlier window re-enters after skipping one; it does not bound over-requesting.",
  "Author-developed; equation~(\\ref{eq:decomp}); Appendix~\\ref{app:model}, equation~(\\ref{eq:stockflow})", "Table~\\ref{tab:transitions}; Sections~\\ref{sec:stockflow}, \\ref{sec:policy}"),
 ("D7", "Resubmission ceiling share", "$\\min\\{1,\\,U_n/T_{n+1}\\}$: the largest share of window $n+1$'s requests that resubmission alone could account for.",
  "The upper bound on resubmissions in a later window, as a share of that window's gross requests. Operationally $\\min\\{1,U_n/T_{n+1}\\}$ from D1, D2 (author rule).",
  "Author-developed; Section~\\ref{sec:definitions}", "Table~\\ref{tab:transitions}; Section~\\ref{sec:stockflow}"),
 ("D8", "Cycle (scheduled-expiry) dating", "An offer belongs to the quarter of its scheduled expiry; the one extended offer keeps its original cycle.",
  "The convention that places each offer in time by when requests had to be in. Operationally the quarter of the scheduled expiry date in the offer document; Blue Owl Technology Income's offer scheduled for 31 December 2025 and extended to 8 January 2026 is a 2025-cycle offer.",
  "Author rule; Section~\\ref{sec:design}", "All tables dated by window; Figure~\\ref{fig:requests}"),
 ("D9", "Exposure to the first proration disclosure", "Straddle: a window open on 24 March 2026; Post: a window opened after it.",
  "Whether investors deciding in a window could know that a fund had rationed. Operationally, relative to Ares's amendment of 24 March 2026 (the first public proration): Straddle = window open on that date; Post = window opened after it; the 2026-cycle indicator approximates exposure dated from the first above-cap disclosure (\\FirstAboveCapDate).",
  "Author rule; Section~\\ref{sec:design}; equations~(\\ref{eq:specA})--(\\ref{eq:specC})", "Table~\\ref{tab:regressions}"),
 ("D10", "Headroom; low headroom", "5\\% cap less the fund's request rate in its last 2025-cycle offer; low = below the median across funds.",
  "A predetermined proxy for how close a fund already was to its cap before 2026. Operationally the five-percent cap minus the request rate (D4) of the fund's last 2025-cycle offer; the low-headroom group is below the median; it proxies expected rationing exposure and does not measure beliefs.",
  "Author-developed; Section~\\ref{sec:horserace}", "Table~\\ref{tab:regressions}; equation~(\\ref{eq:specC})"),
 ("D11", "Listed-twin discount", "Twin's closing price on the first trading day on or after its 10-Q/10-K filing date, over the NAV per share in that filing, minus one (percent).",
  "The market's valuation of an exchange-listed claim on largely the same loans relative to the sponsor's mark. Operationally price (first close on or after the filing date) $\\div$ NAV per share (US-GAAP \\texttt{NetAssetValuePerShare}, period end) $-1$, in percent; the value known at an offer's commencement is the latest filing before the window opened.",
  "XBRL companyfacts (SEC); Yahoo Finance closes; Section~\\ref{sec:data}", "Table~\\ref{tab:discounts}; Figure~\\ref{fig:twins}; equation~(\\ref{eq:specA})"),
 ("D12", "Matched group and mark", "Lines of two vehicles with the same issuer, spread, rate, lien seniority and facility type; mark $=$ fair value $\\div$ tagged principal (equation~\\ref{eq:mark}).",
  "The unit on which a non-traded fund's and its listed twin's valuations of the same loans are compared. Operationally the pooled schedule-of-investments lines of one vehicle sharing issuer key, spread, interest rate, lien seniority and facility type (dollar-denominated only); mark $m_g=\\sum\\mathrm{FV}/\\sum\\mathrm{Prin}$; difference in basis points of principal, weighted by the fund's fair value.",
  "Inline-XBRL schedules of investments (US-GAAP \\texttt{Investment\\allowbreak Owned*} elements); author rule, Appendix~\\ref{app:soi}", "Table~\\ref{tab:marks}; Tables~\\ref{tab:marks_quarterly}, \\ref{tab:marks_largest}; equation~(\\ref{eq:mark})"),
 ("D13", "Non-accrual share", "The filer's own statement of investments on non-accrual as a percent of its portfolio at fair value (basis as stated).",
  "The share of a vehicle's investments on which it has stopped accruing income. Operationally the figure the filing itself states, on the filer's own denominator and basis (fair value preferred; cost or a count where that is all the filing gives), bound to the report date by the nearest ``as of'' clause.",
  "10-Q/10-K text; Appendix~\\ref{app:soi}", "Table~\\ref{tab:marks}; Section~\\ref{sec:marks}"),
 ("D14", "Balance-sheet flows relative to net assets", "Quarterly cash-flow items (repurchases paid, issuance, purchases and dispositions of investments) de-cumulated from year-to-date XBRL facts, divided by net assets.",
  "What the fund paid out, took in and invested in a quarter, scaled by its size. Operationally US-GAAP cash-flow elements (e.g.\\ \\texttt{Payments\\allowbreak For\\allowbreak Repurchase\\allowbreak Of\\allowbreak Common\\allowbreak Stock}, \\texttt{Payments\\allowbreak To\\allowbreak Acquire\\allowbreak Investments}) from 10-Q/10-K XBRL, quarterly values as differences of year-to-date amounts, divided by net assets; dispositions and repayments are reported together by the filers.",
  "XBRL companyfacts (SEC); Section~\\ref{sec:data}", "Table~\\ref{tab:balance}; Section~\\ref{sec:balance}"),
]
# Column widths are fractions of \\linewidth less the column padding, and the fractions sum to one, so each table is exactly
# as wide as the text block in whatever class and margins the manuscript uses (hard-coded centimetre widths overflowed by 28pt and 74pt).
def _cols(fracs):
    return "".join(f">{{\\raggedright\\arraybackslash}}p{{\\dimexpr {f:.3f}\\linewidth-2\\tabcolsep\\relax}}" for f in fracs)   # ragged right: narrow justified columns stretch word spaces
assert abs(sum([0.065, 0.240, 0.480, 0.215]) - 1) < 1e-9 and abs(sum([0.065, 0.180, 0.430, 0.185, 0.140]) - 1) < 1e-9
_short = ["\\begin{tabular}{" + _cols([0.065, 0.240, 0.480, 0.215]) + "}\\toprule", "No. & Term & Definition & Applied in \\\\ \\midrule"]
_full = ["\\begin{longtable}{" + _cols([0.065, 0.180, 0.430, 0.185, 0.140]) + "}", "\\caption{Definitions of the measures used in this paper (full form)}\\label{tab:defs_full}\\\\", "\\toprule No. & Term & Conceptual and operational definition & Source & Applied in \\\\ \\midrule \\endfirsthead",
         "\\multicolumn{5}{l}{\\footnotesize Table~\\thetable\\ (continued)}\\\\ \\toprule No. & Term & Conceptual and operational definition & Source & Applied in \\\\ \\midrule \\endhead",
         "\\midrule\\multicolumn{5}{r}{\\footnotesize continued on next page}\\\\ \\endfoot", "\\bottomrule \\endlastfoot"]
_brk = lambda s: s.replace("~", " ")   # the Source and Applied-in columns are narrow: let "equation (3.1)" and "Section 3.2" break at the space
for d in DEFS:
    _short.append(f"{d[0]} & {d[1]} & {d[2]} & {_brk(d[5])} \\\\ \\addlinespace[1pt]")
    _full.append(f"{d[0]} & {d[1]} & {d[3]} & {_brk(d[4])} & {_brk(d[5])} \\\\ \\addlinespace[2pt]")
_short.append("\\bottomrule\\end{tabular}"); _full.append("\\end{longtable}")
(OUT / "defs_short.tex").write_text("\n".join(_short) + "\n"); (OUT / "defs_full.tex").write_text("\n".join(_full) + "\n")
nums["NDefs"] = str(len(DEFS))

# ---- Asset-side measures from the schedules of investments (referee item 3b): results/soi_asset_side_v3.json, results/nonaccrual_v3.json
SOI = J("soi_asset_side_v3.json")["pairs"]; NA = J("nonaccrual_v3.json")["entities"]
MAIN_PAIRS = ["BCRED-BXSL", "OCIC-OBDC", "OTIC-OBDC", "ASIF-ARCC", "GCRED-GBDC", "OSCF-OCSL", "PCAP-NCDL"]   # ADS-MFIC omitted: Apollo's identifiers are not reliably parseable across the two vehicles
ANCHORS = ["2024-12-31", "2025-12-31", "2026-06-30"]
NUMWORD = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
def na_cell(ent, d):
    rec = NA.get(ent, {}).get(d); v = rec and rec.get("report_date_value")
    if not v: return "n.s."
    if v["pct"] is None:
        n_ = NUMWORD.get(v.get("count_word"), v.get("count_word")); return f"{n_} {'co.' if n_ == 1 else 'cos.'}$^{{c}}$"
    return ("$<$" if v.get("lt") else "") + r(v["pct"], 1) + ("$^{b}$" if v["basis"] == "amortized cost" else "") + ("$^{d}$" if v.get("from_other_filing") else "")
rows = []
for pr in MAIN_PAIRS:
    f, t = pr.split("-")
    for d in ANCHORS:
        x = SOI[pr].get(d)
        if not x: continue
        tr = x["tranches"]
        rows.append(f"{f}--{t} & {d[:7]} & {x['n_common_issuers']} & {r(100*x['overlap_fv_share_fund'],0)} & {r(100*x['overlap_fv_share_twin'],0)} & {tr['n']} & {r(100*(tr['fv_share_fund'] or 0),0)} & {r(tr['wmean_diff_bp'],0)} & {r(tr['median_diff_bp'],0)} & {r(100*tr['share_within_10bp_fvw'],0)} & {na_cell(f, d)} & {na_cell(t, d)} \\\\")
w("marks", "\\begin{tabular}{llrrrrrrrrrr}\\toprule\n & & \\multicolumn{3}{c}{Issuer overlap} & \\multicolumn{5}{c}{Marks on matched groups (fair value / principal)} & \\multicolumn{2}{c}{Non-accrual (\\%, FV)} \\\\ \\cmidrule(lr){3-5}\\cmidrule(lr){6-10}\\cmidrule(lr){11-12}\n" + " & ".join(["Fund--twin", "Quarter", H("Common|issuers"), H("Fund|(\\% of|debt FV)"), H("Twin|(\\% of|debt FV)"), H("Matched|groups"), H("Fund debt|FV covered|(\\%)"), H("FV-weighted|mean diff.|(bp)$^{a}$"), H("Median|diff.|(bp)"), H("Within|10 bp|(\\% of FV)"), "Fund", "Twin"]) + " \\\\ \\midrule\n" + "\n".join(rows) + "\n\\bottomrule\\end{tabular}")
# quarterly appendix table: overlap and weighted mean difference per quarter, all pairs
qs = sorted({d for pr in MAIN_PAIRS for d in SOI[pr]})
head = "Quarter & " + " & ".join(H(pr.split("-")[0] + "|" + pr.split("-")[1]) for pr in MAIN_PAIRS) + " \\\\ \\midrule"
r1 = []; r2 = []; r3 = []
for d in qs:
    r1.append(f"{d[:7]} & " + " & ".join(r(100*SOI[pr][d]['overlap_fv_share_fund'],0) if d in SOI[pr] else "" for pr in MAIN_PAIRS) + " \\\\")
    r2.append(f"{d[:7]} & " + " & ".join(r(SOI[pr][d]['tranches']['wmean_diff_bp'],0) if d in SOI[pr] and SOI[pr][d]['tranches']['wmean_diff_bp'] is not None else "" for pr in MAIN_PAIRS) + " \\\\")
    r3.append(f"{d[:7]} & " + " & ".join(r(100*SOI[pr][d]['tranches']['share_within_10bp_fvw'],0) if d in SOI[pr] and SOI[pr][d]['tranches']['share_within_10bp_fvw'] is not None else "" for pr in MAIN_PAIRS) + " \\\\")
w("marks_quarterly", "\\begin{tabular}{l" + "r"*len(MAIN_PAIRS) + "}\\toprule\n" + head + "\n\\multicolumn{" + str(len(MAIN_PAIRS)+1) + "}{l}{\\emph{Panel A. Issuer overlap: fund debt FV held by the twin's issuers (\\%)}} \\\\\n" + "\n".join(r1) + "\n\\midrule\\multicolumn{" + str(len(MAIN_PAIRS)+1) + "}{l}{\\emph{Panel B. FV-weighted mean mark difference, fund minus twin (bp)}} \\\\\n" + "\n".join(r2) + "\n\\midrule\\multicolumn{" + str(len(MAIN_PAIRS)+1) + "}{l}{\\emph{Panel C. Matched FV marked within 10 bp of the twin (\\%)}} \\\\\n" + "\n".join(r3) + "\n\\bottomrule\\end{tabular}")
# largest discrepancies at the latest common quarter, three per pair
lr = []
for pr in MAIN_PAIRS:
    d = max((q for q in SOI[pr] if SOI[pr][q]["tranches"]["wmean_diff_bp"] is not None), key=lambda q: abs(SOI[pr][q]["tranches"]["wmean_diff_bp"])); x = SOI[pr][d]
    nums[f"MarkWorstQ{pr.split('-')[0]}"] = d[:7]
    for k in x["largest_abs_diffs"][:3]:
        if not (0.02 <= k["mark_fund"] <= 1.5 and 0.02 <= k["mark_twin"] <= 1.5): continue
        lab = (k.get("issuer_label") or k["ids_fund"][0].split("|")[0]).strip().replace("&", "\\&")   # full label as tagged (an earlier 46-character cut split words)
        fac = " / ".join(x for x in (k.get("seniority"), k.get("facility")) if x) or "n/a"
        lr.append(f"{pr.replace('-', '--')} & {d[:7]} & {lab} & {fac} & {r(100*k['mark_fund'],1)} & {r(100*k['mark_twin'],1)} & {r(k['diff_bp'],0)} & {r(k['fv_fund']/1e6,1)} & {r(k['fv_twin']/1e6,1)} \\\\")
w("marks_largest", "\\begin{tabular}{ll>{\\raggedright\\arraybackslash}p{4.3cm}>{\\raggedright\\arraybackslash}p{3.1cm}rrrrr}\\toprule\n" + " & ".join(["Fund--twin", "Quarter", "Issuer (as tagged by the fund)", "Seniority / facility", H("Fund mark|(\\% of par)"), H("Twin mark|(\\% of par)"), H("Difference|(bp)"), H("Fund|position|(\\$m, FV)"), H("Twin|position|(\\$m, FV)")]) + " \\\\ \\midrule\n" + "\n".join(lr) + "\n\\bottomrule\\end{tabular}")
# The manuscript sets the same rows as a longtable on a rotated page: as a rotated float the 21 rows (526pt) plus caption and note
# exceed the 469.75pt text width; the standalone PDF above stays in the replication package.
_hdr = " & ".join(["Fund--twin", "Quarter", "Issuer (as tagged by the fund)", "Seniority / facility", H("Fund mark|(\\% of par)"), H("Twin mark|(\\% of par)"), H("Difference|(bp)"), H("Fund|position|(\\$m, FV)"), H("Twin|position|(\\$m, FV)")])
# Measured at footnotesize/12pt: natural widths of the l and r columns sum to 329.0pt (GCRED--GBDC 71.7, Quarter 34.5, five numeric
# headers 222.9); "first lien / delayed draw" is 105.1pt; with \tabcolsep=3pt (set by the manuscript wrapper) the eight inner gaps take 48pt;
# the issuer column receives the rest of the line (164.4pt on the 647.5pt landscape block), which keeps 15 of the 21 labels on one line.
(OUT / "T_marks_largest_long.tex").write_text(
    "\\begin{longtable}{@{}ll>{\\raggedright\\arraybackslash}p{\\dimexpr\\linewidth-483.1pt\\relax}>{\\raggedright\\arraybackslash}p{106pt}rrrrr@{}}\n"
    "\\caption{Largest mark differences on matched groups, three per pair}\\label{tab:marks_largest}\\\\\n"
    "\\toprule " + _hdr + " \\\\ \\midrule \\endfirsthead\n"
    "\\multicolumn{9}{@{}l}{\\footnotesize Table~\\thetable\\ (continued)}\\\\ \\toprule " + _hdr + " \\\\ \\midrule \\endhead\n"
    "\\midrule\\multicolumn{9}{r@{}}{\\footnotesize continued on next page}\\\\ \\endfoot\n"
    "\\bottomrule \\endlastfoot\n" + "\n".join(lr) + "\n\\end{longtable}\n")
# macros
import statistics
latest = {pr: max(SOI[pr]) for pr in MAIN_PAIRS}
ov = [100*SOI[pr][latest[pr]]["overlap_fv_share_fund"] for pr in MAIN_PAIRS]
ov5 = [100*SOI[pr][latest[pr]]["overlap_fv_share_fund"] for pr in MAIN_PAIRS if pr != "OSCF-OCSL"]
nums.update({"SOIPairs": str(len(MAIN_PAIRS)), "SOIQuarters": str(len(qs)), "SOIFirstQ": qs[0][:7], "SOILastQ": qs[-1][:7],
             "OverlapLatestMin": r(min(ov), 0), "OverlapLatestMax": r(max(ov), 0), "OverlapOSCF": r(100*SOI["OSCF-OCSL"][latest["OSCF-OCSL"]]["overlap_fv_share_fund"], 0),
             "OverlapExOaktreeMin": r(min(ov5), 0), "OverlapExOaktreeMax": r(max(ov5), 0),
             "OverlapBXSLofTwin": r(100*SOI["BCRED-BXSL"][latest["BCRED-BXSL"]]["overlap_fv_share_twin"], 0)})
allpd = [(pr, d, SOI[pr][d]["tranches"]) for pr in MAIN_PAIRS for d in SOI[pr] if SOI[pr][d]["tranches"]["wmean_diff_bp"] is not None]
wm = [t["wmean_diff_bp"] for _, _, t in allpd]; w10 = [t["share_within_10bp_fvw"] for _, _, t in allpd]
nums.update({"MarkPairQuarters": str(len(allpd)), "MarkWmeanAbsLeTen": str(sum(1 for v in wm if abs(v) <= 10)), "MarkWmeanAbsLeFive": str(sum(1 for v in wm if abs(v) <= 5)),
             "MarkWmeanMin": r(min(wm), 0), "MarkWmeanMax": r(max(wm), 0), "MarkWithinTenMedian": r(100*statistics.median(w10), 0), "MarkWithinTenMin": r(100*min(w10), 0),
             "MarkTranchesLatestTotal": str(sum(SOI[pr][latest[pr]]["tranches"]["n"] for pr in MAIN_PAIRS))})
worst = max(allpd, key=lambda z: abs(z[2]["wmean_diff_bp"])); nums.update({"MarkWorstPair": worst[0].replace("-", "--"), "MarkWorstQ": worst[1][:7], "MarkWorstBp": r(worst[2]["wmean_diff_bp"], 0)})
neg = sum(1 for v in wm if v < 0); nums["MarkWmeanNegCount"] = str(neg)
# term-only robustness pooled
to = [SOI[pr][d]["tranches_term_only"] for pr in MAIN_PAIRS for d in SOI[pr] if SOI[pr][d]["tranches_term_only"]["wmean_diff_bp"] is not None]
nums.update({"MarkTermWmeanMin": r(min(t["wmean_diff_bp"] for t in to), 0), "MarkTermWmeanMax": r(max(t["wmean_diff_bp"] for t in to), 0), "MarkTermWithinTenMedian": r(100*statistics.median(t["share_within_10bp_fvw"] for t in to), 0)})
# non-accrual macros at latest anchor
for ent in ["BCRED", "BXSL", "OCIC", "OTIC", "OBDC", "ASIF", "ARCC", "GCRED", "GBDC", "OSCF", "OCSL", "PCAP", "NCDL", "MFIC", "ADS", "HLEND", "FPCF"]:
    for d in ANCHORS:
        v = NA.get(ent, {}).get(d, {}).get("report_date_value")
        if v and v["pct"] is not None: nums[f"NAcc{ent}{d[:7].replace('-', '')}"] = r(v["pct"], 1)
# PCAP-NCDL 2025Q4 and BCRED-BXSL 2025Q4 specific
nums["MarkPCAPQfour"] = r(SOI["PCAP-NCDL"]["2025-12-31"]["tranches"]["wmean_diff_bp"], 0); nums["MarkBCREDQfour"] = r(SOI["BCRED-BXSL"]["2025-12-31"]["tranches"]["wmean_diff_bp"], 0)
nums["MarkASIFWithinTen"] = r(100*SOI["ASIF-ARCC"][latest["ASIF-ARCC"]]["tranches"]["share_within_10bp_fvw"], 0)
nums["MarkPCAPQone"] = r(SOI["PCAP-NCDL"]["2026-03-31"]["tranches"]["wmean_diff_bp"], 0); nums["MarkOCICQone"] = r(SOI["OCIC-OBDC"]["2026-03-31"]["tranches"]["wmean_diff_bp"], 0); nums["MarkBCREDQoneTwentyFour"] = r(SOI["BCRED-BXSL"]["2024-03-31"]["tranches"]["wmean_diff_bp"], 0)
nums["NonUSDShareBCRED"] = r(100*SOI["BCRED-BXSL"][latest["BCRED-BXSL"]]["fv_nonusd_share_fund"], 0); nums["NonUSDShareOSCF"] = r(100*SOI["OSCF-OCSL"][latest["OSCF-OCSL"]]["fv_nonusd_share_fund"], 0)
nums["NonUSDShareMaxOther"] = r(100*max(SOI[pr][latest[pr]]["fv_nonusd_share_fund"] or 0 for pr in MAIN_PAIRS if pr not in ("BCRED-BXSL", "OSCF-OCSL")), 1)
_ex = sorted([(abs(SOI[pr][d]["tranches"]["wmean_diff_bp"]), SOI[pr][d]["tranches"]["wmean_diff_bp"], pr, d) for pr in MAIN_PAIRS for d in SOI[pr] if SOI[pr][d]["tranches"]["wmean_diff_bp"] is not None and abs(SOI[pr][d]["tranches"]["wmean_diff_bp"]) > 10], reverse=True)
for _, v, pr, d in _ex: nums[f"MarkEx{pr.split('-')[0]}{d[:7].replace('-', '')}"] = r(v, 0)
nums["MarkGtTenCount"] = str(len(_ex)); _rest = [v for _, v, _, _ in _ex[1:]]; nums["MarkExRestLo"] = r(min(_rest), 0); nums["MarkExRestHi"] = r(max(_rest), 0)
_ot = [v for _, v, pr, _ in _ex if pr == "OTIC-OBDC"]; nums["MarkOTICExCount"] = str(len(_ot)); nums["MarkOTICExLo"] = r(min(_ot), 0) if _ot else "n/a"; nums["MarkOTICExHi"] = r(max(_ot), 0) if _ot else "n/a"; nums["MarkOTICQuarters"] = str(len(SOI["OTIC-OBDC"]))
_nv = [k for k in SOI["PCAP-NCDL"]["2025-12-31"]["largest_abs_diffs"][:3] if 0.02 <= k["mark_fund"] <= 1.5]
nums["MarkNuveenLoPct"] = r(100*min(k["mark_fund"] for k in _nv), 0); nums["MarkNuveenHiPct"] = r(100*max(k["mark_fund"] for k in _nv), 0); nums["MarkNuveenTwinLoPct"] = r(100*min(k["mark_twin"] for k in _nv), 0)
nums["MarkTranchesLatestTotal"] = f"{sum(SOI[pr][latest[pr]]['tranches']['n'] for pr in MAIN_PAIRS):,}"
nums["MarkBCREDQtwoTwentyFour"] = r(SOI["BCRED-BXSL"]["2024-06-30"]["tranches"]["wmean_diff_bp"], 0); nums["MarkASIFWmean"] = r(SOI["ASIF-ARCC"][latest["ASIF-ARCC"]]["tranches"]["wmean_diff_bp"], 0)
nums["MarkPCAPQfourTerm"] = r(SOI["PCAP-NCDL"]["2025-12-31"]["tranches_term_only"]["wmean_diff_bp"], 1)
nums["MarkTermLeTen"] = str(sum(1 for t in to if abs(t["wmean_diff_bp"]) <= 10)); nums["MarkASIFTermWithinTen"] = r(100*SOI["ASIF-ARCC"][latest["ASIF-ARCC"]]["tranches_term_only"]["share_within_10bp_fvw"], 0)
_unres = sum(SOI[pr][d]["n_unit_unresolved_fund"] + SOI[pr][d]["n_unit_unresolved_twin"] for pr in MAIN_PAIRS for d in SOI[pr])
nums["MarkUnresolvedPhrase"] = "no line in these filings carried a unit that did not resolve" if _unres == 0 else f"{_unres} lines in these filings carried a unit that did not resolve and were excluded"
nums["MarkUnresolvedUnits"] = str(sum(SOI[pr][d]["n_unit_unresolved_fund"] + SOI[pr][d]["n_unit_unresolved_twin"] for pr in MAIN_PAIRS for d in SOI[pr]))
import importlib.util as _iu
_sp = _iu.spec_from_file_location("_m", BASE / "code" / "soi_asset_side_measures_v3.py"); _m = _iu.module_from_spec(_sp); _sp.loader.exec_module(_m)
def _round_share(entity, unit):
    f = _m.latest_original(entity)[max(_m.latest_original(entity))]; L = [l for l in _m.lines_for(f) if l["fv"] and l["fv"] > 0 and l["principal"] and l["principal"] > 0]
    return 100 * sum(1 for l in L if abs(l["fv"] / unit - round(l["fv"] / unit)) < 1e-6) / len(L)
nums["ARCCRoundHundredK"] = r(_round_share("ARCC", 1e5), 0); nums["ASIFRoundHundredK"] = r(_round_share("ASIF", 1e5), 0)
def _contrib(fund, twin, d):
    """share of the pair-quarter weighted mean carried by the two groups with the largest |diff × fund FV|, and sign counts of the rest (> 0.5 bp)."""
    from collections import defaultdict
    ff = _m.latest_original(fund)[d]; tf = _m.latest_original(twin)[d]; Lf = _m.lines_for(ff); Lt = _m.lines_for(tf)
    is_debt = lambda l: bool(l["principal"]) and l["principal"] > 0 and l["fv"] is not None and l["fv"] > 0 and (l["cost"] is None or l["cost"] > 0)
    usd = lambda l: (l.get("principal_unit") or "").endswith("iso4217:usd") and (l.get("fv_unit") or "").endswith("iso4217:usd") and _m.currency_tag(l["identifier"]) is None
    kf = defaultdict(list); kt = defaultdict(list)
    for l in Lf:
        if is_debt(l) and usd(l): kf[_m.tranche_key(l)].append(l)
    for l in Lt:
        if is_debt(l) and usd(l): kt[_m.tranche_key(l)].append(l)
    rows = []
    for k in set(kf) & set(kt):
        if k[1] is None and k[2] is None: continue
        a, b = kf[k], kt[k]; mf = sum(x["fv"] for x in a) / sum(x["principal"] for x in a); mt = sum(x["fv"] for x in b) / sum(x["principal"] for x in b)
        if 0.02 <= mf <= 1.5 and 0.02 <= mt <= 1.5: rows.append(((mf - mt) * 1e4, sum(x["fv"] for x in a)))
    W = sum(w for _, w in rows); wm = sum(dd * w for dd, w in rows) / W
    top = sorted(rows, key=lambda rr: -abs(rr[0] * rr[1]))[:2]; rest = [rr for rr in rows if rr not in top]
    return dict(share=sum(dd * w for dd, w in top) / W / wm, pos=sum(1 for dd, _ in rest if dd > 0.5), neg=sum(1 for dd, _ in rest if dd < -0.5), zero=sum(1 for dd, _ in rest if abs(dd) <= 0.5), wm=wm)
_cb = _contrib("BCRED", "BXSL", "2024-03-31")
nums["MarkBCREDTopTwoShare"] = r(100*_cb["share"], 0); nums["MarkBCREDRestPos"] = str(_cb["pos"]); nums["MarkBCREDRestNeg"] = str(_cb["neg"]); nums["MarkBCREDRestZero"] = str(_cb["zero"])
_bx = sorted(SOI["BCRED-BXSL"]["2024-03-31"]["largest_abs_diffs"], key=lambda k: -abs(k["diff_bp"] * k["fv_fund"]))[:2]
for i, k in enumerate(_bx):
    tag = "One" if i == 0 else "Two"
    nums[f"BXPos{tag}Name"] = re.sub(r"\s+\d+$", "", (k.get("issuer_label") or "").strip()).replace("&", "\\&"); nums[f"BXPos{tag}Fund"] = r(100*k["mark_fund"], 1); nums[f"BXPos{tag}Twin"] = r(100*k["mark_twin"], 1); nums[f"BXPos{tag}FV"] = r(k["fv_fund"]/1e6, 0); nums[f"BXPos{tag}TwinFV"] = r(k["fv_twin"]/1e6, 0)
nums["DiscAvgBZBFQAabs"] = r(abs(TD["avg_disc_by_avail_q"]["2026Q1"]), 1)
nums["MarkExcludedGroupsTotal"] = str(sum(SOI[pr][d]["tranches"]["n_excluded_implausible"] for pr in MAIN_PAIRS for d in SOI[pr]))
nums["MarkExcludedGroupsLatest"] = str(sum(SOI[pr][latest[pr]]["tranches"]["n_excluded_implausible"] for pr in MAIN_PAIRS))
def _rows(fund, twin, d, use_rate=True):
    from collections import defaultdict
    Lf = _m.lines_for(_m.latest_original(fund)[d]); Lt = _m.lines_for(_m.latest_original(twin)[d])
    is_debt = lambda l: bool(l["principal"]) and l["principal"] > 0 and l["fv"] is not None and l["fv"] > 0 and (l["cost"] is None or l["cost"] > 0)
    usd = lambda l: (l.get("principal_unit") or "").endswith("iso4217:usd") and (l.get("fv_unit") or "").endswith("iso4217:usd") and _m.currency_tag(l["identifier"]) is None
    key = lambda l: _m.tranche_key(l) if use_rate else (_m.tranche_key(l)[0], _m.tranche_key(l)[1], None, _m.tranche_key(l)[3], _m.tranche_key(l)[4])
    kf = defaultdict(list); kt = defaultdict(list)
    for l in Lf:
        if is_debt(l) and usd(l): kf[key(l)].append(l)
    for l in Lt:
        if is_debt(l) and usd(l): kt[key(l)].append(l)
    out = []
    for k in set(kf) & set(kt):
        if k[1] is None and k[2] is None: continue
        a, b = kf[k], kt[k]; mf = sum(x["fv"] for x in a) / sum(x["principal"] for x in a); mt = sum(x["fv"] for x in b) / sum(x["principal"] for x in b)
        if 0.02 <= mf <= 1.5 and 0.02 <= mt <= 1.5: out.append(((mf - mt) * 1e4, sum(x["fv"] for x in a), sum(x["fv"] for x in b)))
    return out
def _w10(rows): return 100 * sum(w for dd, w, _ in rows if abs(dd) <= 10) / sum(w for _, w, _ in rows)
for fund, twin, tag in (("BCRED", "BXSL", "BX"), ("GCRED", "GBDC", "GC")):
    nums[f"FourField{tag}WithRate"] = r(_w10(_rows(fund, twin, latest[f"{fund}-{twin}"])), 0); nums[f"FourField{tag}NoRate"] = r(_w10(_rows(fund, twin, latest[f"{fund}-{twin}"], use_rate=False)), 0)
_r = _rows("BCRED", "BXSL", "2024-03-31"); nums["MarkBCREDQoneTwinW"] = r(sum(dd * wt for dd, _, wt in _r) / sum(wt for _, _, wt in _r), 0)
_gr = {pr: (100 * (SOI[pr]["2026-06-30"]["fv_debt_fund"] / SOI[pr]["2024-12-31"]["fv_debt_fund"] - 1), 100 * (SOI[pr]["2026-06-30"]["fv_debt_twin"] / SOI[pr]["2024-12-31"]["fv_debt_twin"] - 1)) for pr in MAIN_PAIRS}
nums["GrowthFundMin"] = r(min(v[0] for v in _gr.values()), 0); nums["GrowthFundMax"] = r(max(v[0] for v in _gr.values()), 0); nums["GrowthTwinMin"] = r(min(v[1] for v in _gr.values()), 0); nums["GrowthTwinMax"] = r(max(v[1] for v in _gr.values()), 0)
nums["GrowthFundOTIC"] = r(_gr["OTIC-OBDC"][0], 0); nums["GrowthFundGCRED"] = r(_gr["GCRED-GBDC"][0], 0); nums["GrowthFundPCAP"] = r(_gr["PCAP-NCDL"][0], 0); nums["GrowthFundASIF"] = r(_gr["ASIF-ARCC"][0], 0)
_cov = [100 * SOI[pr][latest[pr]]["tranches"]["fv_share_fund"] for pr in MAIN_PAIRS if pr != "OSCF-OCSL"]
nums["CoverageExOaktreeMin"] = r(min(_cov), 0); nums["CoverageExOaktreeMax"] = r(max(_cov), 0); nums["CoverageOSCF"] = r(100 * SOI["OSCF-OCSL"][latest["OSCF-OCSL"]]["tranches"]["fv_share_fund"], 0)
nums["OverlapOCSLofTwin"] = r(100 * SOI["OSCF-OCSL"][latest["OSCF-OCSL"]]["overlap_fv_share_twin"], 0)
_names = {"BCRED": "Blackstone", "OCIC": "Blue Owl (diversified)", "OTIC": "Blue Owl (technology)", "ASIF": "Ares", "GCRED": "Golub", "OSCF": "Oaktree", "PCAP": "Nuveen"}
_exl = sorted(_ex, key=lambda z: (z[2], z[3]))
_parts = []
for _, v, pr, d in _exl:
    _parts.append(f"{_names[pr.split('-')[0]]} at {d[:7]} ({r(v, 0)})")
nums["MarkExList"] = "; ".join(_parts)
nums["FourFieldPhrase"] = ("leaves Blackstone's share at " + nums["FourFieldBXWithRate"] + " percent" if nums["FourFieldBXWithRate"] == nums["FourFieldBXNoRate"] else "moves Blackstone's share from " + nums["FourFieldBXWithRate"] + " to " + nums["FourFieldBXNoRate"] + " percent") + \
                           (" and Golub's at " + nums["FourFieldGCWithRate"] if nums["FourFieldGCWithRate"] == nums["FourFieldGCNoRate"] else " and moves Golub's from " + nums["FourFieldGCWithRate"] + " to " + nums["FourFieldGCNoRate"]) + " percent"
_nv3 = [k for k in SOI["PCAP-NCDL"]["2025-12-31"]["largest_abs_diffs"] if 0.02 <= k["mark_fund"] <= 1.5][:3]
nums["NuveenThree"] = "; ".join(f"{re.sub(r'\s+\d+$', '', k['issuer_label'].strip()).replace('&', chr(92)+'&')} (\\${r(k['fv_fund']/1e6, 1)} million at the fund, marked {r(100*k['mark_fund'], 0)} against {r(100*k['mark_twin'], 0)} percent at the twin, which held \\${r(k['fv_twin']/1e6, 1)} million)" for k in _nv3)
_gt20 = [(pr, d, v) for _, v, pr, d in _ex if abs(v) > 20 and not (pr == "PCAP-NCDL" and d == "2025-12-31")]
nums["MarkGtTwentyOthers"] = "; ".join(f"{_names[pr.split('-')[0]]} at {d[:7]} ({r(v, 0)})" for pr, d, v in sorted(_gt20))
nums["MarkGtTwentyOthersN"] = str(len(_gt20))
_xo = G["specs"]["A_fundFE_excl_OSCF"]["coef"]["twin_disc"]; nums["TwinDiscAxo"] = r(_xo["b"], 3); nums["TwinDiscAxot"] = r(_xo["t_cluster"], 2); nums["NRegOffersXO"] = str(G["specs"]["A_fundFE_excl_OSCF"]["n"])
nums["MarkNuveenFacility"] = ", ".join(sorted({k["facility"] or "unclassified" for k in SOI["PCAP-NCDL"]["2025-12-31"]["largest_abs_diffs"][:3]}))
RAWSOI = J("soi_raw_v3.json"); nums["SOIFilings"] = str(len(RAWSOI["filings"])); nums["SOIEntities"] = str(len({f["entity"] for f in RAWSOI["filings"]}))
_ads = [100*SOI["ADS-MFIC"][d]["overlap_fv_share_fund"] for d in SOI["ADS-MFIC"] if d >= "2025-01-01" and SOI["ADS-MFIC"][d]["overlap_fv_share_fund"]]
nums["ADSOverlapLo"] = r(min(_ads), 0); nums["ADSOverlapHi"] = r(max(_ads), 0)

D2L = str.maketrans("0123456789", "ZABCDEFGHI")   # LaTeX macro names cannot contain digits: 2026 -> BZBF
for _k in ("NFundsPurchHalved", "NFundsPurchHalvedInDomain", "NFundsRateRoseFirst", "NCashFundsTwentySix", "NResultSameFunds", "NBaseBefore", "NBaseSame", "NBaseAfter", "NZeroTender", "NFirstWindowsClosedAfterAboveCap", "NFirstWindowsOpenedAfterAboveCap", "NFirstWindowsClosedAfterBlueOwlDec", "NEnlargedByOutcome", "NResultAfter", "NFirstRationedHOne"):
    if _k in nums and str(nums[_k]).isdigit() and int(nums[_k]) <= 10: nums[_k] = WORDS[int(nums[_k])]
import datetime as _dt2; nums["FirstAboveCapDate"] = _dt2.date.fromisoformat(nums["FirstAboveCapDate"]).strftime("%-d %B %Y")
(OUT / "numbers_v3.tex").write_text("\n".join(f"\\newcommand{{\\{k.translate(D2L)}}}{{{v}}}" for k, v in nums.items()) + "\n")
print("tables:", sorted(p.name for p in OUT.glob("T_*.tex"))); print("numbers:", len(nums))
for p in sorted(OUT.glob("T_*.tex")):
    res = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-output-directory", str(OUT), str(p)], capture_output=True, text=True)
    if "!" in res.stdout.split("\n")[-30:].__str__() and not (OUT / (p.stem + ".pdf")).exists(): print("COMPILE ERROR", p.name)
print("pdfs:", len(list(OUT.glob("T_*.pdf"))))
def check_widths():
    import subprocess as sp
    bad = []
    for p in sorted(OUT.glob("T_*.pdf")):
        info = sp.run(["pdfinfo", str(p)], capture_output=True, text=True).stdout
        m = re.search(r"Page size:\s+([0-9.]+) x ([0-9.]+)", info); wpt = float(m.group(1)); hpt = float(m.group(2))
        limit = 630 if p.stem[2:] in LANDSCAPE else 469
        flag = "" if wpt <= limit else "  <-- EXCEEDS"
        if wpt > limit: bad.append(p.name)
        print(f"  {p.name:26s} {wpt:7.1f} x {hpt:6.1f} pt  ({'landscape' if p.stem[2:] in LANDSCAPE else 'portrait'}, limit {limit}){flag}")
    return bad
_bad = check_widths(); print("tables exceeding their slot:", _bad or "none")
