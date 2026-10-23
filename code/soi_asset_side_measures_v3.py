"""soi_asset_side_measures_v3.py — Stage 2: pair-level asset-side measures from the raw SOI extracts (results/soi_raw_v3.json).

For each (non-traded fund, listed twin) pair and each quarter-end both filed:
  overlap   share of each sibling's debt fair value held in issuers that also appear in the other sibling's schedule;
  marks     for tranches held by both (same normalized issuer, same spread and interest rate when both tag them), the mark
            fair value / principal of each sibling; signed difference (non-traded minus listed) in basis points of par; summary
            statistics weighted by the non-traded fund's fair value; share of common tranches within 10 and 50 bp;
  issuer    the same comparison aggregated to the issuer (sum of fair value / sum of principal over the issuer's debt lines).
Debt lines = lines with a positive tagged principal (InvestmentOwnedBalancePrincipalAmount); equity lines have no principal and are
excluded from marks but counted in totals.

Identifier normalization: the typed member reads "<Issuer name> <n> | <Affiliation>" (Blackstone) or a filer-specific variant; the
issuer key strips the trailing line index and affiliation, lower-cases, removes punctuation and corporate suffixes
(inc, llc, l.l.c., corp, corporation, ltd, limited, lp, l.p., co, holdings? — 'holdings' is KEPT because it distinguishes entities).
Run with --inspect to print identifier samples per entity before trusting the normalization.

Output: results/soi_asset_side_v3.json (every summary carries the accession numbers of the two filings it was computed from and the
number of lines/tranches). Nothing here is typed by hand.
"""
from __future__ import annotations
import json, re, sys
from collections import defaultdict
from pathlib import Path
import numpy as np

BASE = Path(__file__).resolve().parent.parent
R = BASE / "results"
RAW = json.loads((R / "soi_raw_v3.json").read_text())
PAIRS = {"BCRED": "BXSL", "OCIC": "OBDC", "OTIC": "OBDC", "ASIF": "ARCC", "GCRED": "GBDC", "OSCF": "OCSL", "ADS": "MFIC", "PCAP": "NCDL"}
SUFFIX = re.compile(r"\b(inc|incorporated|llc|l\.l\.c|corp|corporation|ltd|limited|lp|l\.p|plc|co|company|sarl|s\.a\.r\.l|bv|b\.v|gmbh|pty|sa|s\.a|ag|nv|n\.v)\b\.?")


TRANCHE_WORDS = r"(first[- ]lien|second[- ]lien|senior secured|one stop|subordinated|unsecured|mezzanine|preferred|common|warrants?|equity|revolv\w*|term loan|delayed draw|fixed rate bond|bonds?|notes?|units?|membership|llc interest|class [a-z]|investment type|multi-sector holdings)"
CUT_RE = re.compile(r",?\s+" + TRANCHE_WORDS + r"\b", re.I)
TYPE_RE = re.compile(r"(delayed draw|revolv\w*|second[- ]lien|first[- ]lien|one stop|senior secured|subordinated|unsecured|mezzanine|bond|note|term loan)", re.I)
SENIORITY_RE = re.compile(r"(second[- ]lien|first[- ]lien|one stop|last[- ]out|first[- ]out|unitranche|senior secured|subordinated|mezzanine|unsecured|preferred|bonds?|notes?)", re.I)
FACILITY_RE = re.compile(r"\b(delayed[- ]draw|revolv\w*|term loan|bridge loan|letter of credit)\b", re.I)
CURRENCY_RE = re.compile(r"\b(EUR|GBP|CAD|AUD|CHF|DKK|SEK|NOK|NZD|JPY|SGD|HKD)\b|[€£]", re.I)


