"""m2_regressions_v3.py — Table 6 rebuilt on the offer master. Unit = offer (fund × window). Variables:
 log_t = ln(tendered shares); req_pct = tendered / fund's own denominator (where available);
 twin_disc = listed twin's price-to-book discount (%) from the most recent 10-Q/10-K FILED ON OR BEFORE THE OFFER'S COMMENCEMENT (information available when the window opened);
 news: pre (expiry <= 2026-03-27), straddle (commenced before 27 March, expired after), post (commenced on/after 27 March);
 headroom_i = 5 − requested % in the fund's last 2025 offer (predetermined distance to the cap; smaller = closer to rationing).
Specs: (A) log_t ~ twin_disc + straddle + post | fund FE   (re-dated version of the submitted Table 6)
       (B) log_t ~ twin_disc + straddle + post + lowheadroom×(straddle+post) | fund FE
       (C) log_t ~ twin_disc + lowheadroom×post2026 | fund FE + investor-quarter FE   (common shocks absorbed by quarter FE)
Inference: cluster-robust by fund and wild-cluster bootstrap (Rademacher, full enumeration over fund clusters)."""
import json, itertools
from pathlib import Path
import numpy as np, pandas as pd, statsmodels.formula.api as smf
BASE = Path(__file__).resolve().parent.parent; R = BASE / "results"
M = json.load(open(R / "offer_master_v3.json"))["offers"]; TW = json.load(open(R / "twin_discounts_v3.json"))["twins"]   # NAVPS-based (2026-10-16)
TWIN = {"BCRED": "BXSL", "OCIC": "OBDC", "OTIC": "OBDC", "ASIF": "ARCC", "GCRED": "GBDC", "OSCF": "OCSL"}; NEWS = "2026-03-24"
rows = []
for o in M:
    if not o.get("tendered") or o["fund"] not in TWIN: continue
    recs = [r for r in TW[TWIN[o["fund"]]] if r["filed"] <= o["commencement"]]
    if not recs: continue
    tw = recs[-1]
    rows.append(dict(fund=o["fund"], commencement=o["commencement"], expiry=o["expiry"], sched_expiry=o.get("scheduled_expiry") or o["expiry"], q=pd.Timestamp(o["expiry"]) - pd.Timedelta(days=15), log_t=np.log(o["tendered"]), req_pct=o.get("tendered_pct_basis"), twin_disc=tw["disc_pct"], twin_filed=tw["filed"],
                     news=("post" if o["commencement"] >= NEWS else ("straddle" if o["expiry"] > NEWS else "pre")), prorated=bool(o.get("rationed"))))
df = pd.DataFrame(rows); df["quarter"] = df["q"].dt.to_period("Q").astype(str); df["straddle"] = (df.news == "straddle").astype(int); df["post"] = (df.news == "post").astype(int); df["post2026"] = (df.sched_expiry >= "2026-01-01").astype(int)   # cycle dating: OTIC's extended December-2025 offer is a 2025-cycle offer
hr = {}
for f in df.fund.unique():
    last25 = df[(df.fund == f) & (df.sched_expiry < "2026-01-01") & df.req_pct.notna()].sort_values("sched_expiry")   # last 2025-cycle offer (OTIC's December offer was extended into January)
    hr[f] = 5.0 - last25.req_pct.iloc[-1] if len(last25) else None
df["headroom"] = df.fund.map(hr); med = df.drop_duplicates("fund").headroom.median(); df["lowheadroom"] = (df.headroom < med).astype(int)
# robustness baseline: last offer whose ACTUAL expiry fell in calendar 2025 (for OTIC the September-2025 offer, not the extended December offer)
hr_cal = {}
for f in df.fund.unique():
    lastcal = df[(df.fund == f) & (df.expiry < "2026-01-01") & df.req_pct.notna()].sort_values("expiry"); hr_cal[f] = 5.0 - lastcal.req_pct.iloc[-1] if len(lastcal) else None
df["headroom_cal"] = df.fund.map(hr_cal); med_cal = df.drop_duplicates("fund").headroom_cal.median(); df["lowheadroom_cal"] = (df.headroom_cal < med_cal).astype(int)
print("calendar-expiry headroom:", {k: round(v, 2) for k, v in hr_cal.items()}, "| median", round(med_cal, 2), "| low group:", sorted(df[df.lowheadroom_cal == 1].fund.unique()))
print("headroom by fund (5 − last-2025 request %):", {k: (round(v, 2) if v is not None else None) for k, v in hr.items()}, "| median", round(med, 2))
def wcb(formula, data, coef, cluster):
    m = smf.ols(formula, data).fit(cov_type="cluster", cov_kwds={"groups": data[cluster]}); G = data[cluster].unique(); n = len(G)
    # restricted residuals (impose coef = 0)
    lhs, rhs = formula.split("~"); terms = [t.strip() for t in rhs.split("+")]; f0 = lhs + "~ " + " + ".join(t for t in terms if t != coef)
    m0 = smf.ols(f0, data).fit(); u0 = m0.resid.values; fit0 = m0.fittedvalues.values; t_obs = m.tvalues[coef]; ts = []
    for signs in itertools.product([1, -1], repeat=n):
        w = dict(zip(G, signs)); ystar = fit0 + u0 * data[cluster].map(w).values; d2 = data.copy(); d2["ystar"] = ystar
        mb = smf.ols(formula.replace("log_t", "ystar"), d2).fit(cov_type="cluster", cov_kwds={"groups": d2[cluster]}); ts.append(mb.tvalues[coef])
    ts = np.array(ts); p = float(np.mean(np.abs(ts) >= abs(t_obs) - 1e-9)); return round(float(t_obs), 2), round(p, 4), len(ts)
