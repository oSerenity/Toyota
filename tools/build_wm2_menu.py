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


# Folder ("book") icon colours from pdf.xml <color>, as in the original menu.
BOOK_COLOURS = ["g", "y", "r", "p", "b", "lb"]


def book_icon(node):
    try:
        index = int((node.findtext("color") or "-1").strip())
    except ValueError:
        return ""
    if not 0 <= index < len(BOOK_COLOURS):  # -1 means "no book icon"
        return ""
    colour = BOOK_COLOURS[index]
    if not os.path.exists(os.path.join(CONTENTS, "images", f"close_{colour}.gif")):
        return ""
    return f'<img class="book" src="images/close_{colour}.gif" data-open="images/open_{colour}.gif" data-closed="images/close_{colour}.gif" alt="">'


def render(node, depth):
    pad = "  " * depth
    out = []
    children = [c for c in node if c.tag in ("menu", "item")]
    for i, child in enumerate(children):
        n = 1 if i == len(children) - 1 else 2  # plas1/minas1 for the last child, plas2/minas2 otherwise
        if child.tag == "menu":
            title = esc(child.findtext("title"))
            out.append(f'{pad}<li><details><summary title="{title}">'
                       f'<img class="tog" src="images/plas{n}.gif" data-open="images/minas{n}.gif" data-closed="images/plas{n}.gif" alt="">'
                       f'{book_icon(child)}<span>{title}</span></summary>')
            out.append(f"{pad}  <ul>")
            out.extend(render(child, depth + 2))
            out.append(f"{pad}  </ul>")
            out.append(f"{pad}</details></li>")
        else:
            href = esc(resolve(child.findtext("url")))
            kind = (child.findtext("datatype") or "").strip()
            cls = kind if kind in TAGS else "pdf"
            hint = f' ({TAGS[kind].lower()})' if kind in TAGS else ""
            title = esc(child.findtext("title"))
            out.append(f'{pad}<li><a class="{cls}" href="{href}" target="pdf" title="{title}{hint}" data-doc>{title}</a></li>')
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
