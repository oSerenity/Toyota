#!/usr/bin/env python3
"""Generate the viewer page (index.html) for each manual.

All three manuals share one frame-free viewer (assets/viewer.css, assets/viewer.js)
styled after Workshop Manual 2's original look: Toyota top bar with Back/Forward,
a tree menu with +/- boxes and coloured book icons, the TREE CLOSE / width / RESET
button bar, and a welcome screen. It adapts to phones (the menu becomes a drawer).

The tree for each manual is read from that manual's existing table of contents:
  - Workshop Manual 1 (2006 Repair Manual):  Workshop Manual 1/menu_camry.html
  - EWD (2006 Electrical Wiring Diagram):    EWD/menu.html
  - Workshop Manual 2 (ACV30/MCV30 library): Workshop Manual 2/CONTENTS/pdf.xml

Usage (from the repository root):
    python3 tools/build_viewers.py
"""
import html
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
ASSETS_IMG = os.path.join(ROOT, "assets", "img")
WM2_IMAGES = os.path.join(ROOT, "Workshop Manual 2", "CONTENTS", "images")

sys.path.insert(0, TOOLS)
import build_wm2_menu  # noqa: E402  (reuses its viewer-URL -> PDF resolver)

# Images from Workshop Manual 2 that the shared viewer uses.
IMAGES = (
    ["logo.png", "back_a.jpg"]
    + [f"{b}{n}.gif" for b in ("back", "forward", "treeopen", "treeclose", "widthdown", "widthup", "reset") for n in (1, 2, 3)]
    + [f"{b}{n}.gif" for b in ("plas", "minas") for n in (1, 2)]
    + [f"{s}_{c}.gif" for s in ("close", "open") for c in ("g", "y", "r", "p", "lb")]
)
BOOK_COLOURS = ["g", "y", "r", "p", "b", "lb"]
DOC_TAGS = {"sup": "Supplement", "sb": "Service bulletin"}


class Node:
    """A menu section (children) or a document (href)."""

    def __init__(self, title, href=None, colour=None, kind=None):
        self.title = re.sub(r"\s+", " ", title or "").strip()
        self.href = href
        self.colour = colour  # book colour letter for sections, or None
        self.kind = kind      # "sup" / "sb" for documents
        self.children = []

    def count(self):
        return (1 if self.href else 0) + sum(c.count() for c in self.children)


# --------------------------------------------------------------------------- readers

