"""soi_nonaccrual_v3.py — non-accrual share of the portfolio, by fund and quarter-end, read from each filing's own sentences.

Input : results/soi_cache/<ENTITY>_<report>_<accession>.htm (downloaded by soi_asset_side_v3.py)
Output: results/nonaccrual_v3.json  (per entity × report date: candidate statements with parsed numbers + verbatim sentence)
        paper/reviews/NONACCRUAL_EVIDENCE_v3.md  (every parsed statement with its sentence, for human verification)

Sentence patterns handled (verified on 2026-06-30 filings, 2026-10-21):
  A  "… on non-accrual status represented 2.4% of the total investments at amortized cost (or 1.4% at fair value)"           (Ares)
  B  "… 4.6 % of total investments at amortized cost, or 2.8 % of total investments at fair value, were on non-accrual status" (Apollo)
  C  "… on non-accrual status … which represented approximately 1.52 % of total investments at fair value"                    (Nuveen)
  D  "… on non-accrual, which represents 0.8% of our portfolio at fair value"                                                  (Blue Owl)
  E  "… on non-accrual status that in aggregate represented 4.2 % and 3.1 % of the debt portfolio at cost and fair value, respectively" (Oaktree)
  F  "Investments on non-accrual represented 0.4%, 0.2% and less than 0.1% of total investments at fair value … as of December 31, 2025, 2024 and 2023, respectively" (Blackstone 10-K)
  G  "Percentage of assets on non-accrual, at amortized cost … x % y %" (Blackstone 10-Q MD&A table row; first value = report date)
  H  "none of the loans were on non-accrual status" / "no investments on non-accrual status" / "no … borrowers were on non-accrual" → 0
Each parsed value records basis ('fair value' | 'amortized cost' | 'unspecified'), the as-of date when the sentence states one, and the
sentence. The measures table uses, for each entity × report date, the fair-value-basis share as of the report date when stated,
otherwise the cost-basis share (flagged). Values that could not be parsed are left absent — never typed in.
"""
from __future__ import annotations
import html as htmlmod, json, re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
R = BASE / "results"; CACHE = R / "soi_cache"
RAW = json.loads((R / "soi_raw_v3.json").read_text())
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE_RE = re.compile(rf"({MONTHS})\s+(\d{{1,2}}),\s+(\d{{4}})")
MNUM = {m: i + 1 for i, m in enumerate(MONTHS.split("|"))}
NUM = r"((?:less than\s+)?\d+(?:\.\d+)?)\s*%"


def num(x):
    """'less than 0.1' -> (0.1, True); '2.4' -> (2.4, False)"""
    x = x.strip(); lt = x.lower().startswith("less than")
    return float(x.lower().replace("less than", "").strip()), lt


def to_iso(m):
    return f"{int(m.group(3)):04d}-{MNUM[m.group(1)]:02d}-{int(m.group(2)):02d}"


def sentences(txt: str):
    body = htmlmod.unescape(re.sub(r"<[^>]+>", " ", txt)).replace("\xa0", " ")
    body = re.sub(r"\s+", " ", body)
    # split on sentence ends not inside numbers; keep table-row fragments as their own "sentences" when they contain the key phrase
    parts = re.split(r"(?<=[a-zA-Z\)%”\"])\.\s+(?=[A-Z(“\"])", body)
    return [p.strip() for p in parts if re.search(r"non-?\s?accrual", p, re.I)]


JV_RE = re.compile(r"\b(JV|joint venture|ULTRA III|SDLP|Ivy Hill|IHAM|ADLP|Emerald|Verdelite)\b", re.I)   # sponsor programme vehicles and JVs whose own figures are not the registrant's


