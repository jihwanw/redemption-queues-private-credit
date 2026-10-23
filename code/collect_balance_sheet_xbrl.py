"""collect_balance_sheet_xbrl.py — fund-quarter balance-sheet and cash-flow panel from SEC XBRL companyfacts (10-Q/10-K), 2024Q1–2026Q2.
Flows (cash-flow statement, reported year-to-date in 10-Q): PaymentsForRepurchaseOfCommonStock, ProceedsFromIssuanceOfCommonStock, PaymentsToAcquireInvestments
(alternates: PaymentsForPurchaseOfInvestments...), ProceedsFromSaleMaturityAndCollectionsOfInvestments (alternates), ProceedsFromIssuanceOfDebt, RepaymentsOfDebt,
InvestmentCompanyDividendDistribution. Quarterly flow = YTD(end) − YTD(previous quarter end of the same fiscal year); Q1 = YTD.
Stocks (point in time): CashAndCashEquivalentsAtCarryingValue, debt (DebtLongtermAndShorttermCombinedAmount | LongTermDebt | DebtInstrumentCarryingAmount),
LineOfCreditFacilityRemainingBorrowingCapacity (+ DebtInstrumentUnusedBorrowingCapacityAmount), StockholdersEquity (net assets), NetAssetValuePerShare,
StockRepurchasedDuringPeriodShares | StockRepurchasedAndRetiredDuringPeriodShares (period). Every value keeps concept, form, filed, accession."""
import json, re, time, urllib.request
from pathlib import Path
import pandas as pd
BASE = Path(__file__).resolve().parent.parent; R = BASE / "results"
UA = {"User-Agent": "Jihwan Woo jihwan.woo@gmail.com (academic research)"}
def get(u):
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r: b = r.read(); time.sleep(0.25); return json.loads(b)
        except Exception as e: time.sleep(3 * (a + 1)); err = e
    raise err
src = (BASE / "code" / "m2_main_v2.py").read_text(); FUNDS = {m.group(1): m.group(2) for m in re.finditer(r'"([A-Z]+)":\s*"(\d{10})"', src)}
FLOWS = {"repurchases_paid": ["PaymentsForRepurchaseOfCommonStock"], "repurchases_value": ["StockRepurchasedDuringPeriodValue", "StockRepurchasedAndRetiredDuringPeriodValue"], "issuance_proceeds": ["ProceedsFromIssuanceOfCommonStock", "ProceedsFromIssuanceOrSaleOfEquity"],
         "investment_purchases": ["PaymentsForPurchaseOfInvestmentOperatingActivity", "PaymentsToAcquireInvestments", "PaymentsForPurchaseOfInvestments"],
         "investment_proceeds": ["ProceedsFromDispositionOfInvestmentOperatingActivity", "ProceedsFromSaleMaturityAndCollectionsOfInvestments", "ProceedsFromSaleAndMaturityOfOtherInvestments"],
         "debt_issued": ["ProceedsFromIssuanceOfDebt", "ProceedsFromIssuanceOfLongTermDebt", "ProceedsFromLinesOfCredit"], "debt_repaid": ["RepaymentsOfDebt", "RepaymentsOfLongTermDebt", "RepaymentsOfLinesOfCredit"],
         "distributions": ["InvestmentCompanyDividendDistribution", "PaymentsOfDividends"], "shares_repurchased": ["StockRepurchasedDuringPeriodShares", "StockRepurchasedAndRetiredDuringPeriodShares"]}
