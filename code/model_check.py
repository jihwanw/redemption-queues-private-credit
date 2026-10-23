"""
model_check.py -- numerical verification of Appendix A (two-period queue model, revised 2026-10-09).

Choice set (period 1): tender now / WAIT and decide in period 2 / never tender.
The value of waiting W2 is explicit; the JFSR-submitted version omitted it and had the wrong
sign on dε*/dE[f2] (referee comment 1, 2026-10-09).

Checks
  1. the closed-form threshold eps_star equals the boundary of the brute-force tender rule
  2. signs: d eps*/d E[f2] < 0 (preemption), d eps*/d pi > 0 (valuation), independence from f1
  3. the analytic derivative -delta^2 pi / (1 + delta - delta E[f2])^2 matches a numerical derivative
  4. stock-flow identity T_{n+1} = (1-f) T_n + N_{n+1}  <=>  N_{n+1} = T_{n+1} - Unfilled_n
Writes results/model_check.json; the appendix and hypotheses cite only the signs recorded there.
"""
import itertools, json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

def W2(e, v, d, x):            # value of entering period 2 untendered; x = E[f2]
    return e + d * v + x * max(0.0, 1 - e - d * v)

def tender_now(e, v, d, x, f1=0.5):
    now = f1 * 1.0 + (1 - f1) * (e + d * W2(e, v, d, x))
    wait = e + d * W2(e, v, d, x)
    return now - wait >= -1e-12   # equivalent to 1 - d*W2 >= e when f1 > 0

def eps_star(v, d, x):
    return (1 - d * d * v - d * x * (1 - d * v)) / (1 + d - d * x)

def d_eps_dx_analytic(v, d, x):
    pi = 1 - v
    return -(d * d * pi) / (1 + d - d * x) ** 2

out = {"meta": {"appendix": "A two-period queue model (revised 2026-10-09)",
                "choice_set": ["tender now", "wait", "never"], "wait_value_explicit": True},
       "checks": {}, "grid": []}
ok_boundary = ok_signs = ok_deriv = ok_f1 = True
h = 1e-6
for v, d, x in itertools.product([0.70, 0.80, 0.90, 0.97], [0.85, 0.95, 1.0], [0.2, 0.4, 0.6, 0.8, 0.95]):
    es = eps_star(v, d, x)
    pi = 1 - v
    # 1. boundary
    below, above = tender_now(es - 1e-6, v, d, x), tender_now(es + 1e-6, v, d, x)
    if not (below and not above):
        ok_boundary = False
    # 2. signs (numerical)
    dx = (eps_star(v, d, min(x + h, 1.0)) - eps_star(v, d, x - h)) / (min(x + h, 1.0) - (x - h))
    dpi = (eps_star(v - h, d, x) - eps_star(v + h, d, x)) / (2 * h)   # v down = pi up
    if not (dx < 0 and dpi > 0):
        ok_signs = False
    # 3. analytic vs numerical derivative
    if abs(dx - d_eps_dx_analytic(v, d, x)) > 1e-5:
        ok_deriv = False
    # independence from f1
    if any(tender_now(es - 1e-6, v, d, x, f1) != below or tender_now(es + 1e-6, v, d, x, f1) != above
           for f1 in (0.05, 0.3, 0.9, 1.0)):
        ok_f1 = False
    out["grid"].append({"v": v, "delta": d, "E_f2": x, "eps_star": round(es, 6),
                        "d_eps_dEf2": round(dx, 6), "d_eps_dpi": round(dpi, 6)})

# 4. stock-flow identity on the observed Q2->Q3 BCRED numbers (illustrative, not a result)
T_prev, acc_prev, T_cur = 133_689_552, 133_689_552 / 2.0, 191_782_834
unfilled = T_prev - acc_prev
N_floor = T_cur - unfilled
f = acc_prev / T_prev
identity_ok = abs(((1 - f) * T_prev + N_floor) - T_cur) < 1e-6