def parse(s: str):
    """Return list of dicts(basis, pct, lt, asof, pattern) parsed from one sentence. Sentences whose subject is a joint venture are skipped."""
    out = []
    low = s.lower()
    if JV_RE.search(s) and not re.search(r"excluding investments in joint ventures", s, re.I):
        return out
    dates = [to_iso(m) for m in DATE_RE.finditer(s)]
    m2 = re.search(rf"as of ({MONTHS}) (\d{{1,2}}), (\d{{4}}) and (\d{{4}})\b", s, re.I)
    if m2 and len(dates) == 1:   # "As of December 31, 2025 and 2024" -> second date shares month and day
        dates.append(f"{int(m2.group(4)):04d}-{MNUM[m2.group(1).capitalize()]:02d}-{int(m2.group(2)):02d}")
    # H: none
    m = re.search(r"\b(none of (?:the|our) (?:loans|investments|portfolio companies)|no (?:loans|investments|private credit borrowers|portfolio companies)[^.]{0,40}(?:were|was|are|is) on non-?accrual|(?:were|was|had) no (?:loans|investments|assets) on non-?accrual|had no assets on non-?accrual)", low)
    if m:
        out.append(dict(pos=m.start(), end=m.end(), basis="unspecified", pct=0.0, asof=None, pattern="H"))
    # A: "represented X% of the total investments at amortized cost (or Y% at fair value)" possibly twice with 'respectively'
    for m in re.finditer(rf"represented\s+{NUM}\s+of the total investments at amortized cost\s*\(or\s+{NUM}\s+at fair value\)", s, re.I):
        out.append(dict(pos=m.start(), end=m.end(), basis="amortized cost", pct=num(m.group(1))[0], lt=num(m.group(1))[1], pattern="A", asof=None)); out.append(dict(pos=m.start(), end=m.end(), basis="fair value", pct=num(m.group(2))[0], lt=num(m.group(2))[1], pattern="A", asof=None))
    for m in re.finditer(rf"and\s+{NUM}\s+at amortized cost\s*\(or\s+{NUM}\s+at fair value\)", s, re.I):
        d2 = dates[1] if len(dates) >= 2 else None
        out.append(dict(pos=m.start(), end=m.end(), basis="amortized cost", pct=num(m.group(1))[0], lt=num(m.group(1))[1], pattern="A2", asof=d2)); out.append(dict(pos=m.start(), end=m.end(), basis="fair value", pct=num(m.group(2))[0], lt=num(m.group(2))[1], pattern="A2", asof=d2))
    # B: "X % of total investments at amortized cost, or Y % of total investments at fair value, were on non-accrual status"
    for m in re.finditer(rf"{NUM}\s+of total investments at amortized cost,?\s+or\s+{NUM}\s+of total investments at fair value,?\s+were on non-?accrual", s, re.I):
        out.append(dict(pos=m.start(), end=m.end(), basis="amortized cost", pct=num(m.group(1))[0], lt=num(m.group(1))[1], pattern="B", asof=None)); out.append(dict(pos=m.start(), end=m.end(), basis="fair value", pct=num(m.group(2))[0], lt=num(m.group(2))[1], pattern="B", asof=None))
    # C: "which represented approximately X % of total investments at fair value"
    for m in re.finditer(rf"non-?accrual status[^.]{{0,120}}?represented (?:approximately\s+)?{NUM}\s+of (?:the )?total investments at fair value", s, re.I):
        out.append(dict(pos=m.start(), end=m.end(), basis="fair value", pct=num(m.group(1))[0], lt=num(m.group(1))[1], pattern="C", asof=None))
    # D: "on non-accrual, which represent(s|ed) X% of our portfolio at fair value"
    for m in re.finditer(rf"on non-?accrual,?\s+which represent(?:s|ed)?\s+(?:approximately\s+)?{NUM}\s+of (?:our|the) (?:debt )?portfolio at fair value", s, re.I):
        out.append(dict(pos=m.start(), end=m.end(), basis="fair value", pct=num(m.group(1))[0], lt=num(m.group(1))[1], pattern="D", asof=None))
    # E: "represented X % and Y % of the debt portfolio at cost and fair value, respectively"
    for m in re.finditer(rf"represented\s+{NUM}\s+and\s+{NUM}\s+of the (?:total )?(?:debt )?(?:portfolio|investments) at (?:amortized )?cost and fair value, respectively", s, re.I):
        out.append(dict(pos=m.start(), end=m.end(), basis="amortized cost", pct=num(m.group(1))[0], lt=num(m.group(1))[1], pattern="E", asof=None)); out.append(dict(pos=m.start(), end=m.end(), basis="fair value", pct=num(m.group(2))[0], lt=num(m.group(2))[1], pattern="E", asof=None))
    for m in re.finditer(rf"represented\s+{NUM}\s+and\s+{NUM}\s+of the (?:total )?(?:debt )?(?:portfolio|investments) at fair value and (?:amortized )?cost, respectively", s, re.I):
        out.append(dict(pos=m.start(), end=m.end(), basis="fair value", pct=num(m.group(1))[0], lt=num(m.group(1))[1], pattern="E2", asof=None)); out.append(dict(pos=m.start(), end=m.end(), basis="amortized cost", pct=num(m.group(2))[0], lt=num(m.group(2))[1], pattern="E2", asof=None))
    # F: Blackstone 10-K: "non-accrual represented a%, b% and less than c% of total investments at fair value … as of D1, D2 and D3, respectively"
    m = re.search(rf"non-?accrual represented\s+{NUM},\s+{NUM}\s+and\s+{NUM}\s+of total investments at fair value[^.]*?as of ({MONTHS}) (\d{{1,2}}), (\d{{4}}), (\d{{4}}) and (\d{{4}})", s, re.I)
    if m:
        mon, day = m.group(4), int(m.group(5))
        for pct, yr in zip((m.group(1), m.group(2), m.group(3)), (m.group(6), m.group(7), m.group(8))):
            out.append(dict(pos=m.start(), end=m.end(), basis="fair value", pct=num(pct)[0], lt=num(pct)[1], pattern="F", asof=f"{int(yr):04d}-{MNUM[mon]:02d}-{day:02d}"))
    m = re.search(rf"non-?accrual represented\s+{NUM}\s+and\s+{NUM}\s+of total investments at fair value[^.]*?as of ({MONTHS}) (\d{{1,2}}), (\d{{4}}) and (\d{{4}})", s, re.I)
    if m:
        mon, day = m.group(3), int(m.group(4))
        for pct, yr in zip((m.group(1), m.group(2)), (m.group(5), m.group(6))):
            out.append(dict(pos=m.start(), end=m.end(), basis="fair value", pct=num(pct)[0], lt=num(pct)[1], pattern="F2", asof=f"{int(yr):04d}-{MNUM[mon]:02d}-{day:02d}"))
    # G: Blackstone MD&A table row "Percentage of assets on non-accrual, at amortized cost (n) x % y %"  (x = report date column)
    m = re.search(r"Percentage of assets on non-?accrual, at amortized cost\s*(?:\(\d+\))?\s*(—|–|-|\d+(?:\.\d+)?)\s*%\s*(—|–|-|\d+(?:\.\d+)?)\s*%", s)
    if m:
        v = 0.0 if m.group(1) in ("—", "–", "-") else float(m.group(1))
        out.append(dict(pos=m.start(), end=m.end(), basis="amortized cost", pct=v, pattern="G", asof=None))
    # G2: Blackstone MD&A row at fair value
    m = re.search(r"Percentage of assets on non-?accrual, at fair value\s*(?:\(\d+\))?\s*(—|–|-|\d+(?:\.\d+)?)\s*%\s*(—|–|-|\d+(?:\.\d+)?)\s*%", s)
    if m:
        v = 0.0 if m.group(1) in ("—", "–", "-") else float(m.group(1))
        out.append(dict(pos=m.start(), end=m.end(), basis="fair value", pct=v, pattern="G2", asof=None))
    # I: Golub "non-accrual investments as a percentage of total investments at cost and fair value were X% and Y%, respectively" / "at both cost and fair value were X%"
    m = re.search(rf"non-?accrual investments as a percentage of total investments at cost and fair value were\s+{NUM}\s+and\s+{NUM}", s, re.I)
    if m:
        out.append(dict(pos=m.start(), end=m.end(), basis="amortized cost", pct=num(m.group(1))[0], lt=num(m.group(1))[1], pattern="I", asof=None)); out.append(dict(pos=m.start(), end=m.end(), basis="fair value", pct=num(m.group(2))[0], lt=num(m.group(2))[1], pattern="I", asof=None))
    m = re.search(rf"non-?accrual investments as a percentage of total investments at both cost and fair value were\s+{NUM}", s, re.I)
    if m:
        out.append(dict(pos=m.start(), end=m.end(), basis="amortized cost", pct=num(m.group(1))[0], lt=num(m.group(1))[1], pattern="I2", asof=None)); out.append(dict(pos=m.start(), end=m.end(), basis="fair value", pct=num(m.group(1))[0], lt=num(m.group(1))[1], pattern="I2", asof=None))
    # E3: Oaktree "represented X % and Y % of total debt investments at cost and fair value, respectively"
    for m in re.finditer(rf"represented\s+{NUM}\s+and\s+{NUM}\s+of total debt investments at cost and fair value, respectively", s, re.I):
        out.append(dict(pos=m.start(), end=m.end(), basis="amortized cost", pct=num(m.group(1))[0], lt=num(m.group(1))[1], pattern="E3", asof=None)); out.append(dict(pos=m.start(), end=m.end(), basis="fair value", pct=num(m.group(2))[0], lt=num(m.group(2))[1], pattern="E3", asof=None))
    # K: HPS "which represented X % and Y % of total debt and income producing investments …, at fair value, respectively" (two dates)
    m = re.search(rf"on non-?accrual status, respectively, which represented\s+{NUM}\s+and\s+{NUM}\s+of total debt and income producing investments[^.]*?at fair value", s, re.I)
    if m and len(dates) >= 2:
        out.append(dict(pos=m.start(), end=m.end(), basis="fair value", pct=num(m.group(1))[0], lt=num(m.group(1))[1], pattern="K", asof=dates[0])); out.append(dict(pos=m.start(), end=m.end(), basis="fair value", pct=num(m.group(2))[0], lt=num(m.group(2))[1], pattern="K", asof=dates[1]))
    # J: Blue Owl count-only "As of <date>, two of our portfolio companies are on non-accrual" (optionally "… which represents X% of our portfolio at fair value" handled by D)
    m = re.search(r"as of ([A-Z][a-z]+ \d{1,2}, \d{4}), (?:only )?(\w+) of our portfolio companies (?:are|were|is|was) on non-?accrual", s, re.I)
    if m and not any(o["pattern"] == "D" for o in out):
        dm = DATE_RE.search(m.group(1)); out.append(dict(pos=m.start(), end=m.end(), basis="count only", pct=None, count_word=m.group(2), pattern="J", asof=to_iso(dm) if dm else None))
    # date binding, per matched clause: table rows (G, G2) take the first date in the fragment (the report-date column is listed first);
    # every other figure takes the nearest "as of <date>" that precedes its clause, failing that the nearest preceding date, failing that
    # the first date in the sentence (flagged "first-in-sentence" and not used for a report-date value)
    all_dates = [(mm.start(), mm.end(), to_iso(mm)) for mm in DATE_RE.finditer(s)]
    for o in out:
        if o["asof"] is not None:
            continue
        if o["pattern"] in ("G", "G2"):
            o["asof"] = dates[0] if dates else None; o["date_binding"] = "table-first-column"; continue
        pos = o.get("pos", 0); end = o.get("end", pos)
        after = re.match(r"\s*(?:status|loans?|investments?)?\s*,?\s*as\s+of\s+(" + MONTHS + r")\s+(\d{1,2}),\s+(\d{4})", s[end: end + 80], re.I)
        if after:
            o["asof"] = to_iso(after); o["date_binding"] = "as-of-following"; continue
        pre = [(st, en, d) for st, en, d in all_dates if en <= pos]
        pre_asof = [(st, en, d) for st, en, d in pre if re.search(r"as\s+of\s*$", s[max(0, st - 12): st], re.I)]
        if pre_asof:
            o["asof"] = pre_asof[-1][2]; o["date_binding"] = "as-of-preceding"
        elif pre:
            o["asof"] = pre[-1][2]; o["date_binding"] = "preceding"
        else:
            o["asof"] = dates[0] if dates else None; o["date_binding"] = "first-in-sentence"
    return out


