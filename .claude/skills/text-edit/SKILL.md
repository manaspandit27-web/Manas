---
name: text-edit
description: Click-to-edit text overlay for a website. "/text-edit" opens the site in the browser with an editor on top, so the user can click any text (headings, buttons, labels, placeholders, alt text) and rewrite it, then Save. "/text-edit apply" has Claude apply the saved edits (text-edits/edits.json) to the real source files. Use when the user wants to edit copy or UI text visually, says "open the text editor", or says "apply my edits".
argument-hint: "[start [dir | dev-server URL] | apply [edits.json]]"
---

# Text edit

Two halves. The user edits words visually in their browser; you put those words
into the source.

The tool files sit next to this SKILL.md (this skill's base directory):
`serve.mjs` (server that injects the overlay and saves edits), `overlay.js`
(the editor), and `locate.mjs` (finds where each original sentence is written).
Node 18+ only, no installs. Below, `$SKILL` means that directory.

Arguments: `$ARGUMENTS`. Empty or `start …` means **Start**. `apply …` means **Apply**.

---

## Start: open the editor

1. Work out how the site is served:
   - **Plain HTML folder:** `node $SKILL/serve.mjs --root <folder>`
   - **App with a dev server** (Vite, Next, CRA…): start the dev server if it
     isn't running, then `node $SKILL/serve.mjs --proxy http://localhost:<devport>`.
     Hot reload passes through.
   - If the user gave a folder or URL, use it.

   Run it from the project root, in the background, with `--port 8780` (pick
   another if busy). Edits save to `text-edits/edits.json` in the project root
   (`--out` to change). Never point it at a production or shared server.
2. Give the user the link (`http://localhost:8780/…`) and these instructions:
   - Turn on **✎ Edit text** (bottom right, or Alt+E). Clicks stop working as
     page clicks while it's on; turn it off to move around the site, then on again.
   - Click any text. A card shows each piece of the sentence separately
     (a bold label, a coloured word, a link) so the styling survives. Placeholders,
     alt text and button labels show as their own fields.
   - Optional **Note for Claude**: anything that isn't a wording change
     ("make it bold", "too long on mobile").
   - **N edits** lists everything with Show / Undo. **Save** writes the file.
     Edits survive reloads.
   - When done, run `/text-edit apply`.
3. If the user is on another machine than the server, say so: the overlay needs
   to be opened where the server runs. Fallback without the server: Save
   downloads `edits.json`; put it at `text-edits/edits.json`.

---

## Apply: put the saved edits into the source

The page the user edited is the *output*. The words live in source: HTML,
JSX/TSX, Vue/Svelte templates, `.mjs` modules, markdown, translation files.

1. **Read the file.** `text-edits/edits.json` (or the path given). Each edit has
   `before`/`after` for the whole sentence, `fields` (each changed text piece or
   attribute, with `tag` of its wrapper), `note`, `page`, `selector`, `context`
   (nearby words) and `viewport`.
2. **Find each sentence.** `node $SKILL/locate.mjs text-edits/edits.json`
   reports per edit: **WHOLE** (file:line), **PIECES** (the sentence is split
   across nodes or around `{variables}`), or **NOWHERE** (data the page was
   showing, or text built at runtime). For NOWHERE, tell the user; don't invent
   a home. When a sentence appears several times, use `page`, `selector` and
   `context` to pick the right one; list the others.
3. **Read the source around each string before changing it.**
   - *Pieces:* a sentence is often a bold label + plain text, or a heading with
     one word in a coloured span. Put each piece's new words in its own node.
     Never fold a rewrite into the first node (it turns the whole line bold).
   - *Variables and plurals:* the page showed `111`; source has `{n}`. Keep the
     variable and plural logic; change only the words around them.
   - *Conditions:* a string can sit in a branch (`cond ? "A PDF" : "A PDF or PPTX"`).
     The user saw only one branch. Apply their words where they're true and say
     what you did with the other branch.
   - *Matching quirks:* the page shows `’` where source has `'` or `&rsquo;`;
     whitespace is collapsed; `pre-wrap` text keeps its newlines.
4. **Apply exactly their words.**
   - Fix only obvious slips (spelling, a missing final full stop) and list each one.
     Never polish, shorten or rephrase.
   - A note is a request for a change, not text to paste. Do exactly what it
     names (resize means resize only).
   - Don't spread a rename to sibling labels, buttons or footers unless asked;
     list the ones you left alone.
   - Keep markup, classes, styling and variables. Don't add new states, styles or sentences.
   - Escape properly for the file type (HTML entities in attributes, quotes in
     JS strings and template literals, `{`/`}` in JSX text).
5. **Chase the old words.** Grep each old sentence across the repo:
   - tests and snapshots that pin exact text: update them in step;
   - scripts or selectors that match on visible text;
   - docs or guides that repeat it;
   - `aria-label`, `alt`, `title`, `placeholder` twins of the same words.
   Leave agent/LLM prompt text, API schemas and fixture data alone unless the
   user said so; those are not UI copy. If the project has a `CLAUDE.md` with
   banned words or copy rules, follow it.
6. **Check.** Run the project's own build, lint and tests. Then render the
   changed pages (Playwright/Chromium, or the user's browser via the editor) at
   desktop (1366px) and phone (390px) width. Look for each new sentence on the
   right screen, wrapped or clipped buttons, overflow, sideways scroll, console
   errors. Look at the screenshots yourself.
7. **Archive.** Move the applied file to `text-edits/applied/<date>-round-N.json`
   so the editor starts empty next time (the overlay reloads from the server
   file). Suggest adding `text-edits/` to `.gitignore` if the user doesn't want it
   committed.
8. **Report** in a short list: each change `old → new` with file:line; every
   departure from their literal text; notes and how you handled them; NOWHERE
   edits; sibling labels left alone; tests updated; what you didn't verify.

Never use `alert`/`confirm`/`prompt` to talk to the user from the page, never
restructure a framework's DOM from outside, and never push or deploy unless asked.
