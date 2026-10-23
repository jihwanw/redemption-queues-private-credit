"""
Pre-specified H3 test (committed in draft §3.3 on 2026-07-28, BEFORE Q3 data):
    log(tendered_{i,Q3}) = a + b * prorated_{i,Q2} + c * log(tendered_{i,Q2}) + e_i
    Predicted: b > 0.
Run: python3 code/h3_test.py [--partial]
  --partial : run on available observations for CODE VALIDATION ONLY (not reportable).
Output: results/h3_test_results.json (full cycle) / *_PARTIAL.json (validation)
"""
import sys, json
from pathlib import Path
from datetime import datetime
from itertools import combinations
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

BASE = Path(__file__).resolve().parent.parent
RESULTS = BASE / "results"
PARTIAL = "--partial" in sys.argv

Q2 = {
    "BCRED": {"tendered": 133689552, "prorated": 1},
    "HLEND": {"tendered": 45605292, "prorated": 1},
    "ADS":   {"tendered": 66882332, "prorated": 1},
    "GCRED": {"tendered": 15148979, "prorated": 1},
    "FPCF":  {"tendered": 1427358, "prorated": 0},
    "PCAP":  {"tendered": 1752092, "prorated": 0},
}
EXPECTED_Q3 = set(Q2)

log = json.loads((RESULTS / "q3_monitor_log.json").read_text())
q3 = {}
for f in log["new_filings"]:
    fund, t = f["fund"], f.get("tendered")
    if fund in Q2 and t and f["date"] >= "2026-07-26":
        if fund not in q3 or t > q3[fund]["tendered"]:
            q3[fund] = {"tendered": t, "date": f["date"],
                        "oversub": f.get("oversub_ratio")}

have, missing = set(q3), EXPECTED_Q3 - set(q3)
print(f"H3 test — {datetime.now():%Y-%m-%d %H:%M}")
print(f"  received: {sorted(have)} | missing: {sorted(missing)}")

if missing and not PARTIAL:
    print("\nFull cycle incomplete. Per pre-registration the regression runs only on "
          "the complete sample. Use --partial for code validation (not reportable).")
    sys.exit(0)

rows = []
for fund, q2v in Q2.items():
    if fund in q3:
        rows.append({"fund": fund, "prorated_q2": q2v["prorated"],
                     "log_q2": np.log(q2v["tendered"]),
                     "log_q3": np.log(q3[fund]["tendered"]),
                     "growth_pct": round(100 * (q3[fund]["tendered"] / q2v["tendered"] - 1), 1),
                     "q3_oversub": q3[fund]["oversub"]})
df = pd.DataFrame(rows)
print("\n" + df.to_string(index=False))

m = smf.ols("log_q3 ~ prorated_q2 + log_q2", data=df).fit(cov_type="HC1")
b = float(m.params["prorated_q2"])
print(f"\nlog(Q3) ~ prorated_Q2 + log(Q2):")
print(f"  prorated_Q2 = {b:.4f} (HC1 se {m.bse['prorated_q2']:.4f}, "
      f"p = {m.pvalues['prorated_q2']:.4f}), n = {int(m.nobs)}, "
      f"implied ratio {np.exp(b):.2f}x")

# exact one-sided permutation test on growth (log_q3 - log_q2)
y = df["log_q3"].values - df["log_q2"].values
treat = df["prorated_q2"].values.astype(bool)
obs = y[treat].mean() - y[~treat].mean()
n, k = len(y), int(treat.sum())
perms = list(combinations(range(n), k))
p_perm = sum(1 for c in perms
             if (y[list(c)].mean()
                 - y[[i for i in range(n) if i not in c]].mean()) >= obs - 1e-12) / len(perms)
print(f"  permutation (one-sided): diff = {obs:.3f}, p = {p_perm:.4f} "
      f"({len(perms)} permutations)")

out = {
    "meta": {"run_at": datetime.now().isoformat(), "partial": PARTIAL,
             "pre_registered": "draft v3 §3.3, committed 2026-07-28",
             "received": sorted(have), "missing": sorted(missing)},
    "data": json.loads(df.to_json(orient="records")),
    "ols": {"prorated_q2_coef": round(b, 4),
            "se_HC1": round(float(m.bse["prorated_q2"]), 4),
            "p": round(float(m.pvalues["prorated_q2"]), 4),
            "n": int(m.nobs), "implied_ratio": round(float(np.exp(b)), 2)},
    "permutation": {"diff_log_growth": round(float(obs), 4),
                    "p_one_sided": round(p_perm, 4), "n_perms": len(perms)},
}
suffix = "_PARTIAL" if PARTIAL else ""
(RESULTS / f"h3_test_results{suffix}.json").write_text(json.dumps(out, indent=2))
print(f"Saved -> results/h3_test_results{suffix}.json")