def main():
    res = {"meta": {"source": "results/soi_cache/*.htm via soi_asset_side_v3.py", "patterns": "see docstring"}, "entities": {}}
    md = ["# Non-accrual statements parsed from the filings (evidence for Table: asset-side measures)", "",
          "One row per parsed statement. `asof` is the date the sentence attaches to the figure (first date in the sentence when the pattern does not bind dates). Human check: the figure must be the one the sentence attaches to the report date.", "",
          "| Entity | Report | Form | Pattern | Basis | % | As of | Sentence |", "|---|---|---|---|---|---|---|---|"]
    for f in RAW["filings"]:
        p = CACHE / f"{f['entity']}_{f['report']}_{f['accession']}.htm"
        if not p.exists():
            continue
        found = []
        for s in sentences(p.read_text(errors="ignore")):
            for o in parse(s):
                i = s.lower().find("accrual"); o["sentence"] = s[max(0, i - 320): i + 420]
                found.append(o)
        # de-duplicate identical (pattern, basis, pct, asof)
        uniq, seen = [], set()
        for o in found:
            k = (o["pattern"], o["basis"], o["pct"], o["asof"], o.get("lt", False))
            if k not in seen:
                seen.add(k); uniq.append(o)
        for o in uniq:
            o["accession"] = f["accession"]; o["form"] = f["form"]
        slot = res["entities"].setdefault(f["entity"], {}).setdefault(f["report"], dict(filings=[], statements=[]))
        slot["filings"].append(dict(form=f["form"], filed=f["filed"], accession=f["accession"]))
        seen_keys = {(o["pattern"], o["basis"], o["pct"], o["asof"]) for o in slot["statements"]}
        slot["statements"] += [o for o in uniq if (o["pattern"], o["basis"], o["pct"], o["asof"]) not in seen_keys]
        slot["form"] = slot["filings"][0]["form"]; slot["filed"] = slot["filings"][0]["filed"]; slot["accession"] = ", ".join(x["accession"] for x in slot["filings"])
        for o in uniq:
            md.append(f"| {f['entity']} | {f['report']} | {f['form']} {f['accession']} | {o['pattern']} | {o['basis']} | {o['pct'] if o['pct'] is not None else 'count: ' + str(o.get('count_word'))} | {o['asof']} | {o['sentence'].replace('|', '/')[:260]} |")
    # choose the report-date value per entity × report: fair value basis preferred; own filing first, then any later filing of the same
    # entity that restates the figure for that date (10-K comparatives), flagged from_other_filing
    for e, byrep in res["entities"].items():
        pool = [dict(o, from_other_filing=True) for rec0 in byrep.values() for o in rec0["statements"] if o["pct"] is not None]
        for rep, rec in byrep.items():
            own = [o for o in rec["statements"] if o["asof"] == rep and o.get("date_binding") != "first-in-sentence"]; other = [o for o in pool if o["asof"] == rep and o.get("date_binding") != "first-in-sentence"]
            fv = [o for o in own if o["basis"] == "fair value"] or [o for o in other if o["basis"] == "fair value"]
            if any(o.get("lt") for o in fv) and any(not o.get("lt") for o in fv):   # filing states both "less than 0.1%" and "0.1%": keep the bound, record the ambiguity
                fv = [o for o in fv if o.get("lt")]; rec["dual_formulation"] = True
            ac = [o for o in own if o["basis"] == "amortized cost"] or [o for o in other if o["basis"] == "amortized cost"]
            un = [o for o in own if o["basis"] == "unspecified"]; co = [o for o in own if o["basis"] == "count only"]
            pick = (fv or ac or un or co or [None])[0]
            rec["report_date_value"] = None if pick is None else dict(pct=pick["pct"], basis=pick["basis"], pattern=pick["pattern"], sentence=pick["sentence"], count_word=pick.get("count_word"), accession=pick.get("accession"), form=pick.get("form"), from_other_filing=bool(pick.get("from_other_filing")), lt=bool(pick.get("lt")))
    (R / "nonaccrual_v3.json").write_text(json.dumps(res, indent=1))
    (BASE / "paper" / "reviews" / "NONACCRUAL_EVIDENCE_v3.md").write_text("\n".join(md))
    # coverage report
    for e, byrep in sorted(res["entities"].items()):
        cov = {rep: ((rec["report_date_value"]["pct"] if rec["report_date_value"]["pct"] is not None else "n=" + str(rec["report_date_value"].get("count_word"))) if rec["report_date_value"] else None) for rep, rec in sorted(byrep.items())}
        print(e, {k: v for k, v in cov.items()})


if __name__ == "__main__":
    main()
