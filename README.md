# Bible Data — 7 versi domain publik (scraper BibleGateway)

Teks Alkitab lengkap (66 buku kanonik protestan) untuk 7 terjemahan Inggris **domain publik**, discrape sopan dari BibleGateway.com (satu request per pasal, 3 worker, jeda 0,7 dtk — 8.323/8.323 sukses, 0 gagal).

## Versi
| Kode | Nama | Ayat |
|---|---|---|
| KJV | King James Version (1769) | 31.102 |
| ASV | American Standard Version (1901) | 31.086 |
| WEB | World English Bible | 31.103 |
| YLT | Young's Literal Translation (1898) | 31.102 |
| DARBY | Darby Bible (1889) | 31.099 |
| WYC | Wycliffe Bible (c. 1400, modern spelling) | 31.101 |
| DRA | Douay-Rheims 1899 American Edition | 31.226 (versifikasi Vulgate) |

Selisih jumlah ayat antar versi adalah perbedaan versifikasi yang memang benar, bukan error.

## Isi
- `data/<VER>.jsonl` — satu baris per pasal: `{"version","book","chapter","verses":[{"verse","text"}]}`
- `frontend/<VER>.json.gz` — versi kompak untuk frontend Cloudflare Worker (`{version, books:[{name, chapters:[[verse,text],...]}]}`)
- `biblegateway.py` — scraper per-ayat (passage + keyword), format output mengikuti Actor Apify `lexis-solutions/bible-gate-way-com-scraper`
- `scrape_bible_bg.py` — downloader seluruh Alkitab (checkpoint per pasal)
- `bg_local.py` — query layer lokal, output format persis kontrak Actor di atas

## Catatan hak cipta
Hanya versi domain publik yang di-dump penuh. Versi berhak cipta (NIV, ESV, NLT, NKJV, MSG, dst.) **tidak** ikut — gunakan per-ayat on-demand via `biblegateway.py` untuk kebutuhan riset/pribadi.