class _LegacyMenuParser(HTMLParser):
    """Reads the old showmenu('id') + <DIV id> menus and <details>/<summary> menus."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]     # open sections
        self.div_stack = []          # per <div>: section Node or None
        self.labels = {}             # showmenu id -> label text
        self.trigger = None          # showmenu id of the <a> being read
        self.link = None             # href of the document <a> being read
        self.text = []
        self.in_summary = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a":
            m = re.search(r"showmenu\('([^']+)'\)", a.get("onmousedown") or "")
            href = (a.get("href") or "").strip()
            if m:
                self.trigger, self.text = m.group(1), []
            elif re.search(r"\.pdf(?:[?#]|$)", href, re.I):
                self.link, self.text = href, []
        elif tag == "div":
            section = None
            if a.get("id") in self.labels:
                section = Node(self.labels[a["id"]])
                self.stack[-1].children.append(section)
                self.stack.append(section)
            self.div_stack.append(section)
        elif tag == "details":
            section = Node("")
            self.stack[-1].children.append(section)
            self.stack.append(section)
        elif tag == "summary":
            self.in_summary, self.text = True, []

    def handle_endtag(self, tag):
        if tag == "a" and self.trigger:
            self.labels[self.trigger] = "".join(self.text)
            self.trigger = None
        elif tag == "a" and self.link:
            title = "".join(self.text)
            if title.strip():
                self.stack[-1].children.append(Node(title, href=self.link))
            self.link = None
        elif tag == "div" and self.div_stack:
            if self.div_stack.pop() is not None:
                self.stack.pop()
        elif tag == "details" and len(self.stack) > 1:
            self.stack.pop()
        elif tag == "summary":
            self.stack[-1].title = re.sub(r"\s+", " ", "".join(self.text)).strip()
            self.in_summary = False

    def handle_data(self, data):
        if self.trigger or self.link or self.in_summary:
            self.text.append(data)


def read_legacy_menu(path, top_colour):
    parser = _LegacyMenuParser()
    with open(path, encoding="utf-8", errors="replace") as f:
        parser.feed(f.read())
    root = parser.root
    for child in root.children:
        if not child.href:
            child.colour = top_colour
    return root


def read_pdf_xml(path, manual_dir):
    """Workshop Manual 2: pdf.xml, with URLs made relative to the manual folder."""
    contents = os.path.dirname(path)

    def walk(el, node):
        for child in el:
            if child.tag == "menu":
                try:
                    idx = int((child.findtext("color") or "-1").strip())
                except ValueError:
                    idx = -1
                colour = BOOK_COLOURS[idx] if 0 <= idx < len(BOOK_COLOURS) else None
                section = Node(child.findtext("title"), colour=colour)
                node.children.append(section)
                walk(child, section)
            elif child.tag == "item":
                url = build_wm2_menu.resolve(child.findtext("url"))
                href = os.path.relpath(os.path.normpath(os.path.join(contents, url)), manual_dir).replace(os.sep, "/")
                kind = (child.findtext("datatype") or "").strip() or None
                node.children.append(Node(child.findtext("title"), href=href, kind=kind))

    root = Node("root")
    walk(ET.parse(path).getroot(), root)
    return root


# --------------------------------------------------------------------------- output

def esc(text):
    return html.escape(text or "", quote=True)


def render(node, manual_dir, depth, problems):
    pad = "    " * depth
    out = []
    kids = node.children
    for i, child in enumerate(kids):
        n = 1 if i == len(kids) - 1 else 2  # plas1/minas1 for the last child, as in the original
        title = esc(child.title)
        if child.href:
            path = os.path.normpath(os.path.join(manual_dir, child.href.split("#")[0].split("?")[0]))
            if not os.path.exists(path):
                # The menu lists it but the PDF is not in the repository: show it, but not as a dead link.
                problems.append(child.href)
                out.append(f'{pad}<li><span class="missing" title="{title} (not included in this copy of the manual)">'
                           f'{title} <em>(not included)</em></span></li>')
                continue
            cls = child.kind if child.kind in DOC_TAGS else "pdf"
            hint = f" ({DOC_TAGS[child.kind].lower()})" if child.kind in DOC_TAGS else ""
            out.append(f'{pad}<li><a class="{cls}" href="{esc(child.href)}" target="_blank" rel="noopener" '
                       f'title="{title}{hint}" data-doc>{title}</a></li>')
        else:
            book = ""
            if child.colour and os.path.exists(os.path.join(ASSETS_IMG, f"close_{child.colour}.gif")):
                book = (f'<img src="../assets/img/close_{child.colour}.gif" data-open="../assets/img/open_{child.colour}.gif" '
                        f'data-closed="../assets/img/close_{child.colour}.gif" width="24" height="18" alt="">')
            out.append(f'{pad}<li><details><summary title="{title}">'
                       f'<img src="../assets/img/plas{n}.gif" data-open="../assets/img/minas{n}.gif" '
                       f'data-closed="../assets/img/plas{n}.gif" width="13" height="13" alt="">{book}'
                       f'<span>{title}</span></summary>')
            out.append(f"{pad}    <ul>")
            out.extend(render(child, manual_dir, depth + 2, problems))
            out.append(f"{pad}    </ul>")
            out.append(f"{pad}</details></li>")
    return out


def facts(pairs):
    return "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in pairs)


MANUALS = [
    {
        "dir": "Workshop Manual 1",
        "tree": lambda d: read_legacy_menu(os.path.join(d, "menu_camry.html"), "g"),
        "TITLE": "2006 Camry Repair Manual",
        "DESCRIPTION": "Toyota 2006 Camry repair manual: specifications, diagnostics and repair procedures.",
        "BANNER": "2006 CAMRY &nbsp;·&nbsp; REPAIR MANUAL",
        "SUBTITLE": "2006 · Repair Manual",
        "WELCOME_TITLE": "2006 CAMRY Repair Manual",
        "WELCOME_FACTS": facts([("Model year", "2006")]),
        "COPYRIGHT": "Manual content © Toyota Motor Corporation.",
    },
    {
        "dir": "EWD",
        "tree": lambda d: read_legacy_menu(os.path.join(d, "menu.html"), "r"),
        "TITLE": "2006 Camry Electrical Wiring Diagram",
        "DESCRIPTION": "Toyota 2006 Camry electrical wiring diagram: system circuits, relay locations, routing, ground points and connectors.",
        "BANNER": "2006 CAMRY &nbsp;·&nbsp; ELECTRICAL WIRING DIAGRAM",
        "SUBTITLE": "2006 · Electrical Wiring Diagram",
        "WELCOME_TITLE": "2006 CAMRY Electrical Wiring Diagram",
        "WELCOME_FACTS": facts([("Model year", "2006")]),
        "COPYRIGHT": "Manual content © Toyota Motor Corporation.",
    },
    {
        "dir": "Workshop Manual 2",
        "tree": lambda d: read_pdf_xml(os.path.join(d, "CONTENTS", "pdf.xml"), d),
        "TITLE": "Camry ACV30/MCV30 Workshop Manual",
        "DESCRIPTION": "Toyota Camry ACV30/31 and MCV30 series service library: repair manuals, wiring diagram, body repair and new car features.",
        "BANNER": "OVERSEAS CUSTOMER SERVICE TECHNICAL DIVISION",
        "SUBTITLE": "ACV30/31 &amp; MCV30 series",
        "WELCOME_TITLE": "CAMRY PDF Manual",
        "WELCOME_FACTS": facts([("Applicable models", "ACV30, 31 series<br>MCV30 series")]),
        "COPYRIGHT": "Copyright © 2003-2004 Toyota Motor Corporation. All rights reserved.",
    },
]

REDIRECT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta http-equiv="refresh" content="0; url={target}">
    <script>location.replace("{target}" + location.hash);</script>
</head>
<body>
    <p>This manual has moved. <a href="{target}">Open the {title}</a>.</p>
</body>
</html>
"""

