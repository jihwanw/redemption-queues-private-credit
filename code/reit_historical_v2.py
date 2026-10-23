"""
REIT historical step 2 — parse BREIT's quarterly 'For the months ended ...,
fulfilled a%, b%, c% of NAV, or p%, q%, r% of repurchase requests' format.
Requests as % of NAV are backed out: req_pct = nav_pct / (req_fulfill_pct/100).
Adds 10-Q/10-K to the form set and widens the window to capture all quarters.
Then: H3 historical test — does gating predict next-month request growth in the
escalation phase, and how does the run end?
Output: results/reit_history_v2.json
"""
import json, re, time, urllib.request
from pathlib import Path
from datetime import datetime
from html import unescape
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

BASE = Path(__file__).resolve().parent.parent
RESULTS = BASE / "results"
UA = {"User-Agent": "Jihwan Woo jihwan.woo@kakao.com (academic research)"}
CIK = "0001662972"  # BREIT
WINDOW = ("2022-11-01", "2024-09-30")

def get(url, as_json=True, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            return json.loads(data) if as_json else data.decode(errors="replace")
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(1.5 * (i + 1))

def strip_html(h):
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", unescape(t))

MONTHS = {"January": 1, "February": 2, "March": 3, "April": 4, "May": 5,
          "June": 6, "July": 7, "August": 8, "September": 9, "October": 10,
          "November": 11, "December": 12}
BLOCK_RE = re.compile(
    r"For the months? ended\s+(.{10,140}?),?\s+in accordance with the "
    r"(?:share repurchase plan|Repurchase Plan)[^.]*?fulfilled repurchases? "
    r"equal to\s+([\d.%,\s and]+?)\s+of NAV[^.]*?or\s+([\d.%,\s and]+?)\s+of "
    r"repurchase requests", re.I)
MD_RE = re.compile(r"(" + "|".join(MONTHS) + r")\s+\d{1,2},?\s+(\d{4})")
PCTS_RE = re.compile(r"([\d.]+)\s*%")

d = get(f"https://data.sec.gov/submissions/CIK{CIK}.json")
rows = []
rec = d["filings"]["recent"]
rows += list(zip(rec["form"], rec["accessionNumber"], rec["filingDate"],
                 rec["primaryDocument"]))
for f in d["filings"].get("files", []):
    d2 = get(f"https://data.sec.gov/submissions/{f['name']}")
    rows += list(zip(d2["form"], d2["accessionNumber"], d2["filingDate"],
                     d2["primaryDocument"]))
    time.sleep(0.15)
cand = [(f, a, dt, doc) for f, a, dt, doc in rows
        if f in ("424B3", "10-Q", "10-K", "8-K")
        and "2022-12-01" <= dt <= "2025-06-30"]
print(f"BREIT candidate filings: {len(cand)}")

monthly = {}   # 'YYYY-MM' -> dict
evidence = []
for f, a, dt, doc in sorted(cand, key=lambda x: x[2]):
    acc = a.replace("-", "")
    try:
        txt = strip_html(get(
            f"https://www.sec.gov/Archives/edgar/data/{int(CIK)}/{acc}/{doc}",
            as_json=False))
    except Exception:
        continue
    for m in BLOCK_RE.finditer(txt):
        months_str, nav_str, req_str = m.group(1), m.group(2), m.group(3)
        mds = MD_RE.findall(months_str)
        navs = [float(x) for x in PCTS_RE.findall(nav_str + "%")
                ] or [float(x) for x in re.findall(r"([\d.]+)", nav_str)]
        reqs = [float(x) for x in PCTS_RE.findall(req_str + "%")
                ] or [float(x) for x in re.findall(r"([\d.]+)", req_str)]
        if not mds or len(navs) != len(mds) or len(reqs) != len(mds):
            continue
        for (mon, yr), nav_p, req_p in zip(mds, navs, reqs):
            key = f"{yr}-{MONTHS[mon]:02d}"
            if key not in monthly:
                monthly[key] = {"fulfilled_nav_pct": nav_p,
                                "fulfill_of_requests_pct": req_p,
                                "requests_nav_pct": round(nav_p / (req_p / 100), 2)
                                if req_p > 0 else None,
                                "src": f"{f} {dt}"}
                evidence.append({"month": key, "filing": f"{f} {dt}",
                                 "text": m.group(0)[:400]})
    time.sleep(0.12)

# add known boundary months from step-1 sentences
monthly.setdefault("2022-10", {"fulfilled_nav_pct": 2.7,
                               "fulfill_of_requests_pct": 100.0,
                               "requests_nav_pct": 2.7,
                               "src": "424B3 2022-12-15 (step-1)"})
monthly.setdefault("2022-11", {"fulfilled_nav_pct": 2.0,
                               "fulfill_of_requests_pct": 43.0,
                               "requests_nav_pct": 4.65,
                               "src": "424B3 2023-03-17 (step-1)"})

ser = (pd.DataFrame(monthly).T.sort_index()
       .dropna(subset=["requests_nav_pct"]))
print("\nBREIT monthly requests (% of NAV, backed out) and fulfillment:")
print(ser[["requests_nav_pct", "fulfill_of_requests_pct"]].to_string())

# ---- H3 historical dynamics ----
s = ser["requests_nav_pct"].astype(float)
g = ser["fulfill_of_requests_pct"].astype(float)
df = pd.DataFrame({"req": s, "ful": g})
df["gated"] = (df["ful"] < 99).astype(int)
df["dlog_req_next"] = np.log(df["req"]).diff().shift(-1)
sub = df.dropna()
res = {}
if len(sub) >= 8:
    m1 = smf.ols("dlog_req_next ~ gated", data=sub).fit(cov_type="HC1")
    m2 = smf.ols("dlog_req_next ~ ful", data=sub).fit(cov_type="HC1")
    res = {"n_months": int(len(sub)),
           "gated_coef": [round(float(m1.params["gated"]), 4),
                          round(float(m1.pvalues["gated"]), 4)],
           "fill_rate_coef": [round(float(m2.params["ful"]), 5),
                              round(float(m2.pvalues["ful"]), 4)]}
    print(f"\nH3 dynamics: Δlog req(t+1) ~ gated(t): {res['gated_coef']} | "
          f"~ fill_rate(t): {res['fill_rate_coef']}")

# escalation summary
esc = {
    "first_gate": "2022-11 (43% fulfilled)",
    "requests_path_pct_nav": {k: float(v) for k, v in s.items()},
    "peak": {"month": s.idxmax(), "requests_nav_pct": float(s.max())},
    "escalation_from_first_gate_to_peak_pct":
        round(100 * (s.max() / s.get("2022-11", np.nan) - 1), 1),
}
print(f"\nEscalation: first gate 2022-11 (4.65% of NAV requested) -> "
      f"peak {esc['peak']['month']} ({esc['peak']['requests_nav_pct']}%), "
      f"+{esc['escalation_from_first_gate_to_peak_pct']}%")

out = {"meta": {"run_at": datetime.now().isoformat(),
                "source": "BREIT EDGAR 424B3/10-Q/10-K, 'For the months ended' blocks",
                "requests_backed_out": "req%NAV = fulfilled%NAV / (fulfilled%ofRequests/100)"},
       "monthly": json.loads(ser.to_json(orient="index")),
       "h3_dynamics": res, "escalation": esc, "evidence": evidence}
(RESULTS / "reit_history_v2.json").write_text(json.dumps(out, indent=2, default=str))
print(f"\nSaved -> {RESULTS/'reit_history_v2.json'}")
