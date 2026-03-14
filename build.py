#!/usr/bin/env python3
"""Convert heidelberg.md into a single-file responsive HTML.

This script reads `heidelberg.md`, normalizes scripture links to use ESV,
removes footnote numerals while keeping the reference links, and writes
`index.html` with a responsive, dark-mode-aware stylesheet.

Usage:
    python build.py

Requirements:
    - Python 3.8+
    - markdown package (pip install markdown)

"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup

_CACHE_PATH = pathlib.Path(__file__).resolve().parent / "biblegateway.json"
_CACHE_LOCK = threading.Lock()

try:
    with open(_CACHE_PATH, "r", encoding="utf-8") as f:
        _BIBLEGATEWAY_CACHE: dict[str, str] = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    _BIBLEGATEWAY_CACHE: dict[str, str] = {}


def _save_biblegateway_cache() -> None:
    """Persist the in-memory BibleGateway cache to disk."""

    with _CACHE_LOCK:
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_BIBLEGATEWAY_CACHE, f, ensure_ascii=False, indent=2)


def strip_passage(html):
    passage = BeautifulSoup(html, "html.parser")

    for tag in passage.select("script, style"):
        tag.decompose()

    for tag in passage.select(
        "a.full-chap-link, div.crossrefs, sup.crossreference, div.passage-other-trans"
    ):
        tag.decompose()

    for tag in passage.findAll(True):
        tag.attrs = None

    return passage.decode_contents()


def _fetch_bible_passage(url: str) -> str:
    """Fetch the passage HTML from BibleGateway for the given URL.

    Returns the inner HTML of the passage content, or an empty string on failure.
    """

    try:
        import requests
    except ImportError as e:
        raise SystemExit(
            "The python packages 'requests' and 'beautifulsoup4' are required to fetch passages. "
            "Install them with: pip install requests beautifulsoup4"
        ) from e

    print(f"Fetching passage: {url}")
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
    except Exception as exc:
        print(f"  Failed to fetch passage: {exc}")
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    passage = soup.select_one("div.passage-content")
    if not passage:
        print("  Warning: passage content not found")
        return ""

    html = passage.decode_contents()

    return strip_passage(html)


def _replace_bible_links(html: str) -> str:
    """Replace BibleGateway links with <details> blocks containing the passage."""

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    urls: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "biblegateway.com/passage" not in href:
            continue
        if "version=ESV" not in href:
            continue
        urls.add(href)

    if urls:
        urls_to_fetch = [u for u in urls if u not in _BIBLEGATEWAY_CACHE]
        if urls_to_fetch:
            with ThreadPoolExecutor(max_workers=4) as executor:
                for url, passage_html in zip(
                    urls_to_fetch, executor.map(_fetch_bible_passage, urls_to_fetch)
                ):
                    if passage_html:
                        with _CACHE_LOCK:
                            _BIBLEGATEWAY_CACHE[url] = passage_html

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "biblegateway.com/passage" not in href:
            continue
        if "version=ESV" not in href:
            continue

        summary_text = a.get_text(strip=True)
        if not summary_text:
            summary_text = href

        passage_html = strip_passage(_BIBLEGATEWAY_CACHE.get(href, ""))

        details = soup.new_tag("details")
        summary = soup.new_tag("summary")
        summary.string = summary_text
        details.append(summary)

        if passage_html:
            fragment = BeautifulSoup(passage_html, "html.parser")
            for child in fragment.contents:
                details.append(child)
        else:
            placeholder = soup.new_tag("em")
            placeholder.string = "(passage not available)"
            details.append(placeholder)

        a.replace_with(details)

    # Remove separators (semicolons and <br> tags) that appear between successive
    # <details> elements. These are artifacts of the original markdown formatting
    # (e.g. ";" and "\\" line breaks).
    from bs4 import NavigableString

    for details in soup.find_all("details"):
        # Remove separators immediately following a <details>.
        sibling = details.next_sibling
        while sibling is not None:
            if isinstance(sibling, NavigableString) and re.match(r"^[\s;\u00a0]*$", str(sibling)):
                next_sib = sibling.next_sibling
                sibling.extract()
                sibling = next_sib
                continue

            if getattr(sibling, "name", None) == "br":
                next_sib = sibling.next_sibling
                sibling.extract()
                sibling = next_sib
                continue

            break

    return str(soup)


def _sanitize_markdown(md: str) -> str:
    md = md.replace("\u00a0", " ")

    lines = []

    for line in md.splitlines():
        if re.match(r"^\s*\d+\s*\[", line):
            line = re.sub(r"^\s*\d+\s*", "", line)

        line = re.sub(r"\d+\\$", "  ", line)

        line = re.sub(r"\\$", "  ", line)

        line = re.sub(r"(?<=\S)\d+$", "", line)

        lines.append(line)

    md = "\n".join(lines)

    md = re.sub(r"^(#{3,6})\s+", "### ", md, flags=re.MULTILINE)

    md = md.replace("version=nrsv", "version=ESV")

    return md


def _render_html(markdown_text: str) -> str:
    try:
        import markdown

        html_body = markdown.markdown(
            markdown_text,
            extensions=["extra", "sane_lists", "smarty"],
            output_format="html5",
        )

        html_body = _replace_bible_links(html_body)
    except ImportError as e:
        raise SystemExit(
            "The python package 'markdown' is required to render HTML. "
            "Install it with: pip install markdown"
        ) from e

    return html_body


def _wrap_html(body: str) -> str:
    css = """/* Base typography and layout */