def split_identifier(identifier: str):
    """Return (issuer text, tranche text). Formats seen (2026-10-21): 'Issuer N | Affiliation' (Blackstone), 'Issuer | tranche | affiliation'
    (Blue Owl 2025+, Golub, Nuveen, Ares), 'Issuer, tranche' (Blue Owl and Golub in 2024-2025 filings), 'Issuer | Sector | tranche' (Oaktree),
    '<Sector> <Short> <Legal> [Investment Type] <tranche> … Maturity Date …' (Apollo ADS/MFIC)."""
    if "|" in identifier:
        parts = [x.strip() for x in identifier.split("|")]
        return parts[0], " ".join(parts[1:])
    m = CUT_RE.search(identifier)
    if m:
        return identifier[: m.start()].strip(" ,"), identifier[m.start():].strip(" ,")
    return identifier.strip(), ""


def issuer_key(identifier: str) -> str:
    s, _ = split_identifier(identifier)
    s = re.sub(r"\s+\d+\s*$", "", s.strip())            # trailing line index "… 1"
    s = s.lower()
    s = re.sub(r"[’'`\"]", "", s)
    s = re.sub(r"\((?:f/?k/?a|fka|dba|d/b/a)[^)]*\)", " ", s)   # drop former-name / dba parentheticals
    s = re.sub(r"[^a-z0-9& ]+", " ", s)
    s = SUFFIX.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def tranche_type(identifier: str) -> str | None:
    """Kept for the appendix table labels: first descriptor found."""
    _, t = split_identifier(identifier)
    m = TYPE_RE.search(t) or TYPE_RE.search(identifier)
    return m.group(1).lower().replace("-", " ") if m else None


def seniority(identifier: str) -> str | None:
    _, t = split_identifier(identifier)
    m = SENIORITY_RE.search(t) if t else None
    return m.group(1).lower().replace("-", " ") if m else None


def facility_class(identifier: str) -> str | None:
    """revolver / delayed draw / term loan …, read from the tranche segment of the identifier only (never from the issuer name),
    independently of lien seniority ('First lien senior secured revolving loan' -> revolver). Identifiers without a tranche segment
    (Blackstone: issuer + line index) return None."""
    _, t = split_identifier(identifier)
    m = FACILITY_RE.search(t) if t else None
    if not m:
        return None
    w = m.group(1).lower().replace("-", " ")
    return "revolver" if w.startswith("revolv") else w


def currency_tag(identifier: str) -> str | None:
    m = CURRENCY_RE.search(identifier)
    return (m.group(0).upper() if m else None)


def lines_for(filing: dict):
    """One record per investment context: issuer key, identifier, fv, cost, principal, rate, spread."""
    by_ctx = defaultdict(dict); units = defaultdict(dict)
    for f in filing["facts"]:
        by_ctx[f["ctx"]][f["name"].split(":")[1]] = f["val"]; units[f["ctx"]][f["name"].split(":")[1]] = (f.get("unit") or "").lower()
    out = []
    for cid, c in filing["contexts"].items():
        if c["instant"] != filing["report"]:
            continue  # prior-period comparative columns are tagged with earlier instants
        v = by_ctx.get(cid, {})
        if "InvestmentOwnedAtFairValue" not in v:
            continue
        out.append(dict(ctx=cid, identifier=c["identifier"], issuer=issuer_key(c["identifier"]), fv=v.get("InvestmentOwnedAtFairValue"),
                        cost=v.get("InvestmentOwnedAtCost"), principal=v.get("InvestmentOwnedBalancePrincipalAmount"),
                        rate=v.get("InvestmentInterestRate"), spread=v.get("InvestmentBasisSpreadVariableRate"), dims=c.get("dims", {}),
                        principal_unit=units[cid].get("InvestmentOwnedBalancePrincipalAmount"), fv_unit=units[cid].get("InvestmentOwnedAtFairValue")))
    return out


def latest_original(entity: str):
    """report date -> filing with SOI facts. Prefer the original 10-Q/10-K (latest filed); use an amendment only when no original has facts."""
    out = {}
    for f in RAW["filings"]:
        if f["entity"] != entity or f["n_facts"] == 0:
            continue
        cur = out.get(f["report"]); amend = f["form"].endswith("/A")
        if cur is None:
            out[f["report"]] = f
        elif cur["form"].endswith("/A") and not amend:
            out[f["report"]] = f
        elif cur["form"].endswith("/A") == amend and f["filed"] > cur["filed"]:
            out[f["report"]] = f
    return out


