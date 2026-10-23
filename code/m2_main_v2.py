"""
M2 Main v2 — expanded sample (10 non-traded BDCs) + share-class-aware parsing.

Fixes vs v1:
 - Multi-class filings (e.g., "93,650,433 Class S Shares, 21,440,559 Class D
   Shares and 348,729,633 Class I Shares were validly tendered") now SUMMED.
 - Accepted-for-purchase parsed the same way.
 - Percent statements captured ("requests are approximately 10% of shares
   outstanding", "represents X% of outstanding shares") for normalization
   back-out when XBRL shares outstanding is unavailable.
 - Parse primary doc + press-release exhibits (skip index/.txt duplicates).

Output: results/m2_tender_panel_v2.json
"""
import json, re, time, urllib.request
from pathlib import Path
from datetime import datetime
from html import unescape

BASE = Path(__file__).resolve().parent.parent
RESULTS = BASE / "results"
RAW = RESULTS / "raw_excerpts_v2"
RAW.mkdir(exist_ok=True, parents=True)

UA = {"User-Agent": "Jihwan Woo jihwan.woo@kakao.com (academic research)"}

FUNDS = {
    "BCRED": "0001803498",  # Blackstone Private Credit Fund
    "OCIC":  "0001812554",  # Blue Owl Credit Income Corp.
    "ADS":   "0001837532",  # Apollo Debt Solutions BDC
    "HLEND": "0001838126",  # HPS Corporate Lending Fund
    "ASIF":  "0001918712",  # Ares Strategic Income Fund
    "OSCF":  "0001872371",  # Oaktree Strategic Credit Fund
    "FPCF":  "0001920453",  # Fidelity Private Credit Fund
    "GCRED": "0001930087",  # Golub Capital Private Credit Fund
    "PCAP":  "0001911066",  # Nuveen Churchill Private Capital Income Fund
    "OTIC":  "0001869453",  # Blue Owl Technology Income Corp.
}

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
PCT_REQ = re.compile(
    r"(?:repurchase\s+requests?|tendered)[^.]{0,120}?(?:approximately\s+)?([\d.]+)\s*%\s+of\s+(?:the\s+)?(?:Fund'?s?\s+|Company'?s?\s+)?(?:outstanding\s+shares|shares\s+outstanding)", re.I)
PCT_FUL = re.compile(
    r"(?:fulfill(?:ing)?|repurchas\w+|purchas\w+|accept\w+)[^.]{0,140}?(?:representing\s+|up\s+to\s+)?(?:approximately\s+)?([\d.]+)\s*%\s+of\s+(?:the\s+)?(?:Fund'?s?\s+|Company'?s?\s+)?(?:outstanding\s+shares|shares\s+outstanding)", re.I)

def sentences(text):
    return re.split(r"(?<=\.)\s+", text)

def parse_doc(text):
    """Return dict with tendered/accepted share sums (max over sentences),
    percent statements, proration/upsize language, and evidence sentences."""
    out = {"tendered": None, "accepted": None, "pct_requested": None,
           "pct_fulfilled": None, "prorated_lang": False, "upsized_lang": False,
           "full_fulfillment_lang": False, "evidence": []}
    low_all = text.lower()
    out["prorated_lang"] = bool(re.search(r"pro\s*rata\s+basis|prorat", low_all))
    out["upsized_lang"] = bool(re.search(
        r"(?:increase[sd]?|upsiz\w+)[^.]{0,80}(?:repurchase\s+cap|the\s+offer|amount)", low_all))
    for s in sentences(text):
        low = s.lower()
        nums = [float(m.group(1).replace(",", "")) for m in SHARE_NUM.finditer(s)]
        if re.search(r"(?:validly|properly)\s+tendered|were\s+tendered|repurchase\s+requests?\s+(?:for|totaling)", low) and nums:
            tot = sum(nums)
            if out["tendered"] is None or tot > out["tendered"]:
                out["tendered"] = tot
                out["evidence"].append(("tendered", s[:400]))
        if re.search(r"accepted\s+for\s+(?:purchase|repurchase)|(?:has\s+)?(?:purchased|repurchased)\b", low) and nums:
            tot = sum(nums)
            if out["accepted"] is None or tot > out["accepted"]:
                out["accepted"] = tot
                out["evidence"].append(("accepted", s[:400]))
        if re.search(r"fulfill(?:ed|ing)?\s+(?:100%|all)\s+(?:of\s+)?(?:the\s+)?repurchase\s+requests", low):
            out["full_fulfillment_lang"] = True
            out["evidence"].append(("full_fulfillment", s[:300]))
    m = PCT_REQ.search(text)
    if m:
        out["pct_requested"] = float(m.group(1))
        out["evidence"].append(("pct_requested", m.group(0)[:300]))
    m = PCT_FUL.search(text)
    if m:
        v = float(m.group(1))
        if v <= 20:  # sanity: fulfillment cap statements
            out["pct_fulfilled"] = v
            out["evidence"].append(("pct_fulfilled", m.group(0)[:300]))
    return out

