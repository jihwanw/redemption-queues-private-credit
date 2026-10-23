"""event_study_v3.py — listed twins' abnormal returns around the first public proration disclosure of their non-traded sibling.
Events (first disclosure, from the SC TO-I/A record): ARCC/ASIF 2026-03-24; OBDC/OCIC+OTIC 2026-04-27; GBDC/GCRED 2026-05-14; BXSL/BCRED 2026-06-04.
Market model on daily log returns (adjusted closes, Yahoo) against SPY, estimation window 120 trading days ending 10 trading days before the event;
CAR over [0,+1] and [0,+5]; t = CAR / (sd_resid * sqrt(n)). Also the equal-weight mean across the four distinct events. Saves prices used."""
import json, time, urllib.request
import numpy as np, pandas as pd
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent; R = BASE / "results"
EVENTS = [("ARCC", "ASIF", "2026-03-24"), ("OBDC", "OCIC/OTIC", "2026-04-27"), ("GBDC", "GCRED", "2026-05-14"), ("BXSL", "BCRED", "2026-06-04")]
def yahoo(t):
    for a in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=2y&interval=1d", headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r: d = json.loads(r.read())["chart"]["result"][0]
            adj = d["indicators"].get("adjclose", [{}])[0].get("adjclose") or d["indicators"]["quote"][0]["close"]
            s = pd.Series(adj, index=pd.to_datetime(d["timestamp"], unit="s").normalize()); time.sleep(0.5); return s[~s.index.duplicated(keep="last")].dropna()
        except Exception as e: time.sleep(2); err = e
    raise err
px = {t: yahoo(t) for t in ["SPY"] + [e[0] for e in EVENTS]}
rets = pd.DataFrame({t: np.log(s).diff() for t, s in px.items()}).dropna()
out = {"meta": {"method": "market model vs SPY, 120-day estimation window ending 10 trading days before the event; log returns from adjusted closes", "built": time.strftime("%Y-%m-%d")}, "events": []}
for twin, sib, ev in EVENTS:
    ev = pd.Timestamp(ev); idx = rets.index; pos = idx.searchsorted(ev)
    if pos >= len(idx) or idx[pos] != ev: ev_day = idx[pos]
    else: ev_day = ev
    pos = idx.get_loc(ev_day); est = rets.iloc[pos - 130: pos - 10]
    X = np.column_stack([np.ones(len(est)), est["SPY"].values]); y = est[twin].values; b = np.linalg.lstsq(X, y, rcond=None)[0]; resid = y - X @ b; sd = resid.std(ddof=2)
    rec = {"twin": twin, "sibling": sib, "event_date": str(ev_day.date()), "alpha": round(float(b[0]), 6), "beta": round(float(b[1]), 4), "sd_resid": round(float(sd), 5), "n_est": int(len(est))}
    for lo, hi in ((0, 1), (0, 5)):
        w = rets.iloc[pos + lo: pos + hi + 1]; ar = w[twin].values - (b[0] + b[1] * w["SPY"].values); car = float(ar.sum()); rec[f"car_{lo}_{hi}"] = {"car_pct": round(100 * car, 3), "t": round(car / (sd * np.sqrt(len(ar))), 2), "n": int(len(ar))}
    out["events"].append(rec); print(rec)
cars = [e["car_0_1"]["car_pct"] for e in out["events"]]; ses = [e["car_0_1"]["car_pct"] / e["car_0_1"]["t"] for e in out["events"]]
out["mean_car_0_1"] = {"mean_pct": round(float(np.mean(cars)), 3), "t": round(float(np.mean(cars) / (np.sqrt(sum(s * s for s in ses)) / len(ses))), 2), "n_events": len(cars)}
print("mean [0,+1]:", out["mean_car_0_1"]); json.dump(out, open(R / "event_study_v3.json", "w"), indent=1); rets.to_csv(R / "event_study_v3_returns.csv"); print("saved")