def tranche_key(l):
    r = None if l["rate"] is None else round(float(l["rate"]), 4)
    s = None if l["spread"] is None else round(float(l["spread"]), 4)
    return (l["issuer"], s, r, seniority(l["identifier"]), facility_class(l["identifier"]))


def wmean(x, w):
    x, w = np.asarray(x, float), np.asarray(w, float)
    return float((x * w).sum() / w.sum()) if w.sum() > 0 else None


def compare(fund_lines, twin_lines):
    def is_debt(l):  # funded debt line: positive principal, positive fair value and (when tagged) positive cost; excludes unfunded commitments and equity
        return bool(l["principal"]) and l["principal"] > 0 and l["fv"] is not None and l["fv"] > 0 and (l["cost"] is None or l["cost"] > 0)
    debt_f = [l for l in fund_lines if is_debt(l)]
    debt_t = [l for l in twin_lines if is_debt(l)]
    fv_f_all = sum(l["fv"] for l in fund_lines if l["fv"]); fv_t_all = sum(l["fv"] for l in twin_lines if l["fv"])
    fv_f = sum(l["fv"] for l in debt_f); fv_t = sum(l["fv"] for l in debt_t)
    iss_f = {l["issuer"] for l in debt_f}; iss_t = {l["issuer"] for l in debt_t}
    common = iss_f & iss_t
    ov_f = sum(l["fv"] for l in debt_f if l["issuer"] in common) / fv_f if fv_f else None
    ov_t = sum(l["fv"] for l in debt_t if l["issuer"] in common) / fv_t if fv_t else None
    # tranche-level marks
    def usd(l):  # principal AND fair value positively resolved to iso4217:USD from the filing's unit definitions, and no foreign-currency token in the identifier
        pu = l.get("principal_unit") or ""; fu = l.get("fv_unit") or ""
        return pu.endswith("iso4217:usd") and fu.endswith("iso4217:usd") and currency_tag(l["identifier"]) is None
    def unit_unresolved(l):
        pu = l.get("principal_unit") or ""; fu = l.get("fv_unit") or ""
        return not pu.startswith("iso4217:") or not fu.startswith("iso4217:")
    mk_f = [l for l in debt_f if usd(l)]; mk_t = [l for l in debt_t if usd(l)]
    fv_nonusd_share_fund = 1 - sum(l["fv"] for l in mk_f) / fv_f if fv_f else None
    n_unit_unresolved_fund = sum(1 for l in debt_f if unit_unresolved(l)); n_unit_unresolved_twin = sum(1 for l in debt_t if unit_unresolved(l))
    n_currency_tagged_fund = sum(1 for l in debt_f if currency_tag(l["identifier"]) is not None)
    tf = defaultdict(list); tt = defaultdict(list)
    for l in mk_f: tf[tranche_key(l)].append(l)
    for l in mk_t: tt[tranche_key(l)].append(l)
    rows = []
    for k in set(tf) & set(tt):
        if k[1] is None and k[2] is None:
            continue  # need at least one pricing term (spread or rate) to pin the tranche

        a, b = tf[k], tt[k]
        mf = sum(x["fv"] for x in a) / sum(x["principal"] for x in a); mt = sum(x["fv"] for x in b) / sum(x["principal"] for x in b)
        rows.append(dict(issuer=k[0], issuer_label=split_identifier(a[0]["identifier"])[0], spread=k[1], rate=k[2], seniority=k[3], facility=k[4], n_lines_fund=len(a), n_lines_twin=len(b), mark_fund=mf, mark_twin=mt, diff_bp=(mf - mt) * 1e4, fv_fund=sum(x["fv"] for x in a), fv_twin=sum(x["fv"] for x in b),
                         ids_fund=[x["identifier"] for x in a], ids_twin=[x["identifier"] for x in b]))
    n_raw = len(rows)
    rows = [r for r in rows if 0.02 <= r["mark_fund"] <= 1.5 and 0.02 <= r["mark_twin"] <= 1.5]   # excludes lines whose principal and fair value were tagged on different scales
    n_excluded_scale = n_raw - len(rows)
    diffs = np.array([r["diff_bp"] for r in rows]) if rows else np.array([])
    w = np.array([r["fv_fund"] for r in rows]) if rows else np.array([])
    # robustness: funded term debt only (drop revolvers and delayed-draw tranches, whose principal includes undrawn commitments)
    term = [r for r in rows if r.get("facility") not in ("revolver", "delayed draw")]
    n_term_unknown_facility = sum(1 for r in term if r.get("facility") is None)
    tdiffs = np.array([r["diff_bp"] for r in term]) if term else np.array([]); tw = np.array([r["fv_fund"] for r in term]) if term else np.array([])
    # issuer-level marks
    af = defaultdict(lambda: [0.0, 0.0]); at = defaultdict(lambda: [0.0, 0.0])
    for l in mk_f: af[l["issuer"]][0] += l["fv"]; af[l["issuer"]][1] += l["principal"]
    for l in mk_t: at[l["issuer"]][0] += l["fv"]; at[l["issuer"]][1] += l["principal"]
    irows = [dict(issuer=i, mark_fund=af[i][0] / af[i][1], mark_twin=at[i][0] / at[i][1], diff_bp=(af[i][0] / af[i][1] - at[i][0] / at[i][1]) * 1e4, fv_fund=af[i][0]) for i in common if af[i][1] > 0 and at[i][1] > 0]
    irows = [r for r in irows if 0.02 <= r["mark_fund"] <= 1.5 and 0.02 <= r["mark_twin"] <= 1.5]
    idiffs = np.array([r["diff_bp"] for r in irows]) if irows else np.array([])
    iw = np.array([r["fv_fund"] for r in irows]) if irows else np.array([])
    return dict(
        n_lines_fund=len(fund_lines), n_lines_twin=len(twin_lines), n_debt_fund=len(debt_f), n_debt_twin=len(debt_t),
        fv_total_fund=fv_f_all, fv_total_twin=fv_t_all, fv_debt_fund=fv_f, fv_debt_twin=fv_t,
        n_issuers_fund=len(iss_f), n_issuers_twin=len(iss_t), n_common_issuers=len(common),
        overlap_fv_share_fund=ov_f, overlap_fv_share_twin=ov_t, fv_nonusd_share_fund=fv_nonusd_share_fund,
        n_unit_unresolved_fund=n_unit_unresolved_fund, n_unit_unresolved_twin=n_unit_unresolved_twin, n_currency_tagged_fund=n_currency_tagged_fund,
        n_matched_groups_multi_line=sum(1 for r in rows if r["n_lines_fund"] > 1 or r["n_lines_twin"] > 1),
        tranches=dict(n=len(rows), n_excluded_implausible=n_excluded_scale, fv_share_fund=(w.sum() / fv_f) if fv_f and len(w) else None,
                      mean_diff_bp=float(diffs.mean()) if len(diffs) else None, wmean_diff_bp=wmean(diffs, w) if len(diffs) else None,
                      median_diff_bp=float(np.median(diffs)) if len(diffs) else None, mean_abs_diff_bp=float(np.abs(diffs).mean()) if len(diffs) else None,
                      share_within_10bp=float((np.abs(diffs) <= 10).mean()) if len(diffs) else None, share_within_50bp=float((np.abs(diffs) <= 50).mean()) if len(diffs) else None,
                      share_within_10bp_fvw=wmean((np.abs(diffs) <= 10).astype(float), w) if len(diffs) else None,
                      p10_diff_bp=float(np.percentile(diffs, 10)) if len(diffs) else None, p90_diff_bp=float(np.percentile(diffs, 90)) if len(diffs) else None,
                      max_abs_diff_bp=float(np.abs(diffs).max()) if len(diffs) else None,
                      mark_fund_fvw=wmean([r["mark_fund"] for r in rows], w) if len(rows) else None, mark_twin_fvw=wmean([r["mark_twin"] for r in rows], w) if len(rows) else None),
        tranches_term_only=dict(n=len(term), n_unknown_facility=n_term_unknown_facility, wmean_diff_bp=wmean(tdiffs, tw) if len(tdiffs) else None, median_diff_bp=float(np.median(tdiffs)) if len(tdiffs) else None,
                                share_within_10bp=float((np.abs(tdiffs) <= 10).mean()) if len(tdiffs) else None, share_within_10bp_fvw=wmean((np.abs(tdiffs) <= 10).astype(float), tw) if len(tdiffs) else None,
                                share_within_50bp=float((np.abs(tdiffs) <= 50).mean()) if len(tdiffs) else None),
        issuers=dict(n=len(irows), mean_diff_bp=float(idiffs.mean()) if len(idiffs) else None, wmean_diff_bp=wmean(idiffs, iw) if len(idiffs) else None,
                     median_diff_bp=float(np.median(idiffs)) if len(idiffs) else None, share_within_10bp=float((np.abs(idiffs) <= 10).mean()) if len(idiffs) else None,
                     share_within_50bp=float((np.abs(idiffs) <= 50).mean()) if len(idiffs) else None),
        largest_abs_diffs=sorted(rows, key=lambda r: -abs(r["diff_bp"]))[:8],
    )


