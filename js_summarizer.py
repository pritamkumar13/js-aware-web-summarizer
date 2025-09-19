#!/usr/bin/env python
"""
JS-Aware Web Summarizer (requests → Selenium fallback)
Output: concise 6 bullets + TL;DR
"""
import os, re, time, json, hashlib, pathlib, argparse
from typing import Optional, Tuple
import requests
from bs4 import BeautifulSoup
from readability import Document

# Selenium (lazy import to speed up static runs)
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

CACHE_DIR = pathlib.Path("cache"); CACHE_DIR.mkdir(exist_ok=True)
TIMEOUT = 20
MAX_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "1200"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

def _key(s: str) -> str: return hashlib.sha256(s.encode()).hexdigest()[:16]
def _cache_write(name: str, data: bytes): (CACHE_DIR / name).write_bytes(data)
def _cache_read(name: str): p = CACHE_DIR / name; return p.read_bytes() if p.exists() else None

def strip_noise(html_text: str) -> str:
    soup = BeautifulSoup(html_text, "lxml")
    for tag in soup(["script","style","noscript"]): tag.extract()
    return soup.get_text(" ", strip=True)

def looks_js_heavy(html_text: str) -> bool:
    scripts = len(re.findall(r'<script[\\s>]', html_text, flags=re.I))
    return scripts > 20 or len(strip_noise(html_text)) < 400

class FetchResult(dict):
    __getattr__ = dict.get

def fetch_static(url: str) -> FetchResult:
    t0 = time.time()
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    r.raise_for_status()
    html_text = r.text
    return FetchResult(url=url, method="requests", html=html_text, text=strip_noise(html_text), elapsed=time.time()-t0)

def fetch_selenium(url: str, wait_css: Optional[str]=None) -> FetchResult:
    t0 = time.time()
    opts = Options()
    opts.add_argument("--headless=new"); opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu"); opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument(f"--user-agent={USER_AGENT}")
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=opts)
    try:
        driver.set_page_load_timeout(TIMEOUT)
        driver.get(url)
        if wait_css:
            WebDriverWait(driver, min(TIMEOUT, 15)).until(EC.presence_of_element_located((By.CSS_SELECTOR, wait_css)))
        html_text = driver.page_source
    finally:
        driver.quit()
    return FetchResult(url=url, method="selenium", html=html_text, text=strip_noise(html_text), elapsed=time.time()-t0)

def smart_fetch(url: str, force_js=False, wait_css: Optional[str]=None) -> FetchResult:
    ck = f"raw_{_key(url)}.html"
    cached = _cache_read(ck)
    if cached:
        html_text = cached.decode("utf-8", errors="ignore")
        return FetchResult(url=url, method="cache", html=html_text, text=strip_noise(html_text), elapsed=0.0)
    try:
        if not force_js:
            s = fetch_static(url)
            if not looks_js_heavy(s["html"]):
                _cache_write(ck, s["html"].encode("utf-8", errors="ignore"))
                return s
        s = fetch_selenium(url, wait_css=wait_css)
        _cache_write(ck, s["html"].encode("utf-8", errors="ignore"))
        return s
    except Exception:
        alt = fetch_static(url) if force_js else fetch_selenium(url, wait_css=wait_css)
        _cache_write(ck, alt["html"].encode("utf-8", errors="ignore"))
        return alt

def extract_main_content(html_text: str, url: str) -> Tuple[str, str]:
    try:
        doc = Document(html_text)
        title = doc.short_title()
        text = strip_noise(doc.summary(html_partial=True))
        return title, text
    except Exception:
        return "", strip_noise(html_text)

def short(txt: str, n=18000) -> str:
    return txt[:n] + ("…" if len(txt) > n else "")

def summarize_via_openai(text: str, url: str, model: str = MODEL, max_tokens: int = MAX_TOKENS) -> str:
    import http.client, json
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key: raise RuntimeError("Set OPENAI_API_KEY")
    system = "Be concise. 6 bullets max. Include 1 line TL;DR. Use plain text."
    user = f"Source: {url}\\n\\nContent:\\n{text}"
    body = json.dumps({
        "model": model,
        "input": [
            {"role":"system","content":system},
            {"role":"user","content":user}
        ],
        "max_output_tokens": max_tokens
    })
    conn = http.client.HTTPSConnection("api.openai.com")
    conn.request("POST", "/v1/responses", body=body, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    })
    resp = conn.getresponse()
    data = json.loads(resp.read())
    conn.close()
    try:
        return data["output"][0]["content"][0]["text"]
    except Exception:
        return json.dumps(data, indent=2)

def summarize_url(url: str, force_js=False, wait_css: Optional[str]=None) -> dict:
    fetched = smart_fetch(url, force_js=force_js, wait_css=wait_css)
    title, main_text = extract_main_content(fetched["html"], url)
    text = short(main_text, n=18000)
    summ = summarize_via_openai(text, url)
    out = {
        "url": url,
        "title": title or "(no title)",
        "method": fetched["method"],
        "elapsed_sec": round(fetched["elapsed"], 2),
        "summary": summ.strip(),
    }
    _cache_write(f"sum_{_key(url)}.json", json.dumps(out, ensure_ascii=False, indent=2).encode())
    return out

def main():
    p = argparse.ArgumentParser(description="Short JS-aware web summarizer")
    p.add_argument("url", help="Page to summarize")
    p.add_argument("--force-js", action="store_true", help="Force Selenium")
    p.add_argument("--wait-css", default=None, help="CSS selector to wait for")
    p.add_argument("--print", action="store_true", help="Print summary to stdout")
    args = p.parse_args()
    out = summarize_url(args.url, force_js=args.force_js, wait_css=args.wait_css)
    path = CACHE_DIR / f"sum_{_key(args.url)}.json"
    print(f"Saved: {path}")
    if args.print:
        print("\\n== Summary ==\\n", out["summary"])

if __name__ == "__main__":
    main()