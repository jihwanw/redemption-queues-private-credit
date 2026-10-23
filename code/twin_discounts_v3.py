"""twin_discounts_v3.py — listed twins' discount to NAV: price (Yahoo unadjusted close, first trading day on/after the 10-Q/10-K filing date) over the
NetAssetValuePerShare reported in that filing (XBRL companyfacts, us-gaap:NetAssetValuePerShare, instant at period end), minus one, in percent.
Replaces the StockholdersEquity ÷ cover-page shares approximation (which produced an OBDC 2025Q1 outlier). Output: results/twin_discounts_v3.json."""
import json, time, urllib.request
import pandas as pd
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent; R = BASE / "results"
UA = {"User-Agent": "Jihwan Woo jihwan.woo@gmail.com (academic research)"}
LISTED = {"ARCC": "0001287750", "OBDC": "0001655888", "BXSL": "0001736035", "GBDC": "0001476765", "OCSL": "0001414932"}
def get(u, hdr=UA):
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=hdr), timeout=60) as r: b = r.read(); time.sleep(0.3); return json.loads(b)
        except Exception as e: time.sleep(3 * (a + 1)); err = e
    raise err
def yahoo_close(t):
    d = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=5y&interval=1d", {"User-Agent": "Mozilla/5.0"})["chart"]["result"][0]
    s = pd.Series(d["indicators"]["quote"][0]["close"], index=pd.to_datetime(d["timestamp"], unit="s").normalize()); return s[~s.index.duplicated(keep="last")].dropna()
out = {"meta": {"built": time.strftime("%Y-%m-%d"), "doc": __doc__}, "twins": {}}
for t, cik in LISTED.items():
    d = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"); node = d["facts"]["us-gaap"].get("NetAssetValuePerShare")
    if not node: print(t, "no NAVPS"); continue
    recs = [r for lst in node["units"].values() for r in lst if r.get("form") in ("10-Q", "10-K", "10-Q/A", "10-K/A") and r.get("filed")]
    df = pd.DataFrame(recs).sort_values(["end", "filed"]).drop_duplicates("end", keep="first"); px = yahoo_close(t); rows = []
    for _, r in df.iterrows():
        filed = pd.Timestamp(r["filed"]); w = px[(px.index >= filed) & (px.index <= filed + pd.Timedelta(days=5))]
        if not len(w) or r["end"] < "2023-01-01": continue
        rows.append({"end": r["end"], "filed": r["filed"], "accn": r.get("accn"), "navps": float(r["val"]), "price_at_filed": round(float(w.iloc[0]), 2), "price_date": str(w.index[0].date()), "disc_pct": round(100 * (float(w.iloc[0]) / float(r["val"]) - 1), 4)})
    out["twins"][t] = rows; print(t, len(rows), "obs; latest", rows[-1] if rows else None)
# availability-quarter pivot
rows = [{"twin": t, "q": pd.Timestamp(r["filed"]).to_period("Q").__str__(), "disc": r["disc_pct"]} for t, rs in out["twins"].items() for r in rs]
pv = pd.DataFrame(rows).pivot_table(index="q", columns="twin", values="disc", aggfunc="last"); out["per_twin_disc_by_avail_q"] = json.loads(pv.round(4).to_json()); out["avg_disc_by_avail_q"] = pv.mean(axis=1).round(4).to_dict()   # 4 dp: the table generator applies the only display rounding
print(pv.round(1).to_string()); json.dump(out, open(R / "twin_discounts_v3.json", "w"), indent=1); print("saved")
