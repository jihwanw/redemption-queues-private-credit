"""literature_coupling_audit.py — for every bibliography key, list each sentence in which it is cited, with its location (file, subsection, hypothesis block)
and the operative role of that sentence (premise / mechanism / boundary / rival / prediction / gap / mapping-table row / mirroring / policy / context / unperformed test).
A work whose only citations are 'context' is flagged NAMED-ONLY. Output: paper/reviews/THEORY_MAPPING_AUDIT.md."""
import re, sys
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent; TEX = BASE / "paper" / "tex_v3"
bibkeys = re.findall(r"^@\w+\{([^,]+),", (TEX / "refs.bib").read_text(), re.M)
files = ["sec1_intro.tex", "sec2_setting_theory.tex", "sec3_data.tex", "sec4_design.tex", "sec5_results.tex", "sec6_policy.tex", "appendix.tex"]
ROLE_WORDS = [("premise", r"\\emph\{Premise\}"), ("mechanism", r"\\emph\{Mechanism\}"), ("information", r"\\emph\{Information\}"), ("boundary", r"\\emph\{Boundary\}"), ("rival", r"\\emph\{Rival\}"), ("prediction", r"\\emph\{Prediction[^}]*\}"), ("use/what-it-yields", r"\\emph\{(Use|What the decomposition yields|What it cannot do)\}")]
def role_of(sentence, para, file, sub):
    s = sentence.lower()
    if file == "sec4_design.tex" and re.search(r"bootstrap|cluster|standard error", s): return "method"
    if file == "sec6_policy.tex": return "policy"
    if re.search(r"\b(h1|h2|h3|h4)\b", s) and re.search(r"premise|boundary|rival|margin|is why|which is why|turns on|predicts", s): return "premise/boundary/rival (hypothesis-linked)"
    if sub.lower().startswith("hypotheses"):   # prose hypotheses (2026-10-22): role from the sentence's own words
        if re.search(r"rival|same (common )?(increase|fall|observation)|looks the same|produces the same|unrelated to|without any role", s): return "rival"
        if re.search(r"fails where|holds only|requires that|lie outside|boundary|cannot credibly|does not lag|as likely within", s): return "boundary"
        if re.search(r"we expect|prediction|predicts|rise more|to rise|to adjust", s): return "prediction"
        if re.search(r"raises|lowers|falls only|signal|mechanism|margin|supplies the margins|adds the two", s): return "mechanism"
        return "premise"
    if "mirror" in sub.lower() or "antecedent" in sub.lower(): return "mirroring"
    if "\\begin{longtable}" in para or para.strip().startswith("\\citet") and "&" in para: return "mapping-table row"
    if re.search(r"do not perform|not performed|cannot perform|we name and do not|not available as a test|unperformed|cannot be performed", s): return "unperformed test (named)"
    if "gap" in sub.lower() and re.search(r"first,|second,|third,|gap|the first is|the second is|the third is|has not been studied|not been set against|studies restrictions|observes it where", s): return "gap statement"
    # within a hypothesis paragraph: find the last role label before the sentence
    last = None
    for name, pat in ROLE_WORDS:
        for m in re.finditer(pat, para):
            if m.start() <= para.find(sentence): last = name
    if last: return last
    if re.search(r"premise|is why|which is why|reason|because|so that|requires|assum", s): return "premise/derivation sentence"
    return "context"
rows = []
for f in files:
    txt = (TEX / f).read_text(); sub = ""
    paras = re.split(r"\n\s*\n", txt)
    for para in paras:
        m = re.search(r"\\(sub)?section\*?\{([^}]*)\}", para)
        if m: sub = m.group(2)
        hyp = re.search(r"\\paragraph\{(H\d)", para); hyp = hyp.group(1) if hyp else ""
        sents = re.split(r"(?<=[.;])\s+(?=[A-Z\\])", para)
        for si, sent in enumerate(sents):
            for key in set(re.findall(r"\\cite[tp]?\{([^}]*)\}", sent)):
                for k in [x.strip() for x in key.split(",")]:
                    if k in bibkeys:
                        role = role_of(sent, para, f, sub)
                        if role == "context" and si + 1 < len(sents): role = role_of(sent + " " + sents[si + 1], para, f, sub)   # a coupling statement may follow the citing sentence
                        rows.append((k, f, sub[:40], hyp, role, re.sub(r"\s+", " ", sent)[:230]))
out = ["# Literature coupling audit — every citation, its location and operative role\n", f"Source: `code/literature_coupling_audit.py` over `paper/tex_v3/*.tex`; {len(rows)} citation instances of {len(bibkeys)} works.\n"]
named_only = []
for k in bibkeys:
    rs = [r for r in rows if r[0] == k]
    roles = sorted({r[4] for r in rs})
    flag = "" if any(r not in ("context",) for r in roles) else "  **NAMED-ONLY**"
    if flag: named_only.append(k)
    out.append(f"\n## {k} — {len(rs)} citation(s); roles: {', '.join(roles) or 'none'}{flag}\n")
    for r in rs: out.append(f"- [{r[1]} | {r[2]}{' | ' + r[3] if r[3] else ''} | **{r[4]}**] {r[5]}")
out.insert(2, f"\nWorks cited only as context (no operative role): {named_only or 'none'}\n")
(BASE / "paper" / "reviews" / "THEORY_MAPPING_AUDIT.md").write_text("\n".join(out))
print("works:", len(bibkeys), "| citation instances:", len(rows), "| named-only:", named_only)
for k in bibkeys: print(f"  {k:24} {sorted({r[4] for r in rows if r[0] == k})}")