STOCKS = {"cash": ["CashAndCashEquivalentsAtCarryingValue", "Cash", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"], "debt": ["DebtLongtermAndShorttermCombinedAmount", "LongTermDebt", "DebtInstrumentCarryingAmount", "LongTermDebtNoncurrent"],
          "undrawn_capacity": ["LineOfCreditFacilityRemainingBorrowingCapacity", "DebtInstrumentUnusedBorrowingCapacityAmount"], "net_assets": ["StockholdersEquity", "NetAssets"], "nav_per_share": ["NetAssetValuePerShare"], "shares_outstanding": ["CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding"]}
def facts(d, names, unitpref=None):
    for n in names:
        for taxo in ("us-gaap", "dei", "cef", "ffd"):
            node = d["facts"].get(taxo, {}).get(n)
            if node:
                rows = []
                for unit, lst in node["units"].items():
                    for r in lst:
                        if r.get("form") in ("10-Q", "10-K", "10-K/A", "10-Q/A"): rows.append(dict(concept=f"{taxo}:{n}", unit=unit, start=r.get("start"), end=r["end"], val=float(r["val"]), form=r["form"], filed=r.get("filed"), accn=r.get("accn"), fy=r.get("fy"), fp=r.get("fp")))
                if rows: return pd.DataFrame(rows)
    return None
def quarterly_flows(df):
    """YTD durations -> quarterly values. Keep, for each end date, the duration that starts at the fiscal-year start (longest span <= 12m); then difference within fiscal year."""
    df = df.dropna(subset=["start"]).copy(); df["start"] = pd.to_datetime(df.start); df["end"] = pd.to_datetime(df.end); df["days"] = (df.end - df.start).dt.days
    df = df[(df.days > 60) & (df.days < 380)].sort_values(["end", "filed"]).drop_duplicates(["start", "end"], keep="last")
    out = []
    for end, g in df.groupby("end"):
        g = g.sort_values("days"); q = g.iloc[0]   # shortest duration ending here (a quarter if reported, else YTD)
        if q.days <= 100: out.append(dict(end=end, val=q.val, basis="quarterly", concept=q.concept, form=q.form, filed=q.filed, accn=q.accn)); continue
        ytd = g.iloc[-1]; prev_end = end - pd.offsets.QuarterEnd(1)
        prev = df[(df.end == prev_end) & (df.start == ytd.start)]
        if len(prev): out.append(dict(end=end, val=ytd.val - prev.iloc[0].val, basis="ytd_difference", concept=ytd.concept, form=ytd.form, filed=ytd.filed, accn=ytd.accn))
        elif ytd.days <= 100 or (ytd.start.month == end.month % 12 + 1 and ytd.days < 100): out.append(dict(end=end, val=ytd.val, basis="quarterly", concept=ytd.concept, form=ytd.form, filed=ytd.filed, accn=ytd.accn))
        else: out.append(dict(end=end, val=None, basis=f"ytd_only_{ytd.days}d", concept=ytd.concept, form=ytd.form, filed=ytd.filed, accn=ytd.accn))
    return pd.DataFrame(out)
panel = {}
for fund, cik in FUNDS.items():
    d = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"); rec = {}
    for k, names in FLOWS.items():
        f = facts(d, names)
        if f is None: continue
        qf = quarterly_flows(f)
        for _, r in qf.iterrows():
            if r.end >= pd.Timestamp("2023-12-31"): rec.setdefault(str(r.end.date()), {})[k] = {"val": r.val, "basis": r.basis, "concept": r.concept, "form": r.form, "filed": r.filed, "accn": r.accn}
    for k, names in STOCKS.items():
        f = facts(d, names)
        if f is None: continue
        f = f[f.start.isna()] if f.start.notna().any() and f.start.isna().any() else f
        f = f.sort_values(["end", "filed"]).drop_duplicates("end", keep="first")   # first report of each period end (no restatement look-ahead)
        for _, r in f.iterrows():
            if r.end >= "2023-12-31": rec.setdefault(r.end, {})[k] = {"val": r.val, "concept": r.concept, "form": r.form, "filed": r.filed, "accn": r.accn}
    panel[fund] = dict(sorted(rec.items())); have = {k for v in rec.values() for k in v}
    print(f"{fund}: quarters {len(rec)}; fields {sorted(have)}", flush=True)
json.dump({"meta": {"source": "SEC XBRL companyfacts (10-Q/10-K), fetched " + time.strftime("%Y-%m-%d"), "doc": __doc__}, "panel": panel}, open(R / "balance_sheet_v3.json", "w"), indent=1)
print("saved results/balance_sheet_v3.json")
