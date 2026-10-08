#!/usr/bin/env node
/* locate.mjs — WHERE EACH SAVED EDIT LIVES IN THE SOURCE (the first step of applying text-edits/edits.json).
   Ported from the Snack Arena text editor (tools/text-edit/locate.mjs).

   The editor (server.mjs) records the words as the page SHOWED them. The source writes many of them in pieces: a sentence
   with a number in it, a word set in bold or in colour, a heading built from a variable, a line the server sends. This reads
   the edits file and says, for each edit, where its words are written — the whole sentence where it stands whole, otherwise
   the longest pieces of it, each with its file and line — so the change can be made by hand in the right place. An edit none
   of whose words are in the source is data the page was showing (a name, a price, a user's post), not the site's own text.

     node locate.mjs [text-edits/edits.json] [--root .] [--json]

   It searches every text file under --root (default: the current folder), skipping dependencies, build output and dot folders. */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const args = process.argv.slice(2), asJson = args.includes("--json"), ri = args.indexOf("--root"), root = resolve(ri >= 0 ? args[ri + 1] : ".");
const file = args.find((a, i) => !a.startsWith("--") && args[i - 1] !== "--root") || join("text-edits", "edits.json");
/* everything the site can show words from: its pages, components, modules, templates, content and translation files */
const SKIP = new Set(["node_modules", "dist", "build", "out", "coverage", "vendor", "text-edits", "__pycache__", "venv", "target"]);
const TEXT = /\.(html?|jsx?|tsx?|mjs|cjs|vue|svelte|astro|md|mdx|json|ya?ml|toml|php|erb|hbs|ejs|njk|liquid|twig|py|rb|go|swift|kt|java|strings|po|xml|txt|csv)$/i;
const SOURCES = [];
(function walk(dir) {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    if (e.name.startsWith(".") || SKIP.has(e.name)) continue;
    const p = join(dir, e.name);
    if (e.isDirectory()) walk(p);
    else if (TEXT.test(e.name) && !/\.min\.|\.map$|lock\.json$|\.lock$/.test(e.name) && statSync(p).size < 4e6) SOURCES.push(relative(root, p));
  }
})(root);
const texts = SOURCES.map((f) => ({ f, s: readFileSync(join(root, f), "utf8") }));
const lineOf = (s, at) => s.slice(0, at).split("\n").length;
const spots = (needle, max = 6) => { const out = []; for (const { f, s } of texts) for (let at = s.indexOf(needle); at >= 0 && out.length < max; at = s.indexOf(needle, at + 1)) out.push(`${f}:${lineOf(s, at)}`); return out; };
const anywhere = (needle) => texts.some(({ s }) => s.includes(needle));
/* the page shows ’ where the source may write ' or &apos;, and a non-breaking space where it writes a plain one */
const spellings = (t) => [...new Set([t, t.replace(/[’‘]/g, "'"), t.replace(/'/g, "’"), t.replace(/[“”]/g, '"'), t.replace(/ /g, " "), t.replace(/'/g, "\\'"), t.replace(/"/g, '\\"')])];
function pieces(original) { // the longest runs of the words that are written somewhere, left to right
  const out = []; let i = 0;
  while (i < original.length) {
    let len = 0; for (let L = original.length - i; L >= 6; L--) if (spellings(original.slice(i, i + L)).some(anywhere)) { len = L; break; }
    if (!len) { i++; continue; }
    const words = original.slice(i, i + len); if (words.trim().length >= 6) out.push({ words, at: spots(spellings(words).find(anywhere), 4) }); i += len;
  }
  return out;
}

let edits = []; try { edits = JSON.parse(readFileSync(file, "utf8")).edits || []; } catch (e) { console.error(`no edits file at ${file} (${e.message})`); process.exit(1); }
const report = edits.map((e, i) => {
  const whole = spellings(e.original).map((t) => spots(t)).find((a) => a.length) || [], parts = whole.length ? [] : pieces(e.original);
  return { n: i + 1, kind: e.kind, where: [e.page, e.screen, e.layer, ...(e.where || []).slice(0, 1)].filter(Boolean).join(" · "), original: e.original, text: e.text, note: e.note, html: e.html, whole, parts, found: whole.length ? "whole" : parts.length ? "in pieces" : "nowhere: data the page was showing, or words built entirely from values" };
});
if (asJson) console.log(JSON.stringify(report, null, 2));
else {
  for (const r of report) {
    console.log(`\n#${r.n}  ${r.where || "—"}${r.kind !== "text" ? `   [${r.kind}]` : ""}`);
    if (r.text !== r.original) console.log(`  was: ${r.original}\n  now: ${r.text || "(removed)"}`); else console.log(`  the words: ${r.original}`);
    if (r.note) console.log(`  NOTE: ${r.note}`);
    if (r.whole.length) console.log(`  written whole at: ${r.whole.join("  ")}`);
    else if (r.parts.length) { console.log(`  written in pieces${r.html && /</.test(r.html) ? ` (as built: ${r.html})` : ""}:`); for (const p of r.parts) console.log(`    “${p.words.trim()}”  ${p.at.join("  ")}`); }
    else console.log(`  ${r.found}`);
  }
  const n = (k) => report.filter((r) => r.found.startsWith(k)).length;
  console.log(`\n${report.length} edit(s): ${n("whole")} written whole, ${n("in pieces")} in pieces, ${n("nowhere")} not in the source. (searched ${SOURCES.length} files under ${relative(process.cwd(), root) || "."})`);
}
