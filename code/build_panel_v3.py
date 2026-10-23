"""build_panel_v3.py — tender-offer results panel rebuilt from the locally cached filings (results/filings_cache), independent of m2_main_v2.py.
Rules (each value carries its evidence sentence):
 tendered  : sum of share counts (decimals allowed; '$' amounts excluded) in a sentence stating shares were validly/properly tendered (and not withdrawn);
             'approximately X million Shares ... were validly tendered' also accepted (flag approx=True).
 accepted  : sum of share counts in a sentence 'accepted for purchase <counts>' / 'purchased <counts> ... Shares'; if the filing says 'accepted for purchase 100% of the Shares'
             or 'purchased all validly tendered ... Shares', accepted = tendered (full=True). Footnote sentences ('This amount includes', 'repurchased at a price ... in the Fund's tender offer that expired') excluded.
 pct_requested / pct_fulfilled : percent-of-outstanding statements with their sentence.
 prorated / upsized : language flags.  expiry: 'The Offer expired ... on <date>'."""
import json, re, html, sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parent)); from reextract_independent import to_text, sentences
BASE = Path(__file__).resolve().parent.parent; CACHE = BASE / "results" / "filings_cache"
NUMD = re.compile(r"(?<![\d.,$])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{4,}(?:\.\d+)?)(?![\d,])")
def share_counts(s):
    out = []
    for m in NUMD.finditer(s):
        pre = s[max(0, m.start() - 3): m.start()]
        if "$" in pre: continue
        if "," not in m.group(1) and "." not in m.group(1) and 1900 <= float(m.group(1)) <= 2100: continue   # a year, not a share count
        tail = s[m.end(): m.end() + 40].lower()
        if re.match(r"\s*(class\s+\w+\s+)?(common\s+)?shares?\b", tail) or re.match(r"\s*(class\s+\w+\s+)?shares?\s+of", tail) or re.search(r"shares", s[m.end(): m.end() + 60].lower()): out.append(float(m.group(1).replace(",", "")))
    return out
