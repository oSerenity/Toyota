#!/usr/bin/env python3
"""Generate the site's single combined manual (index.html at the repository root).

Every manual on the site is merged into one tree, grouped by model:
  2006 Camry: Repair Manual + Electrical Wiring Diagram
  ACV30/31 & MCV30 series: the 13 manuals of Workshop Manual 2
It uses one frame-free viewer (assets/viewer.css, assets/viewer.js)
styled after Workshop Manual 2's original look: Toyota top bar with Back/Forward,
a tree menu with +/- boxes and coloured book icons, the TREE CLOSE / width / RESET
button bar, and a welcome screen. It adapts to phones (the menu becomes a drawer).

Each manual's part of the tree is read from its existing table of contents:
  - Workshop Manual 1 (2006 Repair Manual):  Workshop Manual 1/menu_camry.html
  - EWD (2006 Electrical Wiring Diagram):    EWD/menu.html
  - Workshop Manual 2 (ACV30/MCV30 library): Workshop Manual 2/CONTENTS/pdf.xml

Usage (from the repository root):
    python3 tools/build_viewers.py
"""
import html
import json
import urllib.parse
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
        self.extras = []      # [(label, href)] extra pages shown after a document, e.g. "p.2", "Description"

    def count(self):
        return (1 if self.href else 0) + len(self.extras) + sum(c.count() for c in self.children)


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


def read_legacy_menu(path):
    parser = _LegacyMenuParser()
    with open(path, encoding="utf-8", errors="replace") as f:
        parser.feed(f.read())
    return parser.root


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
                raw = child.findtext("url").strip()
                url = build_wm2_menu.resolve(raw)
                kind = (child.findtext("datatype") or "").strip() or None
                doc = Node(child.findtext("title"), href=rel(url), kind=kind)
                doc.extras = viewer_extras(raw)
                node.children.append(doc)

    def rel(path_from_contents):
        return os.path.relpath(os.path.normpath(os.path.join(contents, path_from_contents)), manual_dir).replace(os.sep, "/")

    def viewer_extras(raw):
        """Pages the old wiring-diagram viewer showed with its own buttons."""
        m = build_wm2_menu.VIEWER_URL.match(raw)
        if not m:
            return []
        folder, view, kind, val = m.group("dir", "view", "kind", "val")
        extras = []
        if kind == "page":
            # pages.xml: next="k" means the following k pages continue this one.
            pages = ET.parse(os.path.join(contents, folder, "pages.xml")).getroot().findall("page")
            numbers = [pg.get("no") for pg in pages]
            if val in numbers:
                i = numbers.index(val)
                for n, pg in enumerate(pages[i + 1:i + 1 + int(pages[i].get("next") or 0)], start=2):
                    extras.append((f"p.{n}", rel(f"{folder}{pg.get('no')}.pdf")))
        elif view == "system" and os.path.exists(os.path.join(contents, folder, "text", f"{val}.pdf")):
            extras.append(("Description", rel(f"{folder}text/{val}.pdf")))
        return extras

    root = Node("root")
    walk(ET.parse(path).getroot(), root)
    return root


# --------------------------------------------------------------------------- output

def esc(text):
    return html.escape(text or "", quote=True)


def rehome(node, manual_dir):
    """Make every document href relative to the repository root (URL-encoded)."""
    def fix(href):
        path = os.path.normpath(os.path.join(manual_dir, href))
        return urllib.parse.quote(os.path.relpath(path, ROOT).replace(os.sep, "/"))

    for child in node.children:
        if child.href:
            child.href = fix(child.href)
            child.extras = [(label, fix(href)) for label, href in child.extras]
        rehome(child, manual_dir)
    return node


def render(node, depth, problems, open_levels=0):
    pad = "  " * depth
    out = []
    kids = node.children
    for i, child in enumerate(kids):
        n = 1 if i == len(kids) - 1 else 2  # plas1/minas1 for the last child, as in the original
        title = esc(child.title)
        if child.href:
            if not os.path.exists(os.path.join(ROOT, urllib.parse.unquote(child.href))):
                # Listed in the menu but the PDF is not in the repository: show it, not as a dead link.
                problems.append(child.href)
                out.append(f'{pad}<li><span class="missing" title="Not included in this copy of the manual">'
                           f'{title} <em>(not included)</em></span></li>')
                continue
            cls = child.kind if child.kind in DOC_TAGS else "pdf"
            extras = "".join(f' <a class="extra" href="{esc(href)}" data-doc data-title="{title} ({esc(label)})">{esc(label)}</a>'
                             for label, href in child.extras)
            out.append(f'{pad}<li><a class="{cls}" href="{esc(child.href)}" data-doc>{title}</a>{extras}</li>')
        else:
            is_open = open_levels > 0
            state = ("minas", "open") if is_open else ("plas", "close")
            book = f'<img src="assets/img/{state[1]}_{child.colour}.gif" alt="">' if child.colour else ""
            out.append(f'{pad}<li><details{" open" if is_open else ""}><summary title="{title}">'
                       f'<img src="assets/img/{state[0]}{n}.gif" alt="">{book}<span>{title}</span></summary><ul>')
            out.extend(render(child, depth + 1, problems, open_levels - 1))
            out.append(f"{pad}</ul></details></li>")
    return out


