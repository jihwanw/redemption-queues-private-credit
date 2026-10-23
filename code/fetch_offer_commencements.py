"""fetch_offer_commencements.py — cache every SC TO-I (initial tender-offer statement) and its primary document for the ten funds, 2023-09 onward,
into results/filings_cache/<FUND>_<date>_<accession>_SCTOI/. Also records all SC TO-I/A dates for offer lineage. Output: results/offer_filings_index.json."""
import json, re, time, urllib.request
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent; OUT = BASE / "results" / "filings_cache"
UA = {"User-Agent": "Jihwan Woo jihwan.woo@gmail.com (academic research)"}
src = (BASE / "code" / "m2_main_v2.py").read_text(); FUNDS = {m.group(1): m.group(2) for m in re.finditer(r'"([A-Z]+)":\s*"(\d{10})"', src)}
def get(url, binary=False):
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r: data = r.read(); time.sleep(0.15); return data if binary else data.decode("utf-8", "ignore")
        except Exception as e: time.sleep(3 * (a + 1)); err = e
    raise err
index = {}
for fund, cik in FUNDS.items():
    sub = json.loads(get(f"https://data.sec.gov/submissions/CIK{cik}.json")); rec = sub["filings"]["recent"]
    rows = [dict(form=f, date=d, accession=a, doc=p) for f, d, a, p in zip(rec["form"], rec["filingDate"], rec["accessionNumber"], rec["primaryDocument"]) if f in ("SC TO-I", "SC TO-I/A") and d >= "2023-09-01"]
    # older pages
    for extra in sub["filings"].get("files", []):
        more = json.loads(get("https://data.sec.gov/submissions/" + extra["name"]))
        rows += [dict(form=f, date=d, accession=a, doc=p) for f, d, a, p in zip(more["form"], more["filingDate"], more["accessionNumber"], more["primaryDocument"]) if f in ("SC TO-I", "SC TO-I/A") and d >= "2023-09-01"]
    rows.sort(key=lambda r: r["date"]); index[fund] = rows
    n_new = 0
    for r in rows:
        if r["form"] != "SC TO-I": continue
        d = OUT / f"{fund}_{r['date']}_{r['accession']}_SCTOI"; d.mkdir(exist_ok=True)
        if list(d.glob("*.html")): continue
        accn = r["accession"].replace("-", ""); idx = get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}/index.json"); (d / "index.json").write_text(idx)
        for it in json.loads(idx)["directory"]["item"]:
            nm = it["name"]
            if nm.endswith(".htm") and "index" not in nm.lower() and not re.match(r"R\d+\.htm$", nm): (d / (nm + "l")).write_bytes(get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}/{nm}", binary=True))
        n_new += 1
    print(f"{fund}: {sum(1 for r in rows if r['form']=='SC TO-I')} SC TO-I, {sum(1 for r in rows if r['form']=='SC TO-I/A')} SC TO-I/A; cached {n_new} new", flush=True)
json.dump(index, open(BASE / "results" / "offer_filings_index.json", "w"), indent=1); print("index written")