# Old entry pages that now forward to the new viewer (kept so bookmarks keep working).
REDIRECTS = [
    ("EWD/camry_2006.html", "index.html", "2006 Camry Electrical Wiring Diagram"),
    ("Workshop Manual 1/camry_2006.html", "index.html", "2006 Camry Repair Manual"),
    ("Workshop Manual 2/CONTENTS/index.html", "../index.html", "Camry ACV30/MCV30 Workshop Manual"),
]


def main():
    os.makedirs(ASSETS_IMG, exist_ok=True)
    for name in IMAGES:
        shutil.copy2(os.path.join(WM2_IMAGES, name), os.path.join(ASSETS_IMG, name))

    with open(os.path.join(TOOLS, "viewer.template.html"), encoding="utf-8") as f:
        template = f.read()

    for manual in MANUALS:
        manual_dir = os.path.join(ROOT, manual["dir"])
        tree = manual["tree"](manual_dir)
        problems = []
        body = "\n".join(render(tree, manual_dir, 6, problems))
        page = template.replace("{{TREE}}", body).replace("{{COUNT}}", f"{tree.count() - len(problems):,}")
        for key, value in manual.items():
            if key.isupper():
                page = page.replace("{{" + key + "}}", value)
        out = os.path.join(manual_dir, "index.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(page)
        print(f"Wrote {os.path.relpath(out, ROOT)}: {len(tree.children)} top-level entries, {tree.count()} documents")
        if problems:
            print(f"  Note: {len(problems)} entries point at PDFs that are not in the repository; shown as 'not included':",
                  *problems[:15], sep="\n    ")

    for path, target, title in REDIRECTS:
        with open(os.path.join(ROOT, path), "w", encoding="utf-8") as f:
            f.write(REDIRECT.format(target=target, title=title))
        print(f"Redirect {path} -> {target}")


if __name__ == "__main__":
    main()
