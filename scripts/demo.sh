#!/usr/bin/env bash
set -euo pipefail
python js_summarizer.py "https://news.ycombinator.com" --print
python js_summarizer.py "https://edition.cnn.com" --force-js --print --wait-css "body"