def section(title, *children, colour=None):
    node = Node(title, colour=colour)
    node.children.extend(children)
    return node


def build_tree():
    wm1 = os.path.join(ROOT, "Workshop Manual 1")
    ewd = os.path.join(ROOT, "EWD")
    wm2 = os.path.join(ROOT, "Workshop Manual 2")

    repair = rehome(read_legacy_menu(os.path.join(wm1, "menu_camry.html")), wm1)
    wiring = rehome(read_legacy_menu(os.path.join(ewd, "menu.html")), ewd)
    library = read_pdf_xml(os.path.join(wm2, "CONTENTS", "pdf.xml"), wm2)

    # Connector face diagrams (by Toyota part number) that the old viewer only
    # reached from its connector list; list them all in the wiring diagram.
    connectors = sorted(f for f in os.listdir(os.path.join(wm2, "ewd", "connector")) if f.lower().endswith(".pdf"))
    ewd_library = next(m for m in library.children if m.title == "Electrical Wiring Diagram")
    ewd_library.children.append(section("CONNECTOR DIAGRAMS (by part number)",
                                        *[Node(f[:-4], href=f"ewd/connector/{f}") for f in connectors]))
    rehome(library, wm2)

    return section("root",
        section("2006 Camry",
                section("Repair Manual", *repair.children, colour="g"),
                section("Electrical Wiring Diagram", *wiring.children, colour="r")),
        section("Earlier Camry: ACV30/MCV30", *library.children))


FACTS = (
    "<dt>2006 model year</dt><dd>Repair Manual, Electrical Wiring Diagram</dd>"
    "<dt>ACV30, 31 &amp; MCV30 series</dt><dd>Built from August 2001: repair, engine and transmission manuals,<br>"
    "wiring diagram, body repair, new car features, service data sheets</dd>"
)

PAGE = {
    "TITLE": "Toyota Camry Service Manual",
    "DESCRIPTION": "Toyota Camry service manual: 2006 Camry repair manual and wiring diagram, and the full service "
                   "library for the ACV30/31 and MCV30-series Camry.",
    "BANNER": "CAMRY &nbsp;·&nbsp; SERVICE MANUAL",
    "SUBTITLE": "2006 &amp; ACV30/MCV30 series",
    "WELCOME_TITLE": "CAMRY Service Manual",
    "WELCOME_FACTS": FACTS,
    "COPYRIGHT": "Manual content © Toyota Motor Corporation.",
}

# Old pages forward into the combined manual. A "#doc=" link to a document is
# carried over, rewritten to the document's path from the repository root.
REDIRECT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Toyota Camry Service Manual</title>
    <meta http-equiv="refresh" content="0; url={target}">
    <script>
        (function () {{
            var m = /(?:^#|&)doc=([^&]+)/.exec(location.hash), url = {target_js};
            if (m) {{
                var doc = decodeURIComponent(m[1]).replace(/^\.\//, "");
                url += "#doc=" + encodeURIComponent({prefix_js} + doc);
            }}
            location.replace(url);
        }})();
    </script>
</head>
<body>
    <p>The manuals have been merged. <a href="{target}">Open the Camry service manual</a>.</p>
</body>
</html>
"""

REDIRECTS = [
    # (old page, path back to the root, prefix that makes its old #doc= paths root-relative)
    ("EWD/index.html", "../index.html", "EWD/"),
    ("EWD/camry_2006.html", "../index.html", "EWD/"),
    ("Workshop Manual 1/index.html", "../index.html", "Workshop%20Manual%201/"),
    ("Workshop Manual 1/camry_2006.html", "../index.html", "Workshop%20Manual%201/"),
    ("Workshop Manual 2/index.html", "../index.html", "Workshop%20Manual%202/"),
    ("Workshop Manual 2/CONTENTS/index.html", "../../index.html", "Workshop%20Manual%202/"),
]


def main():
    os.makedirs(ASSETS_IMG, exist_ok=True)
    for name in IMAGES:
        shutil.copy2(os.path.join(WM2_IMAGES, name), os.path.join(ASSETS_IMG, name))

    with open(os.path.join(TOOLS, "viewer.template.html"), encoding="utf-8") as f:
        page = f.read()

    tree = build_tree()
    problems = []
    body = "\n".join(render(tree, 3, problems, open_levels=1))
    page = page.replace("{{TREE}}", body).replace("{{COUNT}}", f"{tree.count() - len(problems):,}")
    for key, value in PAGE.items():
        page = page.replace("{{" + key + "}}", value)
    out = os.path.join(ROOT, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Wrote index.html: {tree.count() - len(problems)} documents "
          f"({', '.join(f'{m.title}: {m.count()}' for m in tree.children)})")
    if problems:
        print(f"  Note: {len(problems)} entries point at PDFs that are not in the repository; shown as 'not included'.")

    for path, target, prefix in REDIRECTS:
        with open(os.path.join(ROOT, path), "w", encoding="utf-8") as f:
            f.write(REDIRECT.format(target=target, target_js=json.dumps(target), prefix_js=json.dumps(prefix)))
        print(f"Redirect {path} -> {target}")


if __name__ == "__main__":
    main()
