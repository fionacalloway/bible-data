#!/usr/bin/env python3
"""Download complete Bibles (public-domain English versions) from bolls.life.
Output: /root/bible/bibles/<VERSION>.jsonl — one line per chapter:
  {"version","bookid","book","chapter","verses":[{"verse","text"}]}
Checkpoint-safe: skips chapters already present.
"""
import json, os, re, ssl, time, urllib.request

OUT_DIR = "/root/bible/bibles"
VERSIONS = ["KJV", "ASV", "WEB", "YLT", "BSB"]
DELAY = 0.25

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (personal research; low rate)"}

def fetch(url, retries=4):
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40, context=ctx) as r:
                return r.read()
        except Exception:
            if a == retries - 1:
                raise
            time.sleep(2 * (a + 1))

def clean_text(t):
    t = re.sub(r"<[^>]+>", "", t)          # strip <S> strongs, <J>, <I>, <E>, <b>, <i>, <br/>
    t = t.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", t).strip()

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for ver in VERSIONS:
        out_path = os.path.join(OUT_DIR, f"{ver}.jsonl")
        done = set()
        if os.path.exists(out_path):
            for line in open(out_path):
                try:
                    r = json.loads(line)
                    done.add((r["bookid"], r["chapter"]))
                except Exception:
                    pass
        books = json.loads(fetch(f"https://bolls.life/get-books/{ver}/"))
        books = [b for b in books if b["bookid"] <= 66]  # protestant canon
        total = sum(b["chapters"] for b in books)
        todo = [(b, ch) for b in books for ch in range(1, b["chapters"] + 1)
                if (b["bookid"], ch) not in done]
        print(f"[{ver}] books={len(books)} chapters={total} done={len(done)} todo={len(todo)}", flush=True)
        if not todo:
            continue
        out = open(out_path, "a")
        errs = 0
        for n, (b, ch) in enumerate(todo, 1):
            try:
                verses = json.loads(fetch(f"https://bolls.life/get-chapter/{ver}/{b['bookid']}/{ch}/"))
                rec = {"version": ver, "bookid": b["bookid"], "book": b["name"], "chapter": ch,
                       "verses": [{"verse": v["verse"], "text": clean_text(v["text"])} for v in verses]}
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
            except Exception as e:
                errs += 1
                out.write(json.dumps({"version": ver, "bookid": b["bookid"], "book": b["name"],
                                      "chapter": ch, "error": str(e)[:120]}) + "\n")
                out.flush()
            if n % 100 == 0:
                print(f"[{ver}] {n}/{len(todo)} errs={errs}", flush=True)
            time.sleep(DELAY)
        out.close()
        print(f"[{ver}] DONE errs={errs}", flush=True)
    print("ALL DONE", flush=True)

if __name__ == "__main__":
    main()
