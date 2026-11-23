#!/usr/bin/env python3
"""Download complete Bibles (public-domain English versions) by scraping
BibleGateway passage pages, one chapter per request.
Output: /root/bible/bibles_bg/<VERSION>.jsonl — one line per chapter:
  {"version","book","chapter","verses":[{"verse","text"}]}
Checkpoint-safe: skips chapters already present.
"""
import html as H
import json, os, re, ssl, threading, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

OUT_DIR = "/root/bible/bibles_bg"
VERSIONS = ["KJV", "ASV", "WEB", "YLT", "DARBY", "WYC", "DRA"]
DELAY = 0.7          # per worker between requests
WORKERS = 3

# (name for BibleGateway URL, chapters) — protestant canon, 66 books
BOOKS = [
    ("Genesis", 50), ("Exodus", 40), ("Leviticus", 27), ("Numbers", 36), ("Deuteronomy", 34),
    ("Joshua", 24), ("Judges", 21), ("Ruth", 4), ("1 Samuel", 31), ("2 Samuel", 24),
    ("1 Kings", 22), ("2 Kings", 25), ("1 Chronicles", 29), ("2 Chronicles", 36), ("Ezra", 10),
    ("Nehemiah", 13), ("Esther", 10), ("Job", 42), ("Psalm", 150), ("Proverbs", 31),
    ("Ecclesiastes", 12), ("Song of Solomon", 8), ("Isaiah", 66), ("Jeremiah", 52),
    ("Lamentations", 5), ("Ezekiel", 48), ("Daniel", 12), ("Hosea", 14), ("Joel", 3),
    ("Amos", 9), ("Obadiah", 1), ("Jonah", 4), ("Micah", 7), ("Nahum", 3), ("Habakkuk", 3),
    ("Zephaniah", 3), ("Haggai", 2), ("Zechariah", 14), ("Malachi", 4),
    ("Matthew", 28), ("Mark", 16), ("Luke", 24), ("John", 21), ("Acts", 28),
    ("Romans", 16), ("1 Corinthians", 16), ("2 Corinthians", 13), ("Galatians", 6),
    ("Ephesians", 6), ("Philippians", 4), ("Colossians", 4), ("1 Thessalonians", 5),
    ("2 Thessalonians", 3), ("1 Timothy", 6), ("2 Timothy", 4), ("Titus", 3), ("Philemon", 1),
    ("Hebrews", 13), ("James", 5), ("1 Peter", 5), ("2 Peter", 3), ("1 John", 5),
    ("2 John", 1), ("3 John", 1), ("Jude", 1), ("Revelation", 22),
]
CUT_MARKERS = ["Read full chapter", '<div class="crossreferences', '<div class="footnotes',
               'passage-other-trans', "View more titles", "Font Size"]
TAIL_JUNK = ["Next ", "View more titles", "Buy Now", "Font Size", "Bible Gateway Plus"]

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}
LOCK = None  # set in main

VERPAT = re.compile(
    r'<span id="en-[^"]+" class="text [^"]+?-(\d+)"'
    r'(.*?)(?=<span id="en-|<div class="crossreferences|<div class="footnotes|'
    r'passage-other-trans|Read full chapter|View more titles|Font Size|$)', re.S)


def fetch(url, retries=4):
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45, context=ctx) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception:
            if a == retries - 1:
                raise
            time.sleep(1.5 * (a + 1))


def clean_text(body):
    body = re.sub(r'<span class="chapternum">.*?</span>', " ", body, flags=re.S)
    body = re.sub(r"<sup\b.*?</sup>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<h[1-4]\b.*?</h[1-4]>", " ", body, flags=re.S | re.I)
    for m in TAIL_JUNK:
        j = body.find(m)
        if j > 0:
            body = body[:j]
    txt = re.sub(r"<[^>]+>", " ", body)
    txt = H.unescape(txt)
    txt = re.sub(r"\(\s+", "(", txt)
    txt = re.sub(r"^[^A-Za-z0-9\"'(\[]+\s*", "", txt)  # leading '> ' artifacts
    return re.sub(r"\s+", " ", txt).strip()


def scrape_chapter(version, book, chapter):
    q = urllib.parse.urlencode({"search": f"{book} {chapter}", "version": version, "interface": "url"})
    page = fetch(f"https://www.biblegateway.com/passage/?{q}")
    i = page.find('<div class="passage-text"')
    if i < 0:
        raise ValueError("passage-text not found (blocked or bad ref)")
    seg = page[i:]
    for marker in CUT_MARKERS:
        j = seg.find(marker)
        if j > 0:
            seg = seg[:j]
    verses = []
    for m in VERPAT.finditer(seg):
        verses.append({"verse": int(m.group(1)), "text": clean_text(m.group(2))})
    if not verses:
        raise ValueError("no verses parsed")
    return verses


def worker(job):
    version, book, chapter, out_path = job
    try:
        verses = scrape_chapter(version, book, chapter)
        line = json.dumps({"version": version, "book": book, "chapter": chapter,
                           "verses": verses}, ensure_ascii=False) + "\n"
    except Exception as e:
        line = json.dumps({"version": version, "book": book, "chapter": chapter,
                           "error": f"{type(e).__name__}: {str(e)[:100]}"}) + "\n"
        err_path = out_path + ".err"
        with LOCK:
            with open(err_path, "a") as f:
                f.write(line)
        return ("err",)
    with LOCK:
        with open(out_path, "a") as f:
            f.write(line)
    return ("ok",)


def main():
    global LOCK
    LOCK = threading.Lock()
    os.makedirs(OUT_DIR, exist_ok=True)
    all_jobs = []
    for ver in VERSIONS:
        path = os.path.join(OUT_DIR, f"{ver}.jsonl")
        done = set()
        if os.path.exists(path):
            for line in open(path):
                try:
                    r = json.loads(line)
                    done.add((r["book"], r["chapter"]))
                except Exception:
                    pass
        for book, nch in BOOKS:
            for ch in range(1, nch + 1):
                if (book, ch) not in done:
                    all_jobs.append((ver, book, ch, path))
    print(f"total jobs: {len(all_jobs)}", flush=True)
    if not all_jobs:
        print("ALL DONE (nothing to do)", flush=True)
        return

    t0 = time.time()
    n_ok = n_err = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = [ex.submit(worker, j) for j in all_jobs]
        from concurrent.futures import as_completed
        for n, fut in enumerate(as_completed(futures), 1):
            r = fut.result()[0]
            if r == "ok":
                n_ok += 1
            else:
                n_err += 1
            if n % 200 == 0:
                print(f"{n}/{len(all_jobs)} ok={n_ok} err={n_err} {time.time()-t0:.0f}s", flush=True)
    print(f"ALL DONE ok={n_ok} err={n_err} in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
