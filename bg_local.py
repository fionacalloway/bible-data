#!/usr/bin/env python3
"""Local query layer over /root/bible/bibles_bg/<VER>.jsonl that reproduces the
output contract of lexis-solutions/bible-gate-way-com-scraper:

  passage mode -> {"url", "search", "version", "passage"}
  keyword mode -> {"url", "search", "version", "totalResults",
                   "suggestedResult", "allSearchResults": [{"title","content"}]}

Local = instant + free (public-domain versions only: KJV ASV WEB YLT DARBY WYC DRA).
Unknown version -> falls back to biblegateway.py (online, still free).

Usage:
  bg_local.py --search "John 3:16" --version KJV
  bg_local.py --search "love" --version KJV [--limit 100] [--json out.json]
"""
import argparse, json, os, re, sys, urllib.parse

DATA_DIR = "/root/bible/bibles_bg"
LOCAL_VERSIONS = sorted(f[:-6] for f in os.listdir(DATA_DIR) if f.endswith(".jsonl"))


def load_version(version):
    """{book: {chapter: [(verse, text), ...]}} with canonical book order."""
    path = os.path.join(DATA_DIR, f"{version}.jsonl")
    if not os.path.exists(path):
        return None
    data, order = {}, []
    for line in open(path):
        r = json.loads(line)
        data.setdefault(r["book"], {})[r["chapter"]] = [(v["verse"], v["text"]) for v in r["verses"]]
        if r["book"] not in order:
            order.append(r["book"])
    return {"data": data, "order": order}


PASSAGE_RE = re.compile(
    r"^\s*((?:[1-3]\s+)?[A-Za-z][A-Za-z .'-]*?)\s+(\d+):(\d+)(?:\s*[-–]\s*(\d+)(?::(\d+))?)?\s*$")


def passage_local(db, search, version):
    m = PASSAGE_RE.match(search)
    if not m:
        return None
    book, ch, v1, v2, v3 = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4), m.group(5)
    # resolve book name case-insensitively + common aliases
    alias = {"psalms": "Psalm", "song of songs": "Song of Solomon", "canticles": "Song of Solomon",
             "1cor": "1 Corinthians", "gen": "Genesis", "rev": "Revelation", "mt": "Matthew",
             "mk": "Mark", "lk": "Luke", "jn": "John", "rom": "Romans"}
    want = book.lower()
    want = alias.get(want, want)
    bkey = next((b for b in db["order"] if b.lower() == want), None)
    if bkey is None:
        return None
    ch_data = dict(db["data"][bkey].get(ch, []))
    if not ch_data:
        return None
    v_end = int(v2) if v2 else v1
    if v2 and v3:  # range like 3:16-4:2 -> cross-chapter not supported; keep simple
        pass
    parts = []
    for n in range(v1, v_end + 1):
        t = ch_data.get(n)
        if t is None:
            continue
        parts.append(f"{n} {t}")
    if not parts:
        return None
    return {
        "url": f"https://www.biblegateway.com/passage/?search={urllib.parse.quote(search)}&version={urllib.parse.quote(version)}",
        "search": search, "version": version, "passage": " ".join(parts),
    }


def keyword_local(db, search, version, limit=100):
    # suffix-flexible word match (love/loved/loveth/lovest/loving), like BG quicksearch
    def tok_pat(t):
        if t.endswith("e"):  # 'love' -> stem 'lov' + (e|es|ed|eth|est|ing)
            return re.escape(t[:-1]) + r"(?:e|es|ed|eth|est|ing)?"
        return re.escape(t) + r"(?:es|ed|eth|est|ing)?"
    pat = re.compile(r"\b" + r"[\s]+".join(tok_pat(t) for t in search.split()) + r"\b", re.I)
    results, total = [], 0
    for book in db["order"]:
        for ch in sorted(db["data"][book]):
            for num, text in db["data"][book][ch]:
                if pat.search(text):
                    total += 1
                    if len(results) < limit:
                        results.append({
                            "title": f"{book} {ch}:{num}",
                            "content": text[:200] + ("..." if len(text) > 200 else ""),
                        })
    return {
        "url": f"https://www.biblegateway.com/quicksearch/?quicksearch={urllib.parse.quote(search)}&version={urllib.parse.quote(version)}",
        "search": search, "version": version,
        "totalResults": total,
        "suggestedResult": None,
        "allSearchResults": results,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", required=True)
    ap.add_argument("--version", default="KJV")
    ap.add_argument("--limit", type=int, default=100, help="max allSearchResults returned (totalResults always full)")
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args()

    db = load_version(args.version)
    if db is None:
        print(f"version '{args.version}' not stored locally. Local: {', '.join(LOCAL_VERSIONS)}",
              file=sys.stderr)
        print("fall back online: python3 /root/biblegateway/biblegateway.py "
              f"--search '{args.search}' --version {args.version}", file=sys.stderr)
        sys.exit(2)
    out = passage_local(db, args.search, args.version)
    if out is None:
        out = keyword_local(db, args.search, args.version, limit=args.limit)
    if args.json_out:
        json.dump(out, open(args.json_out, "w"), ensure_ascii=False, indent=2)
        print(f"written: {args.json_out}")
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
