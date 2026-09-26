#!/usr/bin/env python3
"""Generate Workshop Manual 2's navigation menu from its pdf.xml table of contents.

The original menu parsed pdf.xml at runtime with Internet Explorer-only XML
APIs, so it stopped working in modern browsers. This script turns pdf.xml into
a static menu_tree.html instead, which works in any browser, on GitHub Pages
and when the site is opened straight from disk.

Wiring-diagram entries in pdf.xml point at IE-only viewer pages such as
"f_relay/relay.html?page=20" or "h_system/system.html?code=abs". Each of those
simply displays one PDF, so the menu links to that PDF directly.

Usage (from the repository root):
    python3 tools/build_wm2_menu.py
"""
import html
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENTS = os.path.join(ROOT, "Workshop Manual 2", "CONTENTS")
SOURCE = os.path.join(CONTENTS, "pdf.xml")
OUTPUT = os.path.join(CONTENTS, "menu_tree.html")

VIEWER_URL = re.compile(r"^(?P<dir>.*/)(?P<view>[a-z0-9_]+)\.html\?(?P<kind>page|code)=(?P<val>[A-Za-z0-9_-]+)$")
TAGS = {"sup": "Supplement", "sb": "Service bulletin"}

problems = []


def resolve(url):
    """Return a PDF path (relative to CONTENTS) for an entry's URL."""
    url = url.strip()
    m = VIEWER_URL.match(url)
    if m:
        d, view, kind, val = m.group("dir", "view", "kind", "val")
        if kind == "page":
            candidates = [f"{d}{val}.pdf"]
        else:
            candidates = [f"{d}{view}/{v}.pdf" for v in (val, val.lower(), val.upper())]
        url = next((c for c in candidates if os.path.exists(os.path.join(CONTENTS, c))), url)
    if not os.path.exists(os.path.join(CONTENTS, url)):
        problems.append(url)
    return url


def esc(text):
    return html.escape((text or "").strip(), quote=True)


def render(node, depth):
    pad = "  " * depth
    out = []
    for child in node:
        if child.tag == "menu":
            out.append(f"{pad}<li><details><summary>{esc(child.findtext('title'))}</summary>")
            out.append(f"{pad}  <ul>")
            out.extend(render(child, depth + 2))
            out.append(f"{pad}  </ul>")
            out.append(f"{pad}</details></li>")
        elif child.tag == "item":
            href = esc(resolve(child.findtext("url")))
            tag = TAGS.get((child.findtext("datatype") or "").strip())
            badge = f' <span class="tag">{tag}</span>' if tag else ""
            out.append(f'{pad}<li><a href="{href}" target="pdf" data-doc>{esc(child.findtext("title"))}</a>{badge}</li>')
    return out


def main():
    root = ET.parse(SOURCE).getroot()
    body = "\n".join(render(root, 3))
    count = len(root.findall(".//item"))
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "menu_tree.template.html"), encoding="utf-8") as f:
        page = f.read()
    page = page.replace("<!-- MENU -->", body).replace("<!-- COUNT -->", str(count))
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Wrote {os.path.relpath(OUTPUT, ROOT)}: {len(root.findall('menu'))} manuals, {count} entries")
    if problems:
        print(f"WARNING: {len(problems)} entries point at files that do not exist:", *problems[:20], sep="\n  ")
        sys.exit(1)


if __name__ == "__main__":
    main()
