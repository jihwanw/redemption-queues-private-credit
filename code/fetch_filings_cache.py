"""fetch_filings_cache.py — download every filing document referenced in results/m2_tender_panel_v2.json into results/filings_cache/<FUND>_<date>_<accession>/ (index.json + each non-index document as .html/.txt). Idempotent; EDGAR rate limit respected (<=8 req/s)."""
import json, time, urllib.request, re
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent; OUT = BASE / "results" / "filings_cache"; OUT.mkdir(exist_ok=True)
UA = {"User-Agent": "Jihwan Woo jihwan.woo@gmail.com (academic research)"}
FUNDS = {"BCRED": "0001803498", "OCIC": "0001812554", "ADS": "0001837532"}
# read CIKs from the main script to avoid retyping
src = (BASE / "code" / "m2_main_v2.py").read_text()
for m in re.finditer(r'"([A-Z]+)":\s*"(\d{10})"', src): FUNDS[m.group(1)] = m.group(2)
panel = json.load(open(BASE / "results" / "m2_tender_panel_v2.json"))
rows = panel if isinstance(panel, list) else (panel.get("rows") or panel.get("panel") or list(panel.values())[0])
def get(url, binary=False):
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r: data = r.read(); time.sleep(0.15); return data if binary else data.decode("utf-8", "ignore")
        except Exception as e:
            time.sleep(3 * (a + 1)); err = e
    raise err
log = []
for r in rows:
    fund, date, acc = r["fund"], r["date"], r["accession"]; cik = FUNDS[fund]; accn = acc.replace("-", "")
    d = OUT / f"{fund}_{date}_{acc}"; d.mkdir(exist_ok=True)
    if (d / "index.json").exists() and len(list(d.glob("*.html")) + list(d.glob("*.txt"))) > 0: continue
    try:
        idx = get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}/index.json"); (d / "index.json").write_text(idx)
        items = json.loads(idx)["directory"]["item"]
        for it in items:
            n = it["name"]
            if n.endswith((".htm", ".html", ".txt")) and not n.endswith("-index.htm") and "index" not in n.lower() and not re.search(r"\.txt$", n) or n.endswith(".htm"):
                if n.endswith(".txt"): continue   # full submission text duplicates the documents
                (d / (n if n.endswith(".html") else n + "l" if n.endswith(".htm") else n)).write_bytes(get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}/{n}", binary=True))
        log.append((fund, date, acc, "ok", len(list(d.glob("*.html")))))
    except Exception as e:
        log.append((fund, date, acc, f"ERROR {e}", 0))
    print(log[-1], flush=True)
json.dump(log, open(OUT / "_fetch_log.json", "w"), indent=1); print("done", sum(1 for l in log if l[3] == "ok"), "ok of", len(log))