def inspect():
    for e in sorted({f["entity"] for f in RAW["filings"]}):
        fl = latest_original(e)
        if not fl:
            print(e, "no SOI facts"); continue
        rep = max(fl); L = lines_for(fl[rep])
        nd = sum(1 for l in L if l["principal"] and l["principal"] > 0)
        nr = sum(1 for l in L if l["rate"] is not None); ns = sum(1 for l in L if l["spread"] is not None)
        print(f"{e} {rep} {fl[rep]['form']} lines={len(L)} debt={nd} with_rate={nr} with_spread={ns}")
        for l in L[:4]:
            print("   ", repr(l["identifier"])[:90], "->", l["issuer"], "| fv", l["fv"], "prin", l["principal"], "rate", l["rate"], "spr", l["spread"], "dims", list(l["dims"].values())[:2])


def main():
    out = {"meta": {"source": "results/soi_raw_v3.json", "collected": RAW["meta"].get("collected"), "pairs": PAIRS}, "pairs": {}}
    for fund, twin in PAIRS.items():
        ff, tf = latest_original(fund), latest_original(twin)
        dates = sorted(set(ff) & set(tf))
        out["pairs"][f"{fund}-{twin}"] = {}
        for d in dates:
            res = compare(lines_for(ff[d]), lines_for(tf[d]))
            res["fund_filing"] = dict(form=ff[d]["form"], filed=ff[d]["filed"], accession=ff[d]["accession"])
            res["twin_filing"] = dict(form=tf[d]["form"], filed=tf[d]["filed"], accession=tf[d]["accession"])
            out["pairs"][f"{fund}-{twin}"][d] = res
            t = res["tranches"]
            print(f"{fund}-{twin} {d}: common issuers {res['n_common_issuers']} ({res['n_issuers_fund']}/{res['n_issuers_twin']}); overlap FV share fund {res['overlap_fv_share_fund']:.2f} twin {res['overlap_fv_share_twin']:.2f}; "
                  f"tranches {t['n']} covering {100*(t['fv_share_fund'] or 0):.0f}% of fund debt FV; wmean diff {t['wmean_diff_bp']} bp; within 10bp {t['share_within_10bp']}")
    (R / "soi_asset_side_v3.json").write_text(json.dumps(out, indent=1, default=float))
    print("saved", R / "soi_asset_side_v3.json")


if __name__ == "__main__":
    inspect() if "--inspect" in sys.argv else main()
