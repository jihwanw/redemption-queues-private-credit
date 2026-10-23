"""build_offer_master.py — one row per tender OFFER (fund × commencement), from the cached SC TO-I documents, linked to the result filings in
m2_tender_panel_v3.json by expiry date. Fields and their filing language:
 commencement = SC TO-I filing date; expiry = "scheduled to expire at ... on <date>" (or "WILL EXPIRE ... ON <DATE>"); valuation_date = "determined as of <date>" /
 "VALUATION DATE: <date>" / "price per share in effect as of <date>"; cap_shares = "offer(ing) to purchase up to N Shares" / "will purchase up to N Shares";
 cap_pct and cap_basis_date = "represent approximately X% of the Fund's Shares outstanding as of <date>" (or "X% of the aggregate number of ... shares outstanding as of <date>");
 shares_outstanding_basis = cap_shares / cap_pct (the fund's own denominator). Result filings (prelim/final/amendments) are attached with their dates; final values from v3."""
import json, re, sys
from pathlib import Path
from datetime import datetime, timedelta
sys.path.insert(0, str(Path(__file__).resolve().parent)); from reextract_independent import to_text, sentences
BASE = Path(__file__).resolve().parent.parent; CACHE = BASE / "results" / "filings_cache"
MON = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}"
def pdate(s):
    try: return datetime.strptime(s, "%B %d, %Y").strftime("%Y-%m-%d")
    except ValueError: return None
EXP = re.compile(r"(?:scheduled\s+to\s+expire|will\s+expire|expires?)\s+(?:at\s+[^,]{0,25},?\s*(?:eastern|new york)[^,]{0,15},?\s*)?on\s+(" + MON + r")", re.I)
VAL = re.compile(r"(?:determined\s+as\s+of|valuation\s+date\s*:?\s*(?:is|will\s+be|of)?|price\s+per\s+share\s+in\s+effect\s+as\s+of|net\s+asset\s+value\s+(?:per\s+share\s+)?as\s+of)\s*(" + MON + r")", re.I)
CAPN = re.compile(r"(?:offer(?:ing)?\s+to\s+(?:purchase|repurchase)|will\s+(?:purchase|repurchase)|purchase)\s+up\s+to\s+(?:approximately\s+)?(?:the\s+tender\s+cap\s+of\s+)?([\d,]+(?:\.\d+)?)\s+(?:of\s+those\s+outstanding\s+)?(?:class\s+[a-z]\s+)?(?:common\s+)?shares", re.I)   # 'Class I Shares' (PCAP, Nov 2023)
CAPP = re.compile(r"(\d(?:\.\d+)?)\s*%\s+of\s+(?:the\s+)?(?:fund.s|company.s)?\s*(?:aggregate\s+number\s+of\s+)?(?:the\s+)?(?:fund.s\s+|company.s\s+)?(?:outstanding\s+)?(?:common\s+)?shares(?:\s+of\s+beneficial\s+interest)?\s*(?:outstanding)?\s+as\s+of\s+(" + MON + r")", re.I)
def parse_offer(folder):
    o = {"folder": folder.name, "fund": folder.name.split("_")[0], "commencement": folder.name.split("_")[1], "accession": folder.name.split("_")[2], "expiry": None, "valuation_date": None, "cap_shares": None, "cap_pct": None, "cap_basis_date": None, "evidence": []}
    for f in sorted(folder.glob("*.html")):
        for s in sentences(to_text(f.read_text(errors="ignore"))):
            if len(s) > 900: continue
            if o["expiry"] is None:
                m = EXP.search(s)
                if m and pdate(m.group(1)): o["expiry"] = pdate(m.group(1)); o["evidence"].append(("expiry", s[:260]))
            if o["valuation_date"] is None and not re.search(r"illustrative|for example|following year|EX-FILING FEES|xbrli|transaction value is calculated|Fee Offsets|filing fee", s, re.I):   # filing-fee exhibits cite the NAV used for the fee, not the valuation date
                m = VAL.search(s)
                if m and pdate(m.group(1)): o["valuation_date"] = pdate(m.group(1)); o["evidence"].append(("valuation", s[:260]))
            if o["cap_shares"] is None:
                m = CAPN.search(s)
                if m: o["cap_shares"] = float(m.group(1).replace(",", "")); o["evidence"].append(("cap_shares", s[:260]))
            if o["cap_pct"] is None:
                m = CAPP.search(s)
                if m and pdate(m.group(2)): o["cap_pct"] = float(m.group(1)); o["cap_basis_date"] = pdate(m.group(2)); o["evidence"].append(("cap_pct", s[:260]))
    if o["cap_shares"] and o["cap_pct"]: o["shares_outstanding_basis"] = round(o["cap_shares"] / (o["cap_pct"] / 100))
    return o