out = {"n_offers": len(df), "funds": sorted(df.fund.unique().tolist()), "news_counts": df.news.value_counts().to_dict(), "headroom": {k: (round(v, 3) if v is not None else None) for k, v in hr.items()}, "headroom_definition": "5 minus the request rate (percent of shares) in the fund's last 2025-CYCLE offer (scheduled expiry in 2025); OTIC's is its December-2025 offer, extended to 8 January 2026 and reported on 29 January 2026, before any 2026-cycle window opened", "low_headroom_funds": sorted(df[df.lowheadroom == 1].fund.unique().tolist()), "headroom_calendar_expiry": {k: (round(v, 3) if v is not None else None) for k, v in hr_cal.items()}, "low_headroom_funds_calendar_expiry": sorted(df[df.lowheadroom_cal == 1].fund.unique().tolist()), "straddle_note": "both straddling offers (OCIC and OTIC, March 2026) belong to low-headroom funds, so a low-headroom x straddle interaction is perfectly collinear with the straddle dummy and is not estimated; the straddle coefficient in (A) and (B) is the low-headroom straddle effect", "specs": {}}
specs = {"A_fundFE": "log_t ~ twin_disc + straddle + post + C(fund)", "B_fundFE_headroom": "log_t ~ twin_disc + straddle + post + lowheadroom:post + C(fund)", "C_fund_quarterFE_headroom": "log_t ~ twin_disc + lowheadroom:post2026 + C(fund) + C(quarter)", "C_alt_calendar_headroom": "log_t ~ twin_disc + lowheadroom_cal:post2026 + C(fund) + C(quarter)", "C2_fund_quarterFE_disclosure": "log_t ~ twin_disc + lowheadroom:straddle + lowheadroom:post + C(fund) + C(quarter)"}
for name, fml in specs.items():
    m = smf.ols(fml, df).fit(cov_type="cluster", cov_kwds={"groups": df["fund"]}); res = {"formula": fml, "n": int(m.nobs), "r2": round(m.rsquared, 3), "coef": {}}
    for k in m.params.index:
        if k.startswith("C("): continue
        res["coef"][k] = {"b": round(float(m.params[k]), 4), "se_cluster": round(float(m.bse[k]), 4), "t_cluster": round(float(m.tvalues[k]), 2)}
    for key in ("twin_disc", "post", "lowheadroom:post", "lowheadroom:post2026", "lowheadroom_cal:post2026", "lowheadroom:straddle"):
        if key in m.params.index:
            try:
                t, p, nb = wcb(fml, df, key, "fund"); res["coef"][key]["wcb_p"] = p; res["coef"][key]["wcb_n_draws"] = nb; res["coef"][key]["wcb_p_floor"] = round(2 / nb, 4)
                from scipy import stats; G = df["fund"].nunique(); res["coef"][key]["p_cluster_t_Gminus1"] = round(float(2 * (1 - stats.t.cdf(abs(res["coef"][key]["t_cluster"]), G - 1))), 3)
            except Exception as e: res["coef"][key]["wcb_p"] = f"n/a ({str(e)[:40]})"
    out["specs"][name] = res; print(f"\n[{name}] n={res['n']} R2={res['r2']}"); [print(f"   {k:24} b={v['b']:+.4f} se={v['se_cluster']:.4f} t={v['t_cluster']:+.2f}  wcb_p={v.get('wcb_p','-')} (draws {v.get('wcb_n_draws','-')})") for k, v in res["coef"].items()]
# all-ten-fund headroom specifications (no twin discount): fund FE + investor-quarter FE; headroom from each fund's last 2025-cycle offer
rows10 = []
for o in M:
    if not o.get("tendered"): continue
    rows10.append(dict(fund=o["fund"], commencement=o["commencement"], expiry=o["expiry"], sched_expiry=o.get("scheduled_expiry") or o["expiry"], q=pd.Timestamp(o["expiry"]) - pd.Timedelta(days=15), log_t=np.log(o["tendered"]), req_pct=(100 * o["tendered"] / o["shares_outstanding_basis"]) if o.get("shares_outstanding_basis") else o.get("tendered_pct_basis"),
                       news=("post" if o["commencement"] >= NEWS else ("straddle" if o["expiry"] > NEWS else "pre"))))
