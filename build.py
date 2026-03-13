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

import pathlib
import re
import sys


def _sanitize_markdown(md: str) -> str:
    # Normalize non-breaking spaces used by pandoc output.
    md = md.replace("\u00A0", " ")

    lines = []

    for line in md.splitlines():
        # Remove footnote numbering at the start of footnote reference lines.
        # e.g. "1 [1 Cor...." -> "[1 Cor...."
        if re.match(r"^\s*\d+\s*\[", line):
            line = re.sub(r"^\s*\d+\s*", "", line)

        # Remove footnote numbers immediately before a hard line break marker.
        # Example: ",1\" -> ",  "
        line = re.sub(r"\d+\\$", "  ", line)

        # Convert remaining hard line breaks (trailing backslash) into Markdown breaks.
        # In Markdown, two spaces at end of line emit a <br>.
        line = re.sub(r"\\$", "  ", line)

        # Remove remaining inline footnote numbers at the end of a line.
        # Example: "... my own,1" -> "... my own,"
        line = re.sub(r"(?<=\S)\d+$", "", line)

        lines.append(line)

    md = "\n".join(lines)

    # Normalize headings so that h2 are preserved and deeper headings become h3.
    # Source uses "##" for major sections (Part I/II) and "####" for Lord's Day.
    md = re.sub(r"^(#{3,6})\s+", "### ", md, flags=re.MULTILINE)

    # Convert scripture links from nrsv to ESV.
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
    print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