offers = [parse_offer(d) for d in sorted(CACHE.iterdir()) if d.is_dir() and d.name.endswith("_SCTOI")]
v3 = json.load(open(BASE / "results" / "m2_tender_panel_v3.json"))
results = [dict(key=k, fund=k.split("_")[0], filing_date=k.split("_")[1], **{kk: vv for kk, vv in v.items() if kk != "folder"}) for k, v in v3.items()]
for o in offers:
    o["result_filings"] = []
    if not o["expiry"]: continue
    ex = datetime.strptime(o["expiry"], "%Y-%m-%d")
    for r in results:
        if r["fund"] != o["fund"]: continue
        fd = datetime.strptime(r["filing_date"], "%Y-%m-%d")
        rex = datetime.strptime(r["expiry"], "%Y-%m-%d") if r["expiry"] else None
        same = (rex is not None and ex <= rex <= ex + timedelta(days=20)) or (rex is None and ex <= fd <= ex + timedelta(days=75))
        if same: o["result_filings"].append({k: r[k] for k in ("filing_date", "key", "expiry", "tendered", "tendered_approx", "accepted", "full_fill", "prorated", "upsized", "pct_requested", "pct_fulfilled")})
    rex = sorted({r["expiry"] for r in o["result_filings"] if r.get("expiry")})
    o["scheduled_expiry"] = o["expiry"]
    if rex and rex[-1] > o["expiry"]: o["expiry"] = rex[-1]; o["extended"] = True; o["evidence"].append(("expiry_actual", f"result filing reports expiry {rex[-1]} (scheduled {o['scheduled_expiry']})"))
    finals = [r for r in o["result_filings"] if r["tendered"] is not None and not r["tendered_approx"]]
    fin = finals[-1] if finals else ([r for r in o["result_filings"] if r["tendered"] is not None] or [None])[-1]
    if fin:
        o.update(final_filing=fin["filing_date"], tendered=fin["tendered"], accepted=fin["accepted"], prorated_language=any(r["prorated"] for r in o["result_filings"]), full_fill=fin["full_fill"], upsized=any(r["upsized"] for r in o["result_filings"]))
        o["rationed"] = bool(fin["tendered"] and fin["accepted"] is not None and fin["accepted"] < 0.999 * fin["tendered"]); o["prorated"] = o["rationed"]
        if o.get("cap_shares") and fin["accepted"] and fin["accepted"] > 1.01 * o["cap_shares"]: o["upsized"] = True; o["enlarged_by_outcome"] = True; o["evidence"].append(("enlarged", f"accepted {fin['accepted']:,.0f} shares exceeds the commencement cap of {o['cap_shares']:,.0f} by more than 1%"))   # ASIF Dec-2025: 21,646,158 accepted vs cap 19,157,609, no 'upsize' wording
        if fin["tendered"] and fin["accepted"]: o["fill_rate"] = round(min(fin["accepted"] / fin["tendered"], 1), 4); o["oversub"] = round(fin["tendered"] / fin["accepted"], 3)
        elif fin["tendered"] == 0: o["fill_rate"] = 1.0; o["oversub"] = 1.0; o["zero_tender"] = True   # 'No Shares ... were validly tendered' (PCAP Dec 2023, GCRED May 2024)
        if o.get("shares_outstanding_basis") and fin["tendered"] is not None: o["tendered_pct_basis"] = round(100 * fin["tendered"] / o["shares_outstanding_basis"], 2)
        else:
            # OCIC/OTIC state the requested share directly: "... were validly tendered ..., which represents X% of the aggregate number of the Company's shares outstanding as of <date>"
            for f in sorted((CACHE / fin["key"]).glob("*.html")):
                if re.match(r"R\d+\.html$", f.name): continue
                for sent in sentences(to_text(f.read_text(errors="ignore"))):
                    m = re.search(r"tendered[^.]{0,400}?represents?\s+(\d{1,2}(?:\.\d+)?)\s*%\s+of\s+the\s+aggregate\s+number\s+of\s+the\s+company.s\s+shares\s+outstanding", sent, re.I)
                    if m: o["tendered_pct_stated"] = float(m.group(1)); o["tendered_pct_basis"] = float(m.group(1)); o["shares_outstanding_basis"] = round(fin["tendered"] / (float(m.group(1)) / 100)); o["evidence"].append(("tendered_pct_stated", sent[:300])); break
                if o.get("tendered_pct_stated"): break