out["checks"] = {
    "closed_form_is_boundary_of_brute_force_rule": ok_boundary,
    "sign_d_eps_dEf2_negative": ok_signs,
    "sign_d_eps_dpi_positive": ok_signs,
    "analytic_derivative_matches_numerical": ok_deriv,
    "decision_independent_of_f1": ok_f1,
    "stock_flow_identity": identity_ok,
}
out["comparative_statics"] = {
    "valuation_channel": "+ (eps* rises with pi)",
    "queue_channel": "- (eps* falls as E[f2] rises; a proration signal lowering E[f2] raises eps*)",
    "accommodation": "0 (f1 does not enter the tender condition)",
    "amplification_proportional_to_pi": True,
}
Path(BASE / "results").mkdir(exist_ok=True)
json.dump(out, open(BASE / "results" / "model_check.json", "w"), indent=2)
allok = all(out["checks"].values())
print(json.dumps(out["checks"], indent=1))
print("MODEL CHECK", "PASS" if allok else "FAIL", "->", BASE / "results" / "model_check.json")

# ---- headroom kink (added 2026-10-17): common news g raises expected requests; E[f2] = min(1, kappa/T2e); threshold response only where the cap is near
def eps_star_pi(pi, Ef2, delta=1.0):
    v = 1 - pi
    return (1 - delta**2 * v - delta * Ef2 * (1 - delta * v)) / (1 + delta - delta * Ef2)
def headroom_check(pi=0.10, g=0.30):
    out = {}
    for name, ratio in (("high_headroom (expected requests at 50% of cap)", 0.5), ("at_cap (expected requests = cap)", 1.0), ("low_headroom (expected requests at 150% of cap)", 1.5)):
        Ef2_before = min(1.0, 1.0 / ratio); Ef2_after = min(1.0, 1.0 / (ratio * (1 + g)))
        out[name] = {"E_f2_before": round(Ef2_before, 4), "E_f2_after": round(Ef2_after, 4), "eps_star_before": round(eps_star_pi(pi, Ef2_before), 5), "eps_star_after": round(eps_star_pi(pi, Ef2_after), 5), "threshold_change": round(eps_star_pi(pi, Ef2_after) - eps_star_pi(pi, Ef2_before), 5)}
    hi, at, lo = out["high_headroom (expected requests at 50% of cap)"]["threshold_change"], out["at_cap (expected requests = cap)"]["threshold_change"], out["low_headroom (expected requests at 150% of cap)"]["threshold_change"]
    out["PASS"] = bool(hi == 0 and at > 0 and lo > 0)
    return out

# ---- markdown-risk extension (2026-10-17, corrected): period-2 price is 1 w.p. 1-m and v w.p. m; the holder requests in period 2 only if the price exceeds her holding value
def eps_star_m(pi, Ef2, m, delta=1.0):
    v = 1 - pi; x = (1 - m) * Ef2
    return (1 - delta**2 * v - delta * x * (1 - delta * v)) / (1 + delta - delta * x)
def W2_opt(e, pi, Ef2, m, delta=1.0):
    v = 1 - pi
    return e + delta * v + Ef2 * ((1 - m) * max(0.0, 1 - e - delta * v) + m * max(0.0, v - e - delta * v))
def tender_now_m(e, pi, Ef2, m, delta=1.0):
    return 1 - e - delta * W2_opt(e, pi, Ef2, m, delta) >= -1e-12
