---
description: Apply Manas's wording edits to the Snack Arena student page (text-edits/edits.json or a described change) without breaking markup, conditions, probes or tone
argument-hint: "[edits.json path | description of the wording change]"
---

# UI text edit — Snack Arena

Apply this wording change: $ARGUMENTS
(If empty, apply `text-edits/edits.json`.)

The words on the student page live in **source**, not in HTML: mostly
`arena/sandbox/app.jsx` (one large React file) plus `.mjs` modules. Your job is
to put Manas's words into that source exactly, and change nothing else.

## Before you start

- Read the top entries of the root `CLAUDE.md` (dated record of every ruling).
  The game is called **Snack Arena** (since 2026-10-08).
- Work in a worktree (`.claude/worktrees/`), not in the `main` checkout.

## Where words live

| Surface | File |
|---|---|
| Student page | `arena/sandbox/app.jsx` (inline styles) |
| Page CSS, `.ag-*` classes, print rules | `index.html` |
| Fact sheets (also downloaded as .md) | `facts.mjs` — lines are `[label, text]` pairs |
| Decision sentences (also feed the agents' letters) | `explain.mjs` |
| Rules / practice CSV column heads | `rules-md.mjs`, `practice-csv.mjs` |
| Words the gateway sends | `arena/core/rules.mjs`, `packet.mjs` (lint), `website.mjs`, `arena/gateway/server.mjs` (refusals) |
| Instructor pages (plain HTML+JS) | `master.html`, `projector.html`, `fair.html` |
| Front door | strings in `arena/gateway/frontdoor.mjs` |

**Not copy, never touch for a wording change:** `arena/core/prompts.mjs` and
tool schemas (what the agents are told), the example packet, and any team's
uploaded website HTML (kept byte for byte).

## Steps

1. **Locate.** `node tools/text-edit/locate.mjs [edits.json]` — per edit, where
   the original words are written: whole (file:line), in pieces, or "nowhere"
   (demo data the page was showing, not our text → report, don't invent a home).
2. **Read the context of each string** before changing it:
   - *Pieces:* a sentence is often a bold label + plain text, a heading with one
     word in a red span, or interpolated counts/plurals. Keep the label in its
     node, the rest in the plain node; keep variables and plural forms.
   - *Conditions:* text can sit behind a branch (e.g. "A PDF" vs "A PDF or PPTX"
     on `cfg.deckConverts`). The editor's throwaway gateway may show a different
     branch than the class sees. Apply his words only where they are true; tell him.
   - *Matching:* the page shows `’` where source has `'` or an escape; JSX splits
     text into adjacent nodes; normalise whitespace; `white-space: pre-wrap`
     blocks keep their newlines.
3. **Apply by hand**, keeping bold, colour, markup and variables.
   - Use his words. Fix only spelling slips ("loose" → "lose") and missing final
     full stops, and list each one. Never polish, shorten or rephrase.
   - A note left on a spot ("Make it bold", "Make it scrollable") is a fix
     request, not text to paste. Change only the named thing — resize means resize only.
   - Don't propagate a rename to sibling labels/buttons/footers unasked; list the
     mismatches you left.
   - Don't add a new state, style or sentence he didn't ask for.
4. **Chase the old words.** Grep them across `arena/` and `tools/`:
   - `tools/*-probe.mjs` pin exact sentences → move the pins.
   - Scripts key on screen titles (`tools/fixtures/browser-walk.mjs`, the editor's `shell.js`).
   - `arena/market-data/market-data-guide.md` repeats page steps in its own words.
   - `aria-label`, `alt`, `title`, `placeholder` with the same words.
   - Skip `prompts.mjs` matches (see above).
5. **Banned words** on every student surface (`probe:payload`, `GRADED_WORDS`):
   graded, judged, scored, reviewed, rated, evaluated. Also never: the
   explicit/tacit framing, engine field names or JSON, private crowd numbers.
   Only exemption: `BRAND_LINE` in `facts.mjs`.
6. **Build and probe** (all zero-API, fake provider):
   `npm run build:sandbox`, then `npm run probe:steps`, `probe:payload`,
   `probe:website`, `probe:rules`, `probe:market-data`, `probe:redteam`,
   `probe:text-edit` (full list in `package.json`).
7. **Verify in a real browser.** Playwright Chromium (`~/.venvs/main/bin/python`)
   through the editor's JUMP TO stops (`POST /__edit/api/stage {"stop": id}`
   returns a team token, or drive the `#stops` select). Assert each new sentence
   is on the screen where it was edited, computed styles (bold = 700), scrolling,
   no console errors, no sideways scroll at **1366** and **390** px. Look for
   wrapped buttons, a clipped footer line, the step strip breaking, the intro page
   no longer fitting 1366×700. Read the screenshots by eye. For a download,
   download it and open it.
8. **Finish.** Restart the editor (`npm run text-edit`, port 8780, throwaway
   gateway on 8781 — run it from the Terminal panel) and archive the applied file
   to `text-edits/applied/<date>-round-N.json`.

## Never

- Call live Sonnet for copy work, or touch the class gateway on port **8787**.
- Restructure the React DOM from outside (only change the value of an existing text node).
- Use `alert` / `confirm` / `prompt` on these pages (the app's window swallows them).
- Promote to `main` unasked. When asked: merge main into the branch, re-run
  probes, `git merge --ff-only <branch>` in the main checkout, `npm run build:sandbox` there.

Page-only changes load with a rebuild and a reload; gateway code changes need
Snack Arena.app restarted.

## Report

- Each change as `old → new` with file:line.
- Every place you departed from his literal text (spelling, stops, conditional branches).
- Every sibling label you left alone and every probe pin you moved.
- What you did not verify.
