"""Assemble the Explorer page from src/template.html.

Writes two copies of the same page:
  dtree_explorer/explorer.html   for the package and the GitHub release (no visit counting)
  site/index.html                for dtree.digraphs.net (GoatCounter: visits counted, no cookies)

Both embed the examples (from the repository's examples/), the DTree (3.0 and 2.x), EulerTree and DList sources
of this repository (fallback when PyPI cannot be reached; the same version the page installs from PyPI), the
bridge, and the default example precomputed with the bridge (each encoding, each kind of position).
Run from python/explorer:  python src/build.py
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # python/explorer
REPO = os.path.dirname(os.path.dirname(ROOT))                                # the Triordinal repository
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(REPO, "python", "dlist"))                   # this repository's DList and DTree,
sys.path.insert(0, os.path.join(REPO, "python", "dtree"))                   # not an installed copy

import triordinal.dlist as dlist  # noqa: E402
import triordinal.dtree as dtree  # noqa: E402

from dtree_explorer import __version__ as EXPLORER_VERSION  # noqa: E402
from dtree_explorer import bridge  # noqa: E402

# online copy at dtree.digraphs.net: GoatCounter (no cookies) and the privacy notice next to it
SITE = {"counter": "https://dtree.goatcounter.com/count", "privacy": "privacy.html"}

DEFAULT = "Paper, Appendix A: base tree (Test.csx)"
APPENDIX = "examples/Test.csx"
FIG1 = """# Paper, Figure 1 (Q1 = 1 ... 12)
1: 2
2: 3; 4; 9
4: 5
5: 6; 7
7: 8
9: 10; 12
10: 11
"""
EXAMPLES = [
    ("Quick start", "A: B; D\nB: C\n"),
    ("Paper, Sec. 1: D between B and C", "# Paper, Section 1: D becomes a child of B, between B and its sibling C\nA: B; C\nB: D\n"),
    ("Paper, Figure 1", FIG1),
    ("Paper, Sec. 4.1, Case A: v before 6", FIG1 + "# Insert(5, v, 6) before: v directly before its sibling 6\n6 < v\n"),
    ("Paper, Sec. 4.1, Case B: v after 6", FIG1 + "# Insert(5, v, 6) after: v directly after its sibling 6\n6 > v\n"),
    (DEFAULT, APPENDIX),
    ("Paper, Appendix A, Variant A: X first (Test21.csx)", "examples/Test21.csx"),
    ("Paper, Appendix A, Variant A with <", ("base", "# Variant A written with '<': X directly before 02\n02 < X\nX: Y; Z\n")),
    ("Paper, Appendix A, Variant B: X middle (test23.csx)", "examples/test23.csx"),
    ("Paper, Appendix A, Variant B with >", ("base", "# Variant B written with '>': X directly after 03\n03 > X\nX: Y; Z\n")),
    ("Paper, Appendix A, Variant C: X last (test22.csx)", "examples/test22.csx"),
    ("Paper, Appendix A, Variant C with >", ("base", "# Variant C written with '>': X directly after 04\n04 > X\nX: Y; Z\n")),
    ("Siblings with > and <", "examples/siblings.csx"),
    ("Chain of 40", "\n".join(f"n{i}: n{i + 1}" for i in range(40)) + "\n"),
]


def read(path):
    base = REPO if path.startswith("examples/") else ROOT                    # the examples are the repository's
    with open(path if os.path.isabs(path) else os.path.join(base, path), encoding="utf-8-sig") as fh:
        return fh.read()


def safe(text):
    if "</script" in text.lower():
        raise ValueError("embedded text must not contain </script")
    return text


def examples():
    def text(src):
        if isinstance(src, tuple):                      # the appendix base tree plus extra lines
            return read(APPENDIX).rstrip("\n") + "\n" + src[1]
        return read(src) if src.startswith("examples/") else src
    return {name: text(src) for name, src in EXAMPLES}


def page(counter="", privacy=""):
    ex = examples()
    pkg = os.path.dirname(dtree.__file__)
    parts = {
        "__DLIST_SRC__": safe(read(dlist.__file__)),
        "__DTREE_INIT__": safe(read(os.path.join(pkg, "__init__.py"))),
        "__DTREE_SRC__": safe(read(os.path.join(pkg, "core.py"))),
        "__DTREE_EULER__": safe(read(os.path.join(pkg, "euler.py"))),
        "__DTREE_TWO_LISTS__": safe(read(os.path.join(pkg, "two_lists.py"))),
        "__BRIDGE_SRC__": safe(read("dtree_explorer/bridge.py")),
        "__DTREE_VERSION__": dtree.__version__,
        "__EXPLORER_VERSION__": EXPLORER_VERSION,
        "__COUNTER__": counter,
        "__PRIVACY_URL__": privacy,
        "__EXAMPLES__": safe(json.dumps(ex, indent=1)),
        "__DEFAULT__": safe(json.dumps({"example": DEFAULT, "data": {
            f"{kind} {positions}": json.loads(bridge.encode(ex[DEFAULT], kind=kind, positions=positions))
            for kind in bridge.KINDS for positions in bridge.POSITIONS}})),
    }
    html = read("src/template.html")
    for key, value in parts.items():
        if key not in html:
            raise KeyError(key)
        html = html.replace(key, value)
    return html


def write(path, html):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    print(f"wrote {path} ({len(html) // 1024} KB)")


def main():
    write("dtree_explorer/explorer.html", page())
    write("site/index.html", page(SITE["counter"], SITE["privacy"]))
    print(f"DTree Explorer {EXPLORER_VERSION} with triordinal-dtree {dtree.__version__}")


if __name__ == "__main__":
    main()
