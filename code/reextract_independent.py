"""reextract_independent.py — second, independent extraction of tender-offer results from the cached filing documents.
Strategy differs from m2_main_v2.py on purpose: (1) HTML -> text with table cells separated; (2) sentence segmentation; (3) a sentence is a
'tendered' statement if it contains tendered|repurchase requests|requests for repurchase and at least one share count >= 10,000; class-level
counts in the same sentence are summed; (4) an 'accepted' statement must contain accepted for purchase|purchased|repurchased|accepted ... shares,
and sentences that are footnotes ('This amount includes', 'repurchased at a price', '1 This') or that refer to a prior offer ('expired on') are
excluded; (5) percent-of-outstanding statements captured separately; (6) every extracted number is stored with its sentence (evidence)."""
import json, re, html
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent; CACHE = BASE / "results" / "filings_cache"
def to_text(h):
    h = re.sub(r"(?is)<(script|style).*?</\1>", " ", h); h = re.sub(r"(?i)</(td|th|p|div|br|li|tr)>", " \n ", h); h = re.sub(r"<[^>]+>", " ", h)
    t = html.unescape(h); t = t.replace("\xa0", " "); return re.sub(r"[ \t]+", " ", t)
NUM = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d{5,})(?![\d,])")
PCT = re.compile(r"(\d{1,2}(?:\.\d+)?)\s*%")
def sentences(t):
    t = re.sub(r"\s*\n\s*", " ", t); return [s.strip() for s in re.split(r"(?<=[.;])\s+(?=[A-Z(\u201c\"])", t) if s.strip()]
FOOT = re.compile(r"this amount includes|repurchased at a price|^\W*\d\s+this|expired on [A-Z][a-z]+ \d|prior tender offer|previous tender offer", re.I)
TEND = re.compile(r"(validly|properly)\s+tendered|were\s+tendered|tendered\s+and\s+not\s+withdrawn|repurchase\s+requests?\s+(for|totaling|of|representing)|requests?\s+(for|to)\s+(the\s+)?repurchase|shares\s+(were\s+)?submitted\s+for\s+repurchase", re.I)
ACC = re.compile(r"accepted\s+for\s+(purchase|repurchase|payment)|(has|have)\s+(purchased|repurchased|accepted)|(purchased|repurchased)\s+(an\s+aggregate\s+of\s+)?[\d,]+\s+(class\s+\w+\s+)?shares|will\s+(purchase|repurchase)\s+[\d,]+", re.I)
def extract(folder):
    out = {"folder": folder.name, "tendered": [], "accepted": [], "pct_requested": [], "pct_fulfilled": [], "prorated_lang": False, "upsized_lang": False, "full_fulfillment_lang": False}
    for f in sorted(folder.glob("*.html")):
        t = to_text(f.read_text(errors="ignore")); low = t.lower()
        if re.search(r"pro\s*rata|prorat", low): out["prorated_lang"] = True
        if re.search(r"increase[sd]?\s+the\s+(aggregate\s+)?(amount|number|size)|upsiz|amended\s+to\s+increase|elected\s+to\s+(increase|purchase\s+additional)", low): out["upsized_lang"] = True
        if re.search(r"(fulfill|satisf|honor)\w*\s+(100%|all)\s+(of\s+)?(the\s+)?(repurchase\s+)?requests|all\s+(validly\s+)?tendered\s+shares\s+(were|will\s+be)\s+(accepted|purchased|repurchased)|accepted\s+all\s+(of\s+the\s+)?shares", low): out["full_fulfillment_lang"] = True
        for s in sentences(t):
            if len(s) > 1200: continue
            nums = [int(n.replace(",", "")) for n in NUM.findall(s)]; big = [n for n in nums if n >= 10000]
            if FOOT.search(s): continue
            if TEND.search(s) and big: out["tendered"].append({"n": big, "sum": sum(big), "s": s[:400], "doc": f.name})
            if ACC.search(s) and big and not TEND.search(s): out["accepted"].append({"n": big, "sum": sum(big), "s": s[:400], "doc": f.name})
            for m in PCT.finditer(s):
                v = float(m.group(1)); ctx = s[max(0, m.start() - 160): m.end() + 60].lower()
                if re.search(r"request|tender", ctx) and re.search(r"outstanding|net asset|nav", ctx): out["pct_requested"].append({"v": v, "s": s[:300]})
                if re.search(r"(repurchas|purchas|accept)\w*", ctx) and re.search(r"outstanding|net asset|nav|aggregate", ctx) and not re.search(r"request", ctx): out["pct_fulfilled"].append({"v": v, "s": s[:300]})
    return out
if __name__ == "__main__":
    res = {}
    for d in sorted(CACHE.iterdir()):
        if d.is_dir() and list(d.glob("*.html")): res[d.name] = extract(d)
    json.dump(res, open(BASE / "results" / "reextract_independent.json", "w"), indent=1)
    print("extracted", len(res), "filings")