def markdown_check(pi=0.10, delta=0.98):
    import numpy as np
    out = {}; ok = True
    for Ef2 in (1.0, 0.7, 0.4):
        for mm in (0.0, 0.3, 0.6):
            es = eps_star_m(pi, Ef2, mm, delta); grid = np.linspace(0, 0.5, 50001); tender = np.array([tender_now_m(e, pi, Ef2, mm, delta) for e in grid])
            bf = float(grid[tender].max()) if tender.any() else 0.0; ok = ok and abs(bf - es) < 2e-5
            out[f"Ef2={Ef2},m={mm}"] = {"closed_form": round(es, 5), "brute_force_boundary": round(bf, 5)}
    out["valuation_channel_without_rationing"] = round(eps_star_m(pi, 1.0, 0.3, 1.0), 5)   # = m*pi/(1+m) = 0.023077
    out["d_eps_dpi_positive_when_fills_uncertain_or_markdown_possible"] = bool(all(eps_star_m(0.12, Ef2, mm, delta) > eps_star_m(0.10, Ef2, mm, delta) for Ef2 in (1.0, 0.7, 0.4) for mm in (0.0, 0.3, 0.6) if not (Ef2 == 1.0 and mm == 0.0)))
    out["d_eps_dm_positive"] = bool(all(eps_star_m(pi, Ef2, 0.6, delta) > eps_star_m(pi, Ef2, 0.3, delta) for Ef2 in (1.0, 0.7, 0.4)))
    out["reduces_to_baseline_at_m0"] = bool(abs(eps_star_m(pi, 0.7, 0.0, delta) - eps_star(1 - pi, delta, 0.7)) < 1e-12)
    out["PASS"] = bool(ok and out["d_eps_dpi_positive_when_fills_uncertain_or_markdown_possible"] and out["d_eps_dm_positive"] and out["reduces_to_baseline_at_m0"] and abs(out["valuation_channel_without_rationing"] - 0.3 * 0.10 / 1.3) < 1e-4)
    return out

# ---- request-before-price variant (2026-10-18): the request is submitted before the valuation date in BOTH periods (the contract of most funds in the sample).
# Period-1 price is 1 w.p. 1-m1 and v w.p. m1; period-2 price is 1 w.p. 1-m2 and v w.p. m2 (an absorbing markdown that may arrive at either valuation date has m2 >= m1).
# A period-2 request is decided on the expected price: request iff 1 - m2*pi - e - delta*v >= 0.  W2 = e + delta*v + Ef2 * (1 - m2*pi - e - delta*v)_+ .
# Tender now (f1 cancels) iff  1 - m1*pi - e - delta*W2(e) >= 0.  The left side is strictly decreasing in e, so the boundary is unique; on the branch where the
# marginal type would request in period 2:  eps* = [1 - m1*pi - delta^2 v - delta*Ef2*(1 - m2*pi - delta*v)] / (1 + delta - delta*Ef2);  otherwise eps* = (1 - m1*pi - delta^2 v)/(1+delta).
def W2_rbp(e, pi, Ef2, m2, delta=1.0):
    v = 1 - pi; return e + delta * v + Ef2 * max(0.0, 1 - m2 * pi - e - delta * v)
def eps_star_rbp_branch(pi, Ef2, m1, m2, delta=1.0):
    v = 1 - pi; return (1 - m1 * pi - delta**2 * v - delta * Ef2 * (1 - m2 * pi - delta * v)) / (1 + delta - delta * Ef2)
def eps_star_rbp_other(pi, m1, delta=1.0):
    v = 1 - pi; return (1 - m1 * pi - delta**2 * v) / (1 + delta)
def eps_star_rbp(pi, Ef2, m1, m2, delta=1.0):
    v = 1 - pi; e1 = eps_star_rbp_branch(pi, Ef2, m1, m2, delta)
    return e1 if e1 <= 1 - m2 * pi - delta * v + 1e-12 else eps_star_rbp_other(pi, m1, delta)   # the branch condition is that the marginal type would request in period 2