def parse_filing(cik, accession):
    acc = accession.replace("-", "")
    idx = get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/index.json")
    best = {"tendered": None, "accepted": None, "pct_requested": None,
            "pct_fulfilled": None, "prorated_lang": False, "upsized_lang": False,
            "full_fulfillment_lang": False, "evidence": []}
    for item in idx["directory"]["item"]:
        n = item["name"]
        ln = n.lower()
        if not ln.endswith((".htm", ".html")):
            continue
        if "index" in ln or "filingfees" in ln:
            continue
        try:
            text = strip_html(get(
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{n}",
                as_json=False))
        except Exception:
            continue
        r = parse_doc(text)
        for k in ("tendered", "accepted", "pct_requested", "pct_fulfilled"):
            if r[k] is not None and (best[k] is None or r[k] > best[k]):
                best[k] = r[k]
        for k in ("prorated_lang", "upsized_lang", "full_fulfillment_lang"):
            best[k] = best[k] or r[k]
        best["evidence"] += r["evidence"]
        time.sleep(0.12)
    return best

panel = []
for tick, cik in FUNDS.items():
    print(f"\n=== {tick} ===")
    try:
        d = get(f"https://data.sec.gov/submissions/CIK{cik}.json")
    except Exception as e:
        print("  submissions ERR", str(e)[:120])
        continue
    rec = d["filings"]["recent"]
    rows = list(zip(rec["form"], rec["accessionNumber"], rec["filingDate"]))
    toia = sorted([(a, dt) for f, a, dt in rows
                   if f == "SC TO-I/A" and dt >= "2024-01-01"], key=lambda x: x[1])
    print(f"  SC TO-I/A since 2024: {len(toia)}")
    for acc, dt in toia:
        try:
            r = parse_filing(cik, acc)
        except Exception as e:
            panel.append({"fund": tick, "date": dt, "error": str(e)[:120]})
            continue
        row = {"fund": tick, "date": dt, "accession": acc, **{
            k: r[k] for k in ("tendered", "accepted", "pct_requested",
                              "pct_fulfilled", "prorated_lang", "upsized_lang",
                              "full_fulfillment_lang")}}
        if r["tendered"] and r["accepted"]:
            row["oversub_ratio"] = round(r["tendered"] / r["accepted"], 3)
        elif r["pct_requested"] and r["pct_fulfilled"]:
            row["oversub_ratio"] = round(r["pct_requested"] / r["pct_fulfilled"], 3)
        panel.append(row)
        if r["evidence"]:
            (RAW / f"{tick}_{dt}.json").write_text(
                json.dumps({"accession": acc, "evidence": r["evidence"][:10]},
                           indent=2))
        if row.get("tendered") or row.get("pct_requested"):
            print(f"  {dt}: tendered={row.get('tendered')}, "
                  f"accepted={row.get('accepted')}, "
                  f"pct_req={row.get('pct_requested')}, "
                  f"pct_ful={row.get('pct_fulfilled')}, "
                  f"ratio={row.get('oversub_ratio')}, "
                  f"prorate={row['prorated_lang']}, full={row['full_fulfillment_lang']}")

out = {
    "meta": {
        "run_at": datetime.now().isoformat(),
        "data_source": "SEC EDGAR SC TO-I/A, 10 non-traded BDCs, 2024-01 ~ present",
        "parser": "v2: share-class sums per sentence; percent back-out; "
                  "evidence sentences in raw_excerpts_v2/",
        "interval_funds_note": "Cliffwater et al. use N-23C3A + N-CSR for results; "
                               "deferred to Aug batch (different parse structure)",
    },
    "panel": panel,
}
(RESULTS / "m2_tender_panel_v2.json").write_text(json.dumps(out, indent=2))
print(f"\nSaved -> {RESULTS / 'm2_tender_panel_v2.json'} ({len(panel)} filings)")
