---
name: ui-text-editor
description: Edit user-facing text in HTML pages and UI code — headings, body copy, buttons, labels, placeholders, alt text, aria-labels, <title>/meta tags, toasts, error and empty states. Use whenever the user asks to change, rewrite, fix, shorten, translate or proofread wording on a website or app UI, even for a one-word change, so the edit stays minimal, consistent across pages, accessible, and does not break markup or scripts.
---

# UI text editor

Change what people read on a page without changing anything else.

## 1. Find every copy of the text

Wording rarely lives in one place. Before editing, list all strings on the page:

```bash
python3 .claude/skills/ui-text-editor/scripts/list_strings.py index.html
```

It prints each string with its line number and kind (text, title, meta, alt,
aria-label, placeholder, value, js-string). Then grep for the exact phrase and
close variants across the project, since the same copy often appears in:
- visible text and its `alt` / `aria-label` / `title` twin
- `<title>`, `meta[name=description]`, `og:*` / `twitter:*` tags
- JS strings that set text at runtime (`textContent`, template literals, toasts)
- README or other pages that should stay in step

## 2. Edit minimally

- Change only the text node or attribute value. Never reformat, reindent or
  reorder surrounding markup, and keep classes, ids and data attributes as they are.
- Keep entities and encoding valid: escape `&`, `<`, `"` inside attributes, keep
  `&nbsp;`/`&mdash;` where they were intentional, and preserve UTF-8 characters.
- In JS strings, match the quote style and escape quotes and backticks; don't
  put `${` inside template literals by accident.
- Don't touch text inside `<script>`/`<style>` unless it is clearly copy shown to users.
- If the same phrase appears in several places, change all of them or say which you left and why.

## 3. Keep the voice consistent

- Before rewriting, read nearby copy to match its tone, tense, person, and
  capitalisation (sentence case vs Title Case for buttons and headings).
- Reuse the project's existing words for things (don't call a "room" a "scene" on one page).
- Buttons say what happens ("Play sound", not "OK"). Errors say what went wrong and what to do next.
- Prefer shorter. If the new text is noticeably longer than the old one, check the layout.

## 4. Accessibility

- When visible text changes meaning, update the matching `alt`, `aria-label`
  and `title` too. Decorative images keep `alt=""`.
- Don't remove or empty an accessible name. Link text should make sense on its own.

## 5. Verify

1. Re-run `list_strings.py` and diff against the earlier output: only the intended strings should differ.
2. Check the HTML still parses: `python3 -c "import html.parser,sys; html.parser.HTMLParser().feed(open(sys.argv[1]).read())" index.html`
3. Render the page (Playwright/Chromium is available) at desktop and ~375px
   width and screenshot the changed areas. Look for overflow, wrapping, clipped
   buttons and text that JS overwrites after load.
4. Report each change as `old → new` with its file and line.

## Never

- Never change wording the user didn't ask about, except identical copies of the same string (say so).
- Never "fix" spelling or style in proper nouns, brand names, code, or quoted material.
- Never edit minified or generated files by hand when a source file exists; edit the source.
