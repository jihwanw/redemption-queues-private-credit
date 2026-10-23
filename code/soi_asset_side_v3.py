"""soi_asset_side_v3.py — Stage 1: collect schedule-of-investments (SOI) facts and non-accrual sentences
from every 10-Q / 10-K (report dates 2024-03-31 … 2026-06-30) of the ten non-traded funds and their
exchange-listed siblings run by the same sponsor.

Why: JFSR referee comment 3b asked for direct asset-side measures (loan overlap, marks on common loans,
non-accruals) instead of the listed-twin discount proxy. This script produces the raw, evidence-backed
extracts; `soi_asset_side_measures_v3.py` turns them into pair-level measures.

Sources (all public, SEC EDGAR):
  - submissions index   https://data.sec.gov/submissions/CIK##########.json  (forms, report dates, accessions, primary documents)
  - primary documents   https://www.sec.gov/Archives/edgar/data/<cik>/<accession-no-dashes>/<primaryDocument>
Inline-XBRL facts read (US-GAAP taxonomy element names, as tagged by the filer):
  us-gaap:InvestmentOwnedAtFairValue, us-gaap:InvestmentOwnedAtCost, us-gaap:InvestmentOwnedBalancePrincipalAmount,
  us-gaap:InvestmentInterestRate, us-gaap:InvestmentBasisSpreadVariableRate, us-gaap:InvestmentOwnedPercentOfNetAssets,
  dimension us-gaap:InvestmentIdentifierAxis (typed member text, e.g. "Corfin Holdings, Inc. 1 | Non-Affiliated Issuer";
  verified on BXSL 10-Q for 2026-06-30, accession 0001736035-26-000016, 2026-10-21).
Every stored fact keeps: fund, cik, form, report date, filed date, accession, context id, fact id.
Non-accrual: every sentence of the primary document containing "non-accrual"/"nonaccrual" and a percent sign is stored
verbatim (with character offset) for the measures script and for human verification. Nothing is interpreted here.

CIKs: ten funds from code/m2_main_v2.py; twins from https://www.sec.gov/files/company_tickers.json (read 2026-10-21):
  BXSL 0001736035, OBDC 0001655888, ARCC 0001287750, GBDC 0001476765, OCSL 0001414932, MFIC 0001278752, NCDL 0001737924.
"""
from __future__ import annotations
import html as htmlmod, json, re, sys, time, urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
R = BASE / "results"; CACHE = R / "soi_cache"; CACHE.mkdir(parents=True, exist_ok=True)
OUT = R / "soi_raw_v3.json"
UA = {"User-Agent": "Jihwan Woo jihwan.woo@gmail.com (academic research)"}

src = (BASE / "code" / "m2_main_v2.py").read_text()
FUNDS = {m.group(1): m.group(2) for m in re.finditer(r'"([A-Z]+)":\s*"(\d{10})"', src)}
TWINS = {"BXSL": "0001736035", "OBDC": "0001655888", "ARCC": "0001287750", "GBDC": "0001476765",
         "OCSL": "0001414932", "MFIC": "0001278752", "NCDL": "0001737924"}
PAIRS = {"BCRED": "BXSL", "OCIC": "OBDC", "OTIC": "OBDC", "ASIF": "ARCC", "GCRED": "GBDC", "OSCF": "OCSL",
         "ADS": "MFIC", "PCAP": "NCDL"}  # FPCF and HLEND have no exchange-listed sibling under the same sponsor
ENTITIES = {**FUNDS, **TWINS}
DATE_MIN, DATE_MAX = "2024-03-31", "2026-06-30"

FACTS = ["us-gaap:InvestmentOwnedAtFairValue", "us-gaap:InvestmentOwnedAtCost", "us-gaap:InvestmentOwnedBalancePrincipalAmount",
         "us-gaap:InvestmentInterestRate", "us-gaap:InvestmentBasisSpreadVariableRate", "us-gaap:InvestmentOwnedPercentOfNetAssets"]


def get(u: str, binary=False, tries=5):
    err = None
    for a in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=180) as r:
                b = r.read(); time.sleep(0.15)
                return b if binary else b.decode("utf-8", "ignore")
        except Exception as e:
            err = e; time.sleep(2 * (a + 1))
    raise err


def filings(cik: str):
    sub = json.loads(get(f"https://data.sec.gov/submissions/CIK{cik}.json"))
    rec = sub["filings"]["recent"]
    rows = []
    for i in range(len(rec["form"])):
        if rec["form"][i] in ("10-Q", "10-K", "10-Q/A", "10-K/A") and DATE_MIN <= rec["reportDate"][i] <= DATE_MAX:
            rows.append(dict(form=rec["form"][i], filed=rec["filingDate"][i], report=rec["reportDate"][i],
                             accession=rec["accessionNumber"][i], doc=rec["primaryDocument"][i]))
    # older filings live in sub["filings"]["files"] pages; 2024Q1 for large filers may be there
    for f in sub["filings"].get("files", []):
        page = json.loads(get("https://data.sec.gov/submissions/" + f["name"]))
        for i in range(len(page["form"])):
            if page["form"][i] in ("10-Q", "10-K", "10-Q/A", "10-K/A") and DATE_MIN <= page["reportDate"][i] <= DATE_MAX:
                rows.append(dict(form=page["form"][i], filed=page["filingDate"][i], report=page["reportDate"][i],
                                 accession=page["accessionNumber"][i], doc=page["primaryDocument"][i]))
    # keep, per report date, the latest filed original (amendments kept separately, flagged)
    rows.sort(key=lambda r: (r["report"], r["filed"]))
    return rows


def fetch_doc(name: str, cik: str, f: dict) -> str:
    p = CACHE / f"{name}_{f['report']}_{f['accession']}.htm"
    if p.exists() and p.stat().st_size > 10000:
        return p.read_text(errors="ignore")
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{f['accession'].replace('-', '')}/{f['doc']}"
    txt = get(url)
    p.write_text(txt)
    return txt


CTX_RE = re.compile(r'<xbrli:context id="([^"]+)">(.*?)</xbrli:context>', re.S)
TYPED_RE = re.compile(r'<xbrldi:typedMember dimension="us-gaap:InvestmentIdentifierAxis">\s*<[^>]+>(.*?)</[^>]+>\s*</xbrldi:typedMember>', re.S)
EXPL_RE = re.compile(r'<xbrldi:explicitMember dimension="([^"]+)">([^<]+)</xbrldi:explicitMember>')
INST_RE = re.compile(r'<xbrli:instant>([0-9-]+)</xbrli:instant>')
FACT_RE = re.compile(r'<ix:nonFraction([^>]*)>(.*?)</ix:nonFraction>', re.S)
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


UNIT_RE = re.compile(r'<xbrli:unit id="([^"]+)">\s*<xbrli:measure>([^<]+)</xbrli:measure>', re.S)


def parse_soi(txt: str):
    """Return (investment contexts, facts) for the SOI lines. Fact units are stored as the unit's measure (e.g. iso4217:USD), not the filer's unit id."""
    umap = {uid: meas.strip().lower() for uid, meas in UNIT_RE.findall(txt)}
    ctxs = {}
    for cid, body in CTX_RE.findall(txt):
        m = TYPED_RE.search(body)
        if not m:
            continue
        inst = INST_RE.search(body)
        dims = {d: v for d, v in EXPL_RE.findall(body)}
        ctxs[cid] = dict(identifier=htmlmod.unescape(re.sub(r"\s+", " ", m.group(1)).strip()),
                         instant=inst.group(1) if inst else None, dims=dims)
    facts = []
    for attrs, inner in FACT_RE.findall(txt):
        a = dict(ATTR_RE.findall(attrs))
        if a.get("name") not in FACTS or a.get("contextRef") not in ctxs:
            continue
        raw = re.sub(r"<[^>]+>", "", inner).strip()
        if raw in ("", "-", "—", "–"):
            val = 0.0
        else:
            try:
                val = float(raw.replace(",", "").replace("$", "").strip())
            except ValueError:
                continue
        scale = int(a.get("scale", "0") or 0)
        val = val * (10 ** scale)
        if a.get("sign") == "-":
            val = -val
        facts.append(dict(ctx=a["contextRef"], name=a["name"], val=val, fid=a.get("id"), decimals=a.get("decimals"), unit=umap.get(a.get("unitRef"), (a.get("unitRef") or "").lower())))
    return ctxs, facts


NA_OCC = re.compile(r"non-?\s?accrual", re.I)
PCT_RE = re.compile(r"(\d|—|–|-)\s?%")


def nonaccrual_sentences(txt: str):
    """Windows of text (±450 characters) around every occurrence of 'non-accrual' that contains a percentage figure.
    Filers differ: Blackstone reports a table row 'Percentage of assets on non-accrual, at amortized cost … %', others write a
    sentence ('… on non-accrual status, representing x% and y% of the debt portfolio at cost and fair value'). Windows are stored
    verbatim; the measures script parses them and keeps the matched text as evidence."""
    body = re.sub(r"<[^>]+>", " ", txt)
    body = htmlmod.unescape(re.sub(r"\s+", " ", body))
    out, seen = [], set()
    for m in NA_OCC.finditer(body):
        w = body[max(0, m.start() - 450): m.end() + 450]
        if not PCT_RE.search(w):
            continue
        key = re.sub(r"[^a-z0-9%]", "", w.lower())[:300]
        if key in seen:
            continue
        seen.add(key); out.append(dict(offset=m.start(), window=w.strip()))
        if len(out) >= 60:
            break
    return out


def main(only=None):
    out = json.loads(OUT.read_text()) if OUT.exists() else {"meta": {"collected": None, "entities": {}}, "filings": []}
    done = {(f["entity"], f["accession"]) for f in out["filings"]}
    for name, cik in ENTITIES.items():
        if only and name not in only:
            continue
        out["meta"]["entities"][name] = dict(cik=cik, role="fund" if name in FUNDS else "twin", twin_of=[k for k, v in PAIRS.items() if v == name] or None,
                                             twin=PAIRS.get(name))
        try:
            fl = filings(cik)
        except Exception as e:
            print(f"[{name}] submissions failed: {e}", file=sys.stderr); continue
        print(f"[{name}] {len(fl)} filings in window", flush=True)
        for f in fl:
            if (name, f["accession"]) in done:
                continue
            try:
                txt = fetch_doc(name, cik, f)
            except Exception as e:
                print(f"[{name}] {f['accession']} download failed: {e}", file=sys.stderr); continue
            ctxs, facts = parse_soi(txt)
            na = nonaccrual_sentences(txt)
            rec = dict(entity=name, cik=cik, **f, size_bytes=len(txt), n_investment_contexts=len(ctxs), n_facts=len(facts),
                       contexts=ctxs, facts=facts, nonaccrual_sentences=na)
            out["filings"].append(rec)
            print(f"  {f['form']} {f['report']} filed {f['filed']} acc {f['accession']}: contexts {len(ctxs)}, facts {len(facts)}, non-accrual sentences {len(na)}", flush=True)
            out["meta"]["collected"] = time.strftime("%Y-%m-%d %H:%M:%S")
            OUT.write_text(json.dumps(out))
    print("saved", OUT, "filings:", len(out["filings"]))


def refresh_na():
    out = json.loads(OUT.read_text())
    for f in out["filings"]:
        p = CACHE / f"{f['entity']}_{f['report']}_{f['accession']}.htm"
        if p.exists():
            f["nonaccrual_sentences"] = nonaccrual_sentences(p.read_text(errors="ignore"))
            print(f"{f['entity']} {f['report']}: {len(f['nonaccrual_sentences'])} non-accrual windows")
    OUT.write_text(json.dumps(out))


def reparse_facts():
    """Re-read SOI facts from the cached documents (no download), e.g. after a parser change."""
    out = json.loads(OUT.read_text())
    for f in out["filings"]:
        p = CACHE / f"{f['entity']}_{f['report']}_{f['accession']}.htm"
        if p.exists():
            ctxs, facts = parse_soi(p.read_text(errors="ignore"))
            f["contexts"], f["facts"], f["n_investment_contexts"], f["n_facts"] = ctxs, facts, len(ctxs), len(facts)
            print(f"{f['entity']} {f['report']}: {len(facts)} facts")
    OUT.write_text(json.dumps(out))


if __name__ == "__main__":
    if "--refresh-na" in sys.argv:
        refresh_na()
    elif "--reparse" in sys.argv:
        reparse_facts()
    else:
        main(only=set(sys.argv[1:]) or None)