d10 = pd.DataFrame(rows10); d10["quarter"] = d10["q"].dt.to_period("Q").astype(str); d10["post"] = (d10.news == "post").astype(int); d10["straddle"] = (d10.news == "straddle").astype(int); d10["post2026"] = (d10.sched_expiry >= "2026-01-01").astype(int)
hr10 = {}
for f in d10.fund.unique():
    l = d10[(d10.fund == f) & (d10.sched_expiry < "2026-01-01") & d10.req_pct.notna()].sort_values("sched_expiry"); hr10[f] = 5.0 - l.req_pct.iloc[-1]
d10["headroom"] = d10.fund.map(hr10); med10 = d10.drop_duplicates("fund").headroom.median(); d10["lowheadroom"] = (d10.headroom < med10).astype(int)
out["headroom_all_ten"] = {k: round(v, 3) for k, v in hr10.items()}; out["low_headroom_funds_all_ten"] = sorted(d10[d10.lowheadroom == 1].fund.unique().tolist())
for name, fml in (("D_allten_fund_quarterFE_cycle", "log_t ~ lowheadroom:post2026 + C(fund) + C(quarter)"), ("D2_allten_fund_quarterFE_disclosure", "log_t ~ lowheadroom:straddle + lowheadroom:post + C(fund) + C(quarter)")):
    m = smf.ols(fml, d10).fit(cov_type="cluster", cov_kwds={"groups": d10["fund"]}); res = {"formula": fml + "  [all ten funds, no twin discount]", "n": int(m.nobs), "r2": round(m.rsquared, 3), "coef": {}}
    for k in m.params.index:
        if k.startswith("C("): continue
        res["coef"][k] = {"b": round(float(m.params[k]), 4), "se_cluster": round(float(m.bse[k]), 4), "t_cluster": round(float(m.tvalues[k]), 2)}
        if k != "Intercept":
            from scipy import stats; res["coef"][k]["p_cluster_t_Gminus1"] = round(float(2 * (1 - stats.t.cdf(abs(res["coef"][k]["t_cluster"]), d10["fund"].nunique() - 1))), 3)
            try:
                t_, p_, nb = wcb(fml, d10, k, "fund"); res["coef"][k]["wcb_p"] = p_; res["coef"][k]["wcb_n_draws"] = nb; res["coef"][k]["wcb_p_floor"] = round(2 / nb, 4)
            except Exception as e: res["coef"][k]["wcb_p"] = f"n/a ({str(e)[:40]})"
    out["specs"][name] = res; print(f"\n[{name}] n={res['n']} R2={res['r2']}"); [print(f"   {k:24} b={v['b']:+.4f} se={v['se_cluster']:.4f} t={v['t_cluster']:+.2f} wcb_p={v.get('wcb_p','-')}") for k, v in res["coef"].items() if k != "Intercept"]
# robustness: drop each fund's FIRST offer (start-up windows in which most shares were still inside the early-repurchase-deduction year; ASIF's first offer drew 2,955 shares)
dfx = df[df.groupby("fund").commencement.transform("min") != df.commencement].copy()
mx = smf.ols(specs["A_fundFE"], dfx).fit(cov_type="cluster", cov_kwds={"groups": dfx["fund"]})
out["specs"]["A_fundFE_excl_first_offers"] = {"formula": specs["A_fundFE"] + "  [each fund's first offer dropped]", "n": int(mx.nobs), "r2": round(mx.rsquared, 3), "coef": {k: {"b": round(float(mx.params[k]), 4), "se_cluster": round(float(mx.bse[k]), 4), "t_cluster": round(float(mx.tvalues[k]), 2)} for k in mx.params.index if not k.startswith("C(")}}
print("[A excl. first offers]", {k: (v["b"], v["t_cluster"]) for k, v in out["specs"]["A_fundFE_excl_first_offers"]["coef"].items() if k != "Intercept"})
# robustness: drop Oaktree's pair (the schedules of investments show OSCF and OCSL share only ~12% of OSCF's book, Section 5.6)
dfo = df[df.fund != "OSCF"].copy()
mo = smf.ols(specs["A_fundFE"], dfo).fit(cov_type="cluster", cov_kwds={"groups": dfo["fund"]})
out["specs"]["A_fundFE_excl_OSCF"] = {"formula": specs["A_fundFE"] + "  [Oaktree pair dropped]", "n": int(mo.nobs), "r2": round(mo.rsquared, 3), "coef": {k: {"b": round(float(mo.params[k]), 4), "se_cluster": round(float(mo.bse[k]), 4), "t_cluster": round(float(mo.tvalues[k]), 2)} for k in mo.params.index if not k.startswith("C(")}}
print("[A excl. OSCF]", {k: (v["b"], v["t_cluster"]) for k, v in out["specs"]["A_fundFE_excl_OSCF"]["coef"].items() if k != "Intercept"})
out["sample_note"] = "offers with positive gross requests and a listed-twin discount available at commencement; two zero-tender offers (PCAP December 2023, Golub May 2024) cannot enter a log specification and are excluded"
df_out = df.drop(columns=["q"]); df_out.to_csv(R / "m2_regression_sample_v3.csv", index=False); out["sample_file"] = "m2_regression_sample_v3.csv"
json.dump(out, open(R / "m2_regressions_v3.json", "w"), indent=1); print("\nsaved; news counts", out["news_counts"])
