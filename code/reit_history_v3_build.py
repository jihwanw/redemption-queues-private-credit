"""reit_history_v3_build.py — build results/reit_history_v3.json (BREIT monthly redemption record used by the REIT comparison table).

Input:  results/reit_history_v2.json  (built by reit_historical_v2.py from BREIT's 424B3/10-Q/10-K "For the months ended" disclosures:
        fulfilled repurchases as % of NAV and as % of requests, month by month, with the evidence sentence and filing for each month).
Output: results/reit_history_v3.json — the same months with (i) the exact quotient requests %NAV = fulfilled %NAV / (fulfilled % of requests / 100),
        (ii) an interval from the disclosed rounding (fulfilled %NAV to 0.1 pp, fulfilled % of requests to 1 pp: half-unit bounds on both inputs;
        a month filled at 100% has no request-share rounding), and (iii) the evidence sentence and filing. October 2022 is disclosed in a
        different form ("In October 2022, we fulfilled repurchase requests ... representing all repurchase requests received in that month")
        in the 424B3 of 15 December 2022 (accession 0001662972-22-000143); that sentence is fetched from EDGAR and checked, not typed.

Written 2026-10-24: the file had been produced on 2026-10-16 by a one-off script that was not kept; this script reproduces its monthly block
exactly (verified against the archived file) and is the producer deposited with the replication package.
"""
import json, re, html, urllib.request, time
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
V2 = BASE / "results" / "reit_history_v2.json"
OUT = BASE / "results" / "reit_history_v3.json"
UA = {"User-Agent": "Jihwan Woo jihwan.woo@gmail.com (academic research)"}
OCT22 = {"accession": "0001662972-22-000143", "cik": "1662972", "document": "breitnavnovember2022.htm",
         "label": "424B3 2022-12-15 (accession 0001662972-22-000143)",
         "pattern": r"In October 2022, we fulfilled repurchase requests pursuant to our share repurchase plan of [0-9.]+% of NAV[^.]*?(?:\$[0-9.]+ billion)?, representing all repurchase requests received in that month\."}

def fetch_oct22_sentence():
    url = f"https://www.sec.gov/Archives/edgar/data/{OCT22['cik']}/{OCT22['accession'].replace('-', '')}/{OCT22['document']}"
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r: raw = r.read().decode(errors="replace")
            break
        except Exception:
            if i == 2: raise
            time.sleep(2 * (i + 1))
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))
    m = re.search(OCT22["pattern"], text)
    if not m: raise SystemExit("October 2022 sentence not found in " + url)
    return m.group(0)

def interval(f, p):
    lo_f, hi_f = f - 0.05, f + 0.05                      # fulfilled %NAV disclosed to 0.1 pp
    if p >= 100: return [lo_f, hi_f]                     # all requests filled: requests = fulfilled
    return [lo_f / ((p + 0.5) / 100), hi_f / ((p - 0.5) / 100)]   # % of requests disclosed to 1 pp

v2 = json.loads(V2.read_text())
evidence = {e["month"]: e for e in v2["evidence"]}
monthly = {}
for month, r in v2["monthly"].items():
    f, p = float(r["fulfilled_nav_pct"]), float(r["fulfill_of_requests_pct"])
    if month in evidence: ev, filing = evidence[month]["text"], evidence[month]["filing"]
    elif month == "2022-10": ev, filing = fetch_oct22_sentence(), OCT22["label"]
    else: raise SystemExit(f"no evidence sentence for {month}")
    monthly[month] = {"fulfilled_nav_pct": f, "fulfill_of_requests_pct": p, "requests_nav_pct": f / (p / 100),
                      "requests_nav_pct_interval": interval(f, p), "evidence": ev, "filing": filing}
out = {"meta": {"built": str(date.today()), "rebuilt_from": f"reit_history_v2.json (run_at {v2['meta'].get('run_at')})",
                "source": "BREIT 424B3/10-Q/10-K 'For the months ended' disclosures (v2 evidence sentences) + 2022-12-15 424B3 for October 2022",
                "method": "requests %NAV = fulfilled %NAV ÷ (fulfilled % of requests / 100). Inputs are disclosed rounded (fulfilled %NAV to 0.1 pp; fulfilled % of requests to 1 pp); the interval uses the half-unit bounds of both inputs."},
       "monthly": monthly}
OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
print(f"wrote {OUT.name}: {len(monthly)} months")
