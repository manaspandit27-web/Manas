---
name: text-edit
description: The click-to-rewrite text editor from Snack Arena, for any website. "/text-edit" opens the real site in Chrome inside a frame with a toolbar, so the user can click any text, rewrite it in place, leave a note for Claude, and SAVE to text-edits/edits.json. "/text-edit apply" has Claude apply those saved edits to the source. Use when the user wants to edit a site's words visually, says "open the text editor", or says "apply my edits".
argument-hint: "[start [folder | dev-server URL] | apply [edits.json]]"
---

# Text edit

Two halves. The user edits words on their real site in Chrome. You put those
words into the source.

The tool files sit next to this SKILL.md, in this skill's base directory
(called `$SKILL` below). They are ported from the Snack Arena editor
(`tools/text-edit/`), with the Snack Arena-only parts removed (JUMP TO, DO THIS
STEP FOR ME, the throwaway gateway):
- `server.mjs` puts the site in a same-origin frame and saves edits.
- `shell.html` and `shell.js` are the toolbar and editor around the frame.
- `locate.mjs` finds where each original sentence is written in the source.

You need Node 18+. There is nothing to install.

Arguments: `$ARGUMENTS`. Empty or `start …` means **Start**. `apply …` means **Apply**.

---

## Start: open the editor

1. **Work out what to frame.**
   - An app with a dev server (Vite, Next, CRA, a Node server): make sure it's
     running, then use `--proxy http://localhost:<its port>`. Streams and hot
     reload pass through. Headers that forbid framing (`X-Frame-Options`,
     CSP `frame-ancestors`) are dropped, since the frame is the point.
   - A folder of HTML files: use `--root <folder>`.
   - If the user named a folder or URL, use that. Never point it at a
     production or shared server, only at the user's own local copy.
2. **Run it from the project root as a long-lived background terminal process**,
   not as an app preview server (those get stopped mid-session, while the user's
   tab is still open):
   `node $SKILL/server.mjs --proxy http://localhost:5173` (or `--root .`)
   Options: `--port 8780` (default), `--out text-edits/edits.json` (default).
3. **Open it in Chrome:** `open -a "Google Chrome" http://localhost:8780/` on a
   Mac. Otherwise, give the user the link. Use Chrome; the built-in browser pane
   can't open file choosers or dialogs, and Firefox is untested.
4. **Tell the user how it works.** The **?** button shows this too.
   - **Click any text** to rewrite it. **⏎** keeps it, **esc** cancels.
     The page changes at once, wherever those same words appear.
   - **Buttons, links and boxes still work.** Hold **⌥ (option)** and click one
     to rewrite its words, or the grey hint inside an empty box.
   - Each rewrite can carry a **note for Claude** ("make it bold", "remove this
     box"). A note alone, with the words left as they are, is kept too.
   - Move around with the site's own links. **ALL EDITS** lists everything,
     with UNDO and a JSON download.
   - **SAVE** writes `text-edits/edits.json`, keeping the previous one as `.bak`.
     Until then, the browser keeps the rewrites.
   - **EDITING: OFF** shows the site exactly as a visitor sees it.
   - When done: SAVE, then `/text-edit apply`.

What it can't reach: text in canvas or SVG, CSS pseudo-elements, native
dropdown options and tooltips, and cross-origin frames. Edits are keyed by
the words, so the same words change everywhere they appear.

---

## Apply: put the saved edits into the source

1. **Read** `text-edits/edits.json` (or the path given). Each edit has:
   - `original` (the words as the page showed them) and `text` (the words they should be);
   - `kind`: `text`, `pre` (newlines matter) or `placeholder`;
   - `note`: an instruction about that spot, not words to paste;
   - where it stood: `page`, `screen` (the first heading), `layer` (dialog,
     header, footer, side panel), `where` (headings above it), `tag`, `path`, `viewport`;
   - `html`: how the original was built, with its inline tags, e.g.
     `<strong>Shoppers:</strong> about 111…`.
2. **Locate:** `node $SKILL/locate.mjs text-edits/edits.json` (add `--root <src>`
   to narrow the search). For each edit it reports one of three results:
   - **written whole** at a file and line;
   - **in pieces**: the longest runs of the words, each with its file and line;
   - **nowhere**: data the page was showing, or words built from values. Tell
     the user; don't invent a home for these.
3. **Read the source around each string before changing it.**
   - **Pieces:** a sentence is often a bold label plus plain text, or a heading
     with one coloured word. Keep each piece in its own element, as `html`
     shows. Never fold a rewrite into the first piece, which makes the whole
     line bold. The user noticed exactly this in Snack Arena.
   - **Variables and plurals:** the page showed `111` where the source has `{n}`.
     Keep the variable and the plural logic, and change only the words around them.
   - **Conditions:** a string can sit in a branch, like
     `cond ? "A PDF" : "A PDF or PPTX"`, and the user only saw one branch. Apply
     their words where they're true, and say what you did with the other branch.
   - **Matching:** the page shows `’` where the source has `'`, `&rsquo;` or an
     escape. Whitespace is collapsed, except that `pre` keeps its newlines.
4. **Apply exactly their words.**
   - Fix only slips (spelling, a missing final full stop), and list each one.
     Never polish, shorten or rephrase.
   - A note asks for a change: do exactly what it names, and nothing more.
   - Don't spread a rename to sibling labels, buttons or footers unless asked.
     List the ones you left.
   - Keep markup, classes, styles and variables. Don't add states, styles or
     sentences they didn't ask for.
   - Escape correctly for the file type: HTML entities, quotes in JS strings,
     `{`/`}` in JSX text.
5. **Chase the old words.** Grep each old sentence across the repo:
   - tests and snapshots that pin exact text: move those pins;
   - scripts or selectors that match visible text;
   - docs that repeat it;
   - `aria-label`, `alt`, `title` and `placeholder` twins of the same words.

   Leave LLM prompt text, API schemas and fixture data alone; those aren't UI
   copy. If the project's `CLAUDE.md` has copy rules or banned words, follow them.
6. **Check:**
   - Run the project's build, lint and tests.
   - Restart the editor if the page is built at start, and tell the user to
     **reload their tab**. A tab from before the change shows the old page.
   - Look at each changed page at 1366px and 390px wide: each new sentence is
     where it was edited, with no wrapped or clipped buttons, no sideways
     scroll, and no console errors. Look at the screenshots yourself.
7. **Archive** the applied file to `text-edits/applied/<date>-round-N.json`, so
   the editor starts empty next round.
8. **Report**, as a short list:
   - each change as `old → new`, with file:line;
   - every departure from their literal words;
   - **where each note landed** and what you did about it;
   - edits found nowhere;
   - sibling labels left alone;
   - test pins moved;
   - what you didn't verify.

Never use `alert`, `confirm` or `prompt` on the page. Never restructure a
framework's DOM from outside. Never push, deploy or merge to main unless asked.
