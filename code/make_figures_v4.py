"""make_figures_v4.py — figures from the v3 results only (offer_master_v3.json, twin_discounts_v3.json).
fig_requests_v3.pdf: gross requests as % of the cap denominator, by fund and cycle quarter (scheduled expiry), rationed offers marked; first public proration (2026-03-24) marked.
fig_twins_v3.pdf: listed twins' price-to-NAV gap at each 10-Q/10-K filing date (percent), five twins and their mean."""
import json
from pathlib import Path
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
BASE = Path(__file__).resolve().parent.parent; R = BASE / "results"; FIG = BASE / "paper" / "figures"; FIG.mkdir(exist_ok=True)
M = json.load(open(R / "offer_master_v3.json"))["offers"]
rows = []
for o in M:
    if o.get("tendered") is None: continue
    rate = 100 * o["tendered"] / o["shares_outstanding_basis"] if o.get("shares_outstanding_basis") else o.get("tendered_pct_basis")
    d = pd.Timestamp(o.get("scheduled_expiry") or o["expiry"]) - pd.Timedelta(days=15)
    rows.append(dict(fund=o["fund"], cycle=d.to_period("Q"), rate=rate, rationed=bool(o.get("rationed")), upsized=bool(o.get("upsized"))))
df = pd.DataFrame(rows); df["t"] = df.cycle.dt.to_timestamp(how="end")
NAMES = {"ADS": "Apollo", "ASIF": "Ares", "BCRED": "Blackstone", "FPCF": "Fidelity", "GCRED": "Golub", "HLEND": "HPS", "OCIC": "Blue Owl Credit Inc.", "OSCF": "Oaktree", "OTIC": "Blue Owl Tech. Inc.", "PCAP": "Nuveen Churchill"}
fig, ax = plt.subplots(figsize=(8.2, 4.4)); cmap = plt.get_cmap("tab10")
for i, (f, g) in enumerate(df.sort_values("t").groupby("fund")):
    ax.plot(g.t, g.rate, "-", color=cmap(i), lw=1.3, alpha=0.9, label=NAMES[f])
    ax.plot(g[~g.rationed].t, g[~g.rationed].rate, "o", color=cmap(i), ms=3.5)
    ax.plot(g[g.rationed].t, g[g.rationed].rate, "s", color=cmap(i), ms=6, mfc="white", mew=1.6)
ax.axhline(5, color="grey", ls="--", lw=0.9); ax.text(pd.Timestamp("2023-11-15"), 5.4, "5% cap", fontsize=8, color="grey")
ax.axvline(pd.Timestamp("2026-03-24"), color="firebrick", ls=":", lw=1.2); ax.text(pd.Timestamp("2026-03-29"), 36, "first public\nproration\n(24 Mar 2026)", fontsize=8, color="firebrick")
ax.set_ylabel("Gross requests (% of shares, offer's own denominator)"); ax.set_xlabel("Cycle (quarter of scheduled expiry)"); ax.set_ylim(0, 44)
ax.legend(frameon=False, fontsize=7.5, ncol=2, loc="upper left"); ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout(); fig.savefig(FIG / "fig_requests_v3.pdf"); fig.savefig(FIG / "fig_requests_v3.png", dpi=180); plt.close(fig)
T = json.load(open(R / "twin_discounts_v3.json"))["twins"]
fig, ax = plt.subplots(figsize=(8.2, 4.0))
allr = []
for i, (t, rs) in enumerate(sorted(T.items())):
    x = [pd.Timestamp(r["filed"]) for r in rs]; y = [r["disc_pct"] for r in rs]; ax.plot(x, y, "o-", color=cmap(i), lw=1.2, ms=3.5, label=t); allr += [(pd.Timestamp(r["filed"]).to_period("Q"), r["disc_pct"]) for r in rs]
q = pd.DataFrame(allr, columns=["q", "d"]).groupby("q").d.mean(); ax.plot(q.index.to_timestamp(how="end"), q.values, "k-", lw=2.4, alpha=0.75, label="mean of five (by filing quarter)")
ax.axhline(0, color="grey", lw=0.8); ax.axvline(pd.Timestamp("2026-03-24"), color="firebrick", ls=":", lw=1.2)
ax.set_ylabel("Price minus NAV per share (% of NAV), at filing date"); ax.set_xlabel("10-Q/10-K filing date"); ax.legend(frameon=False, fontsize=7.5, ncol=3); ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout(); fig.savefig(FIG / "fig_twins_v3.pdf"); fig.savefig(FIG / "fig_twins_v3.png", dpi=180); plt.close(fig)
print("figures written:", sorted(p.name for p in FIG.glob("fig_*_v3.*")))
