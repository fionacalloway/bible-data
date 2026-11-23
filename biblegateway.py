#!/usr/bin/env python3
"""BibleGateway.com scraper — free local mirror of lexis-solutions/bible-gate-way-com-scraper.
Input/output mimics the Actor's documented contract:
  passage mode -> {"url", "search", "version", "passage"}
  keyword mode -> {"url", "search", "version", "totalResults", "suggestedResult",
                   "allSearchResults": [{"title", "content"}, ...]}

Usage:
  biblegateway.py --search "John 3:16" --version NIV [--json out.json]
  biblegateway.py --search "love" --version KJV [--pages 1] [--json out.json]
  biblegateway.py --multi "John 3:16=KJV,NIV,ESV"    # bonus: many versions in one run
"""
import argparse, html as htmllib, json, os, re, sys, time
import urllib.parse, urllib.request, ssl

BASE = "https://www.biblegateway.com"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# book names (incl. numbered books) for passage detection
PASSAGE_RE = re.compile(
    r"^\s*(?:[1-3]\s+)?[A-Za-z][A-Za-z .'-]*\s+\d+:\d+(?:\s*[-–]\s*\d+:\d+|\s*[-–]\s*\d+)?"
    r"(?:\s*,\s*\d+:\d+(?:\s*[-–]\s*\d+)?)*\s*$")


def fetch(url, retries=3):
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45, context=CTX) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception:
            if a == retries - 1:
                raise
            time.sleep(2 * (a + 1))


def clean(html):
    html = re.sub(r"</?b>", "", html)  # keyword highlighting: keep 'lovest' glued
    # drop cross-reference / footnote superscripts, KEEP verse numbers
    html = re.sub(r'<sup\b(?![^>]*class="versenum")[^>]*>.*?</sup>', " ", html, flags=re.S | re.I)
    html = re.sub(r'<sup class="versenum">\s*', ' ', html, flags=re.I)
    html = re.sub(r"</sup>", " ", html, flags=re.I)
    txt = re.sub(r"<[^>]+>", " ", html)
    txt = htmllib.unescape(txt)
    txt = re.sub(r"\(\s+", "(", txt)
    return re.sub(r"\s+", " ", txt).strip()


def scrape_passage(search, version):
    q = urllib.parse.urlencode({"search": search, "version": version, "interface": "url"})
    url = f"{BASE}/passage/?{q}"
    page = fetch(url)
    i = page.find('<div class="passage-text"')
    if i < 0:
        return {"url": url, "search": search, "version": version, "passage": None,
                "error": "passage not found (check reference/version)"}
    seg = page[i:]
    # stop at end-of-content markers inside the passage column
    for marker in ("Read full chapter", '<div class="crossreferences', '<div class="footnotes',
                   'passage-other-trans', "Footer"):
        j = seg.find(marker)
        if j > 0:
            seg = seg[:j]
    # keep verse numbers: they appear as inline text or spans already handled
    passage = clean(seg)
    passage = re.sub(r"\s*Next\s*\(?\w*\)?\s*$", "", passage).strip()
    return {"url": url.replace("&interface=url", ""), "search": search, "version": version,
            "passage": passage or None}


def scrape_keyword(search, version, pages=1):
    items, total, suggested = [], None, None
    for page_no in range(1, pages + 1):
        q = urllib.parse.urlencode({"quicksearch": search, "version": version,
                                    "interface": "url", "page": page_no})
        url = f"{BASE}/quicksearch/?{q}"
        page = fetch(url)
        if total is None:
            m = re.search(r"([\d,]+)\s+Bible results for", page)
            total = int(m.group(1).replace(",", "")) if m else None
        ms = re.search(r"[Dd]id you mean[^<]*", page)
        if ms:
            suggested = clean(ms.group(0))
        rows = re.findall(
            r'<li class="row bible-item"[^>]*>.*?<a class="bible-item-title"[^>]*>(.*?)</a>'
            r'.*?<div class="bible-item-text[^"]*">\s*(.*?)<div class="bible-item-extras">',
            page, flags=re.S)
        if not rows:
            break
        for title, content in rows:
            items.append({"title": clean(title), "content": clean(content)})
        time.sleep(1.0)  # polite rate limit
    return {"url": f"{BASE}/quicksearch/?quicksearch={urllib.parse.quote(search)}&version={urllib.parse.quote(version)}",
            "search": search, "version": version,
            "totalResults": total,
            "suggestedResult": suggested,
            "allSearchResults": items}


VERSIONS_EN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "versions_en.json")


def scrape_all_versions(search, versions=None, delay=0.7):
    """Passage across many versions; default = all English versions from versions_en.json."""
    if versions is None:
        versions = [v["code"] for v in json.load(open(VERSIONS_EN))]
    out = []
    for i, v in enumerate(versions):
        r = scrape_passage(search, v)
        out.append(r)
        print(f"[{i+1}/{len(versions)}] {v}: {'ok' if r.get('passage') else 'EMPTY'}", flush=True)
        if i < len(versions) - 1:
            time.sleep(delay)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", required=True)
    ap.add_argument("--version", default="KJV")
    ap.add_argument("--pages", type=int, default=1, help="result pages for keyword search (20/page)")
    ap.add_argument("--multi", action="store_true",
                    help="treat --version as comma-separated list; run passage for each")
    ap.add_argument("--all-versions", action="store_true",
                    help="passage across all English versions (~49); output = JSON list")
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args()

    if args.all_versions:
        out = scrape_all_versions(args.search)
    elif args.multi:
        res = []
        for v in [v.strip() for v in args.version.split(",") if v.strip()]:
            res.append(scrape_passage(args.search, v))
            time.sleep(1.0)
        out = res
    elif PASSAGE_RE.match(args.search):
        out = scrape_passage(args.search, args.version)
    else:
        out = scrape_keyword(args.search, args.version, pages=args.pages)

    js = args.json_out
    if js:
        json.dump(out, open(js, "w"), ensure_ascii=False, indent=2)
        print(f"written: {js}")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