FOOT = re.compile(r"this amount includes|repurchased at a price|tender offer that expired|prior tender offer|previous tender offer", re.I)
TEND = re.compile(r"(validly|properly)\s+tendered|were\s+tendered|tendered\s+and\s+not\s+withdrawn|tendered\s+prior\s+to", re.I)
ACCN = re.compile(r"accepted\s+for\s+(purchase|repurchase|payment)\s+(approximately\s+)?[\d,]+|(purchased|repurchased)\s+(an\s+aggregate\s+of\s+)?(approximately\s+)?[\d,]+(\.\d+)?\s+(class|common|shares)", re.I)
PAYALL = re.compile(r"representing\s+the\s+net\s+asset\s+value[^.]{0,60}of\s+the\s+total\s+amount\s+of\s+(the\s+)?(class\s+\w+\s+(and\s+class\s+\w+\s+)?)?shares\s+tendered", re.I)
FULL = re.compile(r"accepted\s+for\s+purchase\s+100%|purchased\s+all\s+(of\s+the\s+)?(validly\s+)?tendered|accepted\s+all\s+(of\s+the\s+)?(validly\s+)?tendered|(satisf|fulfill|meet|honor)\w*\s+100%\s+of\s+(the\s+)?(tender|repurchase)\s+requests", re.I)
APPROX = re.compile(r"approximately\s+(\d+(?:\.\d+)?)\s+million\s+shares", re.I)
ZERO = re.compile(r"\bNo\s+(Class\s+\w+\s+)?(Common\s+)?Shares\s+(of\s+the\s+Fund\s+)?were\s+(validly\s+)?tendered", re.I)
SMALL = re.compile(r"(?<![\d,.$])(\d{1,3})\s+(Class\s+\w+\s+)?(Common\s+)?Shares\s+(of\s+the\s+Fund\s+)?were\s+(validly\s+)?tendered", re.I)
EXP = re.compile(r"Offer\s+(?:expired|will\s+expire)\s+(?:at\s+)?.{0,60}?\bon\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})")
PCT = re.compile(r"(\d{1,2}(?:\.\d+)?)\s*%")
def extract(folder):
    o = {"folder": folder.name, "tendered": None, "tendered_approx": False, "accepted": None, "full_fill": False, "full_fill_by_payment": False, "prorated": False, "upsized": False, "expiry": None, "pct_requested": None, "pct_fulfilled": None, "evidence": []}
    for f in sorted(folder.glob("*.html")):
        if re.match(r"R\d+\.html$", f.name): continue   # XBRL cover pages (filing-fee tables)
        t = to_text(f.read_text(errors="ignore")); low = t.lower()
        if re.search(r"pro\s*rata|prorat", low): o["prorated"] = True
        if re.search(r"increase[sd]?\s+the\s+(aggregate\s+)?(amount|number|size)|upsiz|additional\s+\d(\.\d+)?%\s+of\s+the|up\s+to\s+an\s+additional", low): o["upsized"] = True
        for s in sentences(t):
            if len(s) > 1500 or FOOT.search(s): continue
            m = EXP.search(s)
            if m and not o["expiry"]:
                try: o["expiry"] = datetime.strptime(m.group(1), "%B %d, %Y").strftime("%Y-%m-%d")
                except ValueError: pass
            if TEND.search(s):
                c = share_counts(s)
                if c and o["tendered"] is None: o["tendered"] = round(sum(c), 3); o["evidence"].append(("tendered", s[:400]))
                elif not c and o["tendered"] is None:
                    a = APPROX.search(s); z = ZERO.search(s); sm = SMALL.search(s)
                    if a: o["tendered"] = float(a.group(1)) * 1e6; o["tendered_approx"] = True; o["evidence"].append(("tendered~", s[:400]))
                    elif z: o["tendered"] = 0.0; o["accepted"] = 0.0; o["zero_tender"] = True; o["full_fill"] = True; o["evidence"].append(("tendered_zero", s[:400]))   # 'No Shares ... were validly tendered' (PCAP Dec 2023, GCRED May 2024)
                    elif sm: o["tendered"] = float(sm.group(1)); o["evidence"].append(("tendered_small", s[:400]))   # a count below 1,000 written without a thousands separator (ASIF Dec 2023: 301 Shares)
            if FULL.search(s): o["full_fill"] = True; o["evidence"].append(("full", s[:300]))
            elif PAYALL.search(s) and not o["prorated"]: o["full_fill"] = True; o["full_fill_by_payment"] = True; o["evidence"].append(("full_by_payment", s[:300]))
            elif ACCN.search(s) and not TEND.search(s[:ACCN.search(s).start()]):
                c = share_counts(s)
                if c and o["accepted"] is None: o["accepted"] = round(sum(c), 3); o["evidence"].append(("accepted", s[:400]))
            for pm in PCT.finditer(s):
                v = float(pm.group(1)); ctx = s[max(0, pm.start() - 170): pm.end() + 80].lower()
                if o["pct_requested"] is None and re.search(r"request|tender", ctx) and re.search(r"outstanding|net asset|nav", ctx): o["pct_requested"] = v; o["evidence"].append(("pct_req", s[:300]))
                if o["pct_fulfilled"] is None and re.search(r"will\s+repurchase|repurchased|purchase\s+up\s+to|accepted|fulfill", ctx) and re.search(r"outstanding|net asset|nav", ctx) and not re.search(r"request", ctx): o["pct_fulfilled"] = v; o["evidence"].append(("pct_ful", s[:300]))
    if o["full_fill"] and o["tendered"] is not None and o["accepted"] is None: o["accepted"] = o["tendered"]
    if o["tendered"] and o["accepted"]: o["fill_rate"] = round(min(o["accepted"] / o["tendered"], 1.0), 4)
    return o
if __name__ == "__main__":
    out = {d.name: extract(d) for d in sorted(CACHE.iterdir()) if d.is_dir() and list(d.glob("*.html")) and not d.name.endswith("_SCTOI")}   # result filings only; commencement documents (SC TO-I, cached by build_offer_master.py) are parsed there
    json.dump(out, open(BASE / "results" / "m2_tender_panel_v3.json", "w"), indent=1)
    P = json.load(open(BASE / "results" / "m2_tender_panel_v2.json")); rows = P if isinstance(P, list) else (P.get("rows") or P.get("panel") or [v for v in P.values() if isinstance(v, list)][0])
    n_t = n_a = 0; diffs = []
    for r in rows:
        k = f"{r['fund']}_{r['date']}_{r['accession']}"; e = out[k]
        dt = (r.get("tendered") is None) != (e["tendered"] is None) or (r.get("tendered") is not None and e["tendered"] is not None and abs(r["tendered"] - e["tendered"]) > 1)
        a_old = r.get("accepted"); da = (a_old is None) != (e["accepted"] is None) or (a_old is not None and e["accepted"] is not None and abs(a_old - e["accepted"]) > 1)
        if dt: n_t += 1
        if da: n_a += 1
        if dt or da: diffs.append(f"{k}: tendered v2={r.get('tendered')} v3={e['tendered']}{'~' if e['tendered_approx'] else ''} | accepted v2={a_old} v3={e['accepted']} full={e['full_fill']} pror={e['prorated']}")
    print(f"rows {len(rows)}: tendered differs {n_t}, accepted differs {n_a}"); print("\n".join(diffs))