def rbp_check(pi=0.10, delta=0.98):
    import numpy as np
    out = {}; ok = True
    for Ef2 in (1.0, 0.7, 0.4):
        for m1, m2 in ((0.0, 0.0), (0.0, 0.3), (0.1, 0.3), (0.0, 0.8), (0.3, 0.3), (0.3, 0.1)):
            es = eps_star_rbp(pi, Ef2, m1, m2, delta); grid = np.linspace(0, 0.6, 60001)
            tender = np.array([1 - m1 * pi - e - delta * W2_rbp(e, pi, Ef2, m2, delta) >= -1e-12 for e in grid]); bf = float(grid[tender].max()) if tender.any() else 0.0
            ok = ok and abs(bf - max(es, 0.0)) < 2.5e-5; out[f"Ef2={Ef2},m1={m1},m2={m2}"] = {"closed_form": round(es, 5), "brute_force_boundary": round(bf, 5)}
    out["no_rationing_delta1"] = {"eps*(E=1,delta=1,m1=0,m2=0.3)": round(eps_star_rbp(pi, 1.0, 0.0, 0.3, 1.0), 5), "formula pi*(m2-m1)": round(pi * 0.3, 5), "eps*(m1=m2=0.3)": round(eps_star_rbp(pi, 1.0, 0.3, 0.3, 1.0), 5), "eps*(m1=0.3>m2=0.1)": round(eps_star_rbp(pi, 1.0, 0.3, 0.1, 1.0), 5)}
    out["positive_only_if_m2_exceeds_m1_when_fills_certain"] = bool(eps_star_rbp(pi, 1.0, 0.0, 0.3, 1.0) > 0 and abs(eps_star_rbp(pi, 1.0, 0.3, 0.3, 1.0)) < 1e-12 and eps_star_rbp(pi, 1.0, 0.3, 0.1, 1.0) <= 0)
    out["d_eps_dpi_sign_condition"] = "positive iff delta^2 (1-Ef2) + delta*Ef2*m2 > m1 (on the period-2-request branch)"
    out["d_eps_dpi_positive_cases"] = bool(all(eps_star_rbp(0.12, Ef2, m1, m2, delta) > eps_star_rbp(0.10, Ef2, m1, m2, delta) for Ef2, m1, m2 in ((1.0, 0.0, 0.3), (0.7, 0.0, 0.0), (0.7, 0.1, 0.3))))
    out["d_eps_dpi_negative_case_m1_large"] = bool(eps_star_rbp(0.12, 1.0, 0.3, 0.1, 1.0) < eps_star_rbp(0.10, 1.0, 0.3, 0.1, 1.0))
    out["d_eps_dEf2_negative_when_m2pi_small"] = bool(eps_star_rbp(pi, 0.4, 0.0, 0.3, delta) > eps_star_rbp(pi, 0.7, 0.0, 0.3, delta) > eps_star_rbp(pi, 1.0, 0.0, 0.3, delta))
    out["PASS"] = bool(ok and out["positive_only_if_m2_exceeds_m1_when_fills_certain"] and out["d_eps_dpi_positive_cases"] and out["d_eps_dpi_negative_case_m1_large"] and out["d_eps_dEf2_negative_when_m2pi_small"])
    return out

if __name__ == "__main__":
    import json as _json, pathlib as _pl
    hc = headroom_check(); print("headroom kink check:", "PASS" if hc["PASS"] else "FAIL", _json.dumps(hc)[:400])
    try:
        rp = _pl.Path(__file__).resolve().parent.parent / "results" / "model_check.json"; d = _json.load(open(rp)) if rp.exists() else {}; d["headroom_kink"] = hc; _json.dump(d, open(rp, "w"), indent=1)
    except Exception as e: print("could not write model_check.json:", e)
    mk = markdown_check(); print("markdown-risk check:", "PASS" if mk["PASS"] else "FAIL"); d["markdown_risk"] = mk; _json.dump(d, open(rp, "w"), indent=1)
    rb = rbp_check(); print("request-before-price check:", "PASS" if rb["PASS"] else "FAIL"); d["markdown_request_before_price"] = rb; _json.dump(d, open(rp, "w"), indent=1)
    allok = allok and hc["PASS"] and mk["PASS"]
raise SystemExit(0 if allok else 1)
