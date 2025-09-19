# JS-Aware Web Summarizer

**Short summaries from static or JS-rendered pages.**  
Falls back to headless Chrome (Selenium) when a page looks JS-heavy.

## Quick Start
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export OPENAI_API_KEY=YOUR_KEY   # Windows: set OPENAI_API_KEY=YOUR_KEY
python js_summarizer.py https://example.com --print
```

## Why it's unique
- **Smart fetch**: `requests` → auto-fallback to Selenium for JS pages.
- **Ultra-brief output**: ≤ 6 bullets + 1-line TL;DR.
- **Cache-first**: raw HTML + JSON summary saved to `cache/`.
- **Readable**: extracts main content before summarizing.

## Repo Layout
```
js-aware-web-summarizer/
├─ js_summarizer.py        # CLI tool
├─ requirements.txt
├─ README.md
├─ .gitignore
├─ LICENSE
├─ notebooks/
│  └─ summarizer_notebook.ipynb  # Jupyter version
├─ samples/
│  └─ urls.txt             # Try these pages
└─ cache/                  # Auto, ignored by git
```

## CLI
```bash
python js_summarizer.py "https://news.ycombinator.com" --print
python js_summarizer.py "https://example-react-ssr-site.com" --force-js --wait-css ".article"
```
**Flags**
- `--force-js` : force Selenium
- `--wait-css` : CSS selector to wait for (JS content)
- `--print`    : echo summary to stdout

## Notes
- Keep your key in env (`OPENAI_API_KEY`).
- If Chrome/driver issues: update Chrome; the tool auto-installs a driver.