html {
  box-sizing: border-box;
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    'Segoe UI', sans-serif;
  line-height: 1.55;
  scroll-behavior: smooth;
}
*, *::before, *::after { box-sizing: inherit; }

body {
  margin: 0;
  padding: 2rem 1.5rem 3rem;
  color: #111;
  background: #fefefe;
}

main {
  margin: 0 auto;
  max-width: 720px;
}

h1, h2, h3, h4, h5, h6 {
  margin-top: 2.25rem;
  margin-bottom: 1rem;
  line-height: 1.2;
}

h1 {
  font-size: 2.25rem;
}

h2 {
  font-size: 1.75rem;
}

h3 {
  font-size: 1.35rem;
}

p {
  margin: 1rem 0;
}

a {
  color: #1a4b7c;
  text-decoration: none;
}

a:hover, a:focus {
  text-decoration: underline;
}

code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  background: rgba(0, 0, 0, 0.04);
  padding: 0.2em 0.35em;
  border-radius: 0.25em;
}

pre {
  background: rgba(0, 0, 0, 0.04);
  padding: 1rem;
  border-radius: 0.4rem;
  overflow-x: auto;
}

@media (prefers-reduced-motion: reduce) {
  :root {
    scroll-behavior: auto;
  }
}

/* Dark mode */
@media (prefers-color-scheme: dark) {
  body {
    color: #e1e1e1;
    background: #111;
  }

  a {
    color: #7aa7ff;
  }

  code {
    background: rgba(255, 255, 255, 0.08);
  }

  pre {
    background: rgba(255, 255, 255, 0.08);
  }
}
"""

    title = "Heidelberg Catechism"

    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>{css}</style>
  </head>
  <body>
    <main>
      <h1>{title}</h1>
      {body}
    </main>
  </body>
</html>
"""

    return html


def main() -> int:
    root = pathlib.Path(__file__).resolve().parent
    source = root / "heidelberg.md"
    target = root / "index.html"

    if not source.exists():
        print(f"Missing input file: {source}")
        return 1

    markdown_text = source.read_text(encoding="utf-8")
    sanitized = _sanitize_markdown(markdown_text)
    body_html = _render_html(sanitized)
    output = _wrap_html(body_html)

    target.write_text(output, encoding="utf-8")
    _save_biblegateway_cache()
    print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
