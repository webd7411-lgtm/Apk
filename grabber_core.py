# -*- coding: utf-8 -*-
"""
Fatwa Grabber - fatwaqa.com se fatawa download kar ke PDF volumes banata hai.
Android app ka core (Grabber class).
"""
import os, re, sys, io, time, sqlite3, threading, queue, hashlib
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from PIL import Image
from pypdf import PdfWriter, PdfReader

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) personal-archive-tool"}
MAX_PAGES = 500


class Grabber:
    def __init__(self, outdir, log=print, progress=None, stop=None,
                 delay=1.0, workers=3, volume=500):
        self.outdir = outdir
        self.log = log
        self.progress = progress or (lambda done, total: None)
        self.stop = stop or threading.Event()
        self.delay = delay
        self.workers = workers
        self.volume = volume
        os.makedirs(outdir, exist_ok=True)
        self.s = requests.Session()
        self.s.headers.update(UA)
        ad = HTTPAdapter(max_retries=3, pool_maxsize=workers + 2)
        self.s.mount("http://", ad)
        self.s.mount("https://", ad)
        self.db = sqlite3.connect(os.path.join(outdir, "progress.db"),
                                  check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS fatwa("
                        "url TEXT PRIMARY KEY, cat TEXT, idx INTEGER, "
                        "title TEXT, file TEXT, status TEXT)")
        self.db.commit()

    # ---------- network ----------
    def get(self, url):
        time.sleep(self.delay)
        r = self.s.get(url, timeout=60)
        r.raise_for_status()
        return r

    def soup(self, url):
        r = self.get(url)
        r.encoding = r.encoding or "utf-8"
        return BeautifulSoup(r.content, "html.parser"), r

    # ---------- crawl ----------
    @staticmethod
    def fatwa_links(sp, page_url, cat_path):
        out = []
        for a in sp.find_all("a", href=True):
            u = urljoin(page_url, a["href"]).split("#")[0].split("?")[0]
            p = urlparse(u)
            parts = [x for x in p.path.split("/") if x]
            cparts = [x for x in cat_path.split("/") if x]
            if (parts[:len(cparts)] == cparts and len(parts) == len(cparts) + 1):
                out.append(u)
        return list(dict.fromkeys(out))

    def collect_urls(self, cat_url):
        cat_url = cat_url.split("?")[0].rstrip("/")
        cat_path = urlparse(cat_url).path
        urls, seen = [], set()
        for page in range(1, MAX_PAGES + 1):
            if self.stop.is_set():
                break
            pu = cat_url if page == 1 else f"{cat_url}?page={page}"
            try:
                sp, _ = self.soup(pu)
            except Exception as e:
                self.log(f"[crawl] page {page} error: {e}")
                break
            new = [u for u in self.fatwa_links(sp, pu, cat_path) if u not in seen]
            if not new:
                break
            for u in new:
                seen.add(u)
                urls.append(u)
            self.log(f"[crawl] page {page}: {len(new)} naye fatawa (total {len(urls)})")
        return urls

    # ---------- download ----------
    @staticmethod
    def find_download(sp, page_url):
        cands = []
        for a in sp.find_all("a", href=True):
            href = urljoin(page_url, a["href"])
            text = a.get_text(" ", strip=True)
            low = href.lower().split("?")[0]
            score = 0
            if "ڈاؤن" in text or "download" in text.lower():
                score += 2
            if "/download/" in low:
                score += 2
            if low.endswith((".pdf", ".jpg", ".jpeg", ".png", ".webp")) and "theme/assets" not in low:
                score += 1
            if score:
                cands.append((score, href))
        cands.sort(key=lambda x: -x[0])
        return cands[0][1] if cands else None

    @staticmethod
    def title_of(sp):
        h = sp.find("h1")
        if h and h.get_text(strip=True):
            return h.get_text(" ", strip=True)
        return sp.title.get_text(strip=True) if sp.title else "fatwa"

    def to_pdf(self, content, dest):
        if content[:1024].find(b"%PDF") != -1:
            with open(dest, "wb") as f:
                f.write(content)
            PdfReader(dest)  # validate
            return
        img = Image.open(io.BytesIO(content))
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, "white")
            im = img.convert("RGBA")
            bg.paste(im, mask=im.split()[-1])
            img = bg
        else:
            img = img.convert("RGB")
        img.save(dest, "PDF", resolution=110.0)

    def process(self, cat, idx, url, filesdir):
        try:
            sp, _ = self.soup(url)
            title = self.title_of(sp)
            dl = self.find_download(sp, url)
            if not dl:
                raise Exception("download link nahi mila")
            r = self.get(dl)
            slug = urlparse(url).path.rstrip("/").split("/")[-1]
            h = hashlib.md5(url.encode()).hexdigest()[:6]
            dest = os.path.join(filesdir, f"{idx:05d}_{h}.pdf")
            self.to_pdf(r.content, dest)
            return (url, cat, idx, title, dest, "ok", None)
        except Exception as e:
            return (url, cat, idx, "", "", "fail", str(e))

    def download_category(self, cat_url):
        cat = urlparse(cat_url.split("?")[0].rstrip("/")).path.rstrip("/").split("/")[-1] or "category"
        filesdir = os.path.join(self.outdir, cat, "files")
        os.makedirs(filesdir, exist_ok=True)
        self.log(f"=== Category: {cat} ===")
        urls = self.collect_urls(cat_url)
        if not urls:
            self.log("Koi fatwa nahi mila. Link check karo.")
            return cat
        done_ok = {r[0] for r in self.db.execute(
            "SELECT url FROM fatwa WHERE status='ok'")}
        for i, u in enumerate(urls, 1):  # order save karo
            self.db.execute("INSERT OR IGNORE INTO fatwa(url,cat,idx,title,file,status) "
                            "VALUES(?,?,?,?,?,?)", (u, cat, i, "", "", "new"))
            self.db.execute("UPDATE fatwa SET idx=?, cat=? WHERE url=?", (i, cat, u))
        self.db.commit()
        todo = [(i, u) for i, u in enumerate(urls, 1) if u not in done_ok]
        total = len(urls)
        finished = total - len(todo)
        self.log(f"Total {total} fatawa, {len(todo)} download karne hain "
                 f"({finished} pehle se ho chuke).")
        self.progress(finished, total)
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            it = iter(todo)
            pending = set()
            def submit_next():
                try:
                    i, u = next(it)
                except StopIteration:
                    return False
                pending.add(ex.submit(self.process, cat, i, u, filesdir))
                return True
            for _ in range(self.workers * 2):
                if not submit_next():
                    break
            while pending:
                donefs = [f for f in list(pending) if f.done()]
                if not donefs:
                    time.sleep(0.1)
                    if self.stop.is_set():
                        for f in pending:
                            f.cancel()
                    continue
                for f in donefs:
                    pending.discard(f)
                    if f.cancelled():
                        continue
                    url, c, idx, title, dest, status, err = f.result()
                    self.db.execute("UPDATE fatwa SET title=?, file=?, status=? WHERE url=?",
                                    (title, dest, status, url))
                    self.db.commit()
                    finished += 1
                    self.progress(finished, total)
                    if status == "ok":
                        self.log(f"[{finished}/{total}] OK  " + urlparse(url).path.rstrip("/").split("/")[-1][:50])
                    else:
                        self.log(f"[{finished}/{total}] FAIL {url} -> {err}")
                    if not self.stop.is_set():
                        submit_next()
        return cat

    # ---------- merge ----------
    def merge_category(self, cat):
        rows = self.db.execute(
            "SELECT title,file FROM fatwa WHERE cat=? AND status='ok' ORDER BY idx",
            (cat,)).fetchall()
        rows = [r for r in rows if os.path.exists(r[1])]
        if not rows:
            self.log(f"{cat}: merge ke liye kuch nahi.")
            return []
        made = []
        mdir = os.path.join(self.outdir, "PDF_volumes")
        os.makedirs(mdir, exist_ok=True)
        nvol = (len(rows) + self.volume - 1) // self.volume
        for v in range(nvol):
            chunk = rows[v * self.volume:(v + 1) * self.volume]
            w = PdfWriter()
            for title, f in chunk:
                try:
                    w.append(f, outline_item=title or "fatwa", import_outline=False)
                except Exception as e:
                    self.log(f"[merge skip] {f}: {e}")
            name = (f"{cat}.pdf" if nvol == 1 else f"{cat}_volume_{v+1}.pdf")
            path = os.path.join(mdir, name)
            with open(path, "wb") as fh:
                w.write(fh)
            self.log(f"PDF bana: {path} ({len(chunk)} fatawa)")
            made.append(path)
        return made

    def run(self, cat_urls):
        cats = []
        for cu in cat_urls:
            if self.stop.is_set():
                break
            cats.append(self.download_category(cu.strip()))
        self.log("--- PDF jorna shuru ---")
        for c in cats:
            self.merge_category(c)
        self.log("KHATAM." if not self.stop.is_set()
                 else "Roka gaya. Dobara Start karoge to wahin se resume hoga.")