# OCIC/OTIC state the cap as a dollar amount: cap shares = offer dollars ÷ mean of the three classes' most recent net offering prices (both stated in the offer document)
AMT = re.compile(r"repurchased\s+with\s+approximately\s+\$\s?([\d,]+(?:\.\d+)?)", re.I); NAVC = re.compile(r"most\s+recent\s+net\s+offering\s+prices?\s+per\s+share[^$]{0,120}\$\s?(\d+\.\d+)[^$]{0,30}\$\s?(\d+\.\d+)[^$]{0,30}\$\s?(\d+\.\d+)", re.I)
for o in offers:
    if o["fund"] not in ("OCIC", "OTIC") or o.get("shares_outstanding_basis") or o.get("tendered") is None: continue
    amt = nav = None
    for f in sorted((CACHE / o["folder"]).glob("*.html")):
        for sent in sentences(to_text(f.read_text(errors="ignore"))):
            if amt is None and AMT.search(sent): amt = float(AMT.search(sent).group(1).replace(",", "")); o["evidence"].append(("offer_dollars", sent[:260]))
            if nav is None and NAVC.search(sent): g = NAVC.search(sent).groups(); nav = sum(float(x) for x in g) / 3; o["evidence"].append(("nav_classes", sent[:260]))
    if amt and nav:
        o["cap_shares"] = round(amt / nav); o["cap_shares_source"] = "offer dollar amount ÷ mean of the three classes' most recent net offering prices"; o["shares_outstanding_basis"] = round(o["cap_shares"] / (o["cap_pct"] / 100)); o["tendered_pct_basis"] = round(100 * o["tendered"] / o["shares_outstanding_basis"], 2)
json.dump({"meta": {"built": datetime.now().strftime("%Y-%m-%d %H:%M"), "doc": __doc__}, "offers": offers}, open(BASE / "results" / "offer_master_v3.json", "w"), indent=1)
print(f"offers: {len(offers)}; with expiry {sum(1 for o in offers if o['expiry'])}; with cap_shares {sum(1 for o in offers if o['cap_shares'])}; with cap_pct {sum(1 for o in offers if o['cap_pct'])}; linked to a final result {sum(1 for o in offers if o.get('tendered'))}")
print(f"{'fund':6}{'commence':11}{'expiry':11}{'valuation':11}{'cap%':>5}{'cap_shares':>13}{'sh_out_basis':>14}{'tendered':>14}{'accepted':>13}{'fill':>6}{'req%':>6}  final_filing  flags")
for o in offers:
    if o["commencement"] >= "2025-10-01":
        print(f"{o['fund']:6}{o['commencement']:11}{str(o['expiry']):11}{str(o['valuation_date']):11}{str(o['cap_pct']):>5}{(o['cap_shares'] or 0):>13,.0f}{(o.get('shares_outstanding_basis') or 0):>14,.0f}{(o.get('tendered') or 0):>14,.0f}{(o.get('accepted') or 0):>13,.0f}{(o.get('fill_rate') or float('nan')):>6.2f}{(o.get('tendered_pct_basis') or float('nan')):>6.1f}  {o.get('final_filing','-'):11}  {'prorated ' if o.get('prorated') else ''}{'upsized ' if o.get('upsized') else ''}{'n_results=' + str(len(o['result_filings']))}")
