"""
Q3-2026 tender filing monitor for the H3 test (pre-specified in draft v3, §3.3).
Checks EDGAR for new SC TO-I/A filings after 2026-07-25 from the 10 sample funds.
When found, parses with the v2 parser logic and appends to results/q3_monitor_log.json.
Run daily: python3 code/monitor_q3_filings.py
"""
import json, re, time, urllib.request
from pathlib import Path
from datetime import datetime
from html import unescape

BASE = Path(__file__).resolve().parent.parent
RESULTS = BASE / "results"
LOG = RESULTS / "q3_monitor_log.json"
UA = {"User-Agent": "Jihwan Woo jihwan.woo@kakao.com (academic research)"}

FUNDS = {"BCRED": "0001803498", "OCIC": "0001812554", "ADS": "0001837532",
         "HLEND": "0001838126", "ASIF": "0001918712", "OSCF": "0001872371",
         "FPCF": "0001920453", "GCRED": "0001930087", "PCAP": "0001911066",
         "OTIC": "0001869453"}
CUTOFF = "2026-07-25"   # filings after the current panel snapshot

# expected next results-filing dates (from historical cadence, for reference)
EXPECTED = {"FPCF": "~2026-07-29", "BCRED": "~2026-08-03", "HLEND": "~2026-08-03",
            "ADS": "~2026-08-06", "PCAP": "~2026-08-06", "GCRED": "~2026-08-12",
            "OSCF": "~2026-08-15", "ASIF": "~2026-09-26",
            "OCIC": "~2026-10-24", "OTIC": "~2026-10-24"}

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

SHARE_NUM = re.compile(
    r"(?<![$\d.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?)\s+(?:Class\s+[A-Z]+[-\s]*)?(?:common\s+)?[Ss]hares")

def parse_filing(cik, accession):
    acc = accession.replace("-", "")
    idx = get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/index.json")
    best = {"tendered": None, "accepted": None, "prorated_lang": False,
            "pct_requested": None, "pct_fulfilled": None, "evidence": []}
    for item in idx["directory"]["item"]:
        n = item["name"]
        if not n.lower().endswith((".htm", ".html")) or "index" in n.lower() \
           or "filingfees" in n.lower():
            continue
        try:
            text = strip_html(get(
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{n}",
                as_json=False))
        except Exception:
            continue
        if re.search(r"pro\s*rata\s+basis|prorat", text, re.I):
            best["prorated_lang"] = True
        for s in re.split(r"(?<=\.)\s+", text):
            low = s.lower()
            nums = [float(m.group(1).replace(",", "")) for m in SHARE_NUM.finditer(s)]
            if re.search(r"(?:validly|properly)\s+tendered|were\s+tendered", low) and nums:
                tot = sum(nums)
                if best["tendered"] is None or tot > best["tendered"]:
                    best["tendered"] = tot
                    best["evidence"].append(("tendered", s[:300]))
            if re.search(r"accepted\s+for\s+(?:purchase|repurchase)|(?:has\s+)?(?:purchased|repurchased)\b", low) and nums:
                tot = sum(nums)
                if best["accepted"] is None or tot > best["accepted"]:
                    best["accepted"] = tot
                    best["evidence"].append(("accepted", s[:300]))
            m = re.search(r"repurchase\s+requests?[^.]{0,120}?([\d.]+)\s*%\s+of\s+shares", s, re.I)
            if m:
                best["pct_requested"] = float(m.group(1))
                best["evidence"].append(("pct_requested", s[:300]))
        time.sleep(0.15)
    return best

log = json.loads(LOG.read_text()) if LOG.exists() else {"checks": [], "new_filings": []}
known = {(f["fund"], f["accession"]) for f in log["new_filings"]}

print(f"Q3 monitor — {datetime.now():%Y-%m-%d %H:%M} (cutoff {CUTOFF})")
found_any = False
for tick, cik in FUNDS.items():
    try:
        d = get(f"https://data.sec.gov/submissions/CIK{cik}.json")
    except Exception as e:
        print(f"  {tick}: submissions ERR {str(e)[:80]}")
        continue
    rec = d["filings"]["recent"]
    for form, acc, dt in zip(rec["form"], rec["accessionNumber"], rec["filingDate"]):
        if form == "SC TO-I/A" and dt > CUTOFF and (tick, acc) not in known:
            found_any = True
            print(f"  ★ NEW: {tick} SC TO-I/A filed {dt} — parsing...")
            r = parse_filing(cik, acc)
            ratio = (round(r["tendered"] / r["accepted"], 3)
                     if r["tendered"] and r["accepted"] else None)
            entry = {"fund": tick, "date": dt, "accession": acc,
                     "tendered": r["tendered"], "accepted": r["accepted"],
                     "oversub_ratio": ratio, "prorated_lang": r["prorated_lang"],
                     "pct_requested": r["pct_requested"],
                     "evidence": r["evidence"][:4],
                     "parsed_at": datetime.now().isoformat()}
            log["new_filings"].append(entry)
            print(f"     tendered={r['tendered']}, accepted={r['accepted']}, "
                  f"ratio={ratio}, prorate_lang={r['prorated_lang']}")
    time.sleep(0.2)

if not found_any:
    print("  no new filings yet. Expected next:", EXPECTED)

log["checks"].append({"at": datetime.now().isoformat(), "found_new": found_any})
LOG.write_text(json.dumps(log, indent=2))
print(f"Log -> {LOG}")
