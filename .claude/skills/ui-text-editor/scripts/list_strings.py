#!/usr/bin/env python3
"""List user-facing strings in an HTML file: text, key attributes, and JS string literals."""
import re
import sys
from html.parser import HTMLParser

ATTRS = {"alt", "title", "aria-label", "placeholder", "value", "content", "label"}
SKIP = {"style"}
META_KEYS = {"description", "og:title", "og:description", "twitter:title", "twitter:description"}
JS_STR = re.compile(r"""(['"`])((?:\\.|(?!\1).){3,}?)\1""")


class Lister(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag not in ("meta", "img", "input", "br", "hr", "link"):
            self.stack.append(tag)
        a = dict(attrs)
        line = self.getpos()[0]
        for k, v in attrs:
            if k not in ATTRS or not v or not v.strip():
                continue
            if k == "content" and not (tag == "meta" and (a.get("name") in META_KEYS or a.get("property") in META_KEYS)):
                continue
            if k == "value" and a.get("type") not in ("button", "submit", "reset"):
                continue
            self.rows.append((line, "meta" if tag == "meta" else k, v.strip()))

    def handle_endtag(self, tag):
        if tag in self.stack:
            while self.stack and self.stack.pop() != tag:
                pass

    def handle_data(self, data):
        cur = self.stack[-1] if self.stack else ""
        if cur in SKIP or not data.strip():
            return
        line = self.getpos()[0]
        if cur == "script":
            for m in JS_STR.finditer(data):
                s = m.group(2)
                # Keep strings that look like prose: contain a space and a letter, no code-ish chars.
                # Leading punctuation means the regex paired a closing quote with the next opening one.
                if (" " in s and s != "use strict" and re.match(r"\s*[\w\[~¿¡\"']", s)
                        and not re.search(r"[{};=<>]", s)):
                    self.rows.append((line + data[: m.start()].count("\n"), "js-string", s))
            return
        kind = "title" if cur == "title" else "text"
        self.rows.append((line, kind, " ".join(data.split())))


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: list_strings.py FILE.html [...]")
    for path in sys.argv[1:]:
        p = Lister()
        with open(path, encoding="utf-8") as f:
            p.feed(f.read())
        for line, kind, s in p.rows:
            print(f"{path}:{line}\t{kind}\t{s}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass
