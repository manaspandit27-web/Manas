#!/usr/bin/env node
// For each saved edit, find where its original words are written in the source.
//   node locate.mjs [text-edits/edits.json] [--root .]
// Reports each edit as: whole (file:line), pieces (each text piece's file:line), or nowhere.
import fs from 'node:fs';
import path from 'node:path';

const argv = process.argv.slice(2);
const rootIdx = argv.indexOf('--root');
const ROOT = path.resolve(rootIdx >= 0 ? argv[rootIdx + 1] : '.');
const file = argv.find((a, i) => !a.startsWith('--') && argv[i - 1] !== '--root') || 'text-edits/edits.json';
const { edits = [] } = JSON.parse(fs.readFileSync(file, 'utf8'));

const SKIP = new Set(['node_modules', 'dist', 'build', 'out', 'coverage', 'text-edits', 'vendor']);
const EXT = /\.(html?|jsx?|tsx?|mjs|cjs|vue|svelte|astro|md|mdx|json|ya?ml|php|erb|hbs|ejs|liquid|py|rb|txt|strings|po|xml)$/i;
const files = [];
(function walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name.startsWith('.') || SKIP.has(e.name)) continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p);
    else if (EXT.test(e.name) && fs.statSync(p).size < 3e6 && !/\.min\./.test(e.name) && !/lock\.json$/.test(e.name)) files.push(p);
  }
})(ROOT);

// Compare as the browser shows it: entities decoded, curly quotes straightened, whitespace collapsed.
const ENT = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', rsquo: "'", lsquo: "'", rdquo: '"', ldquo: '"', mdash: '—', ndash: '–', hellip: '…' };
const norm = (s) => s
  .replace(/&(#x?[0-9a-f]+|\w+);/gi, (m, e) => e[0] === '#' ? String.fromCodePoint(e[1].toLowerCase() === 'x' ? parseInt(e.slice(2), 16) : +e.slice(1)) : ENT[e.toLowerCase()] ?? m)
  .replace(/\\u([0-9a-f]{4})/gi, (_, h) => String.fromCharCode(parseInt(h, 16)))
  .replace(/\\(['"`])/g, '$1')
  .replace(/[‘’]/g, "'").replace(/[“”]/g, '"').replace(/ /g, ' ')
  .replace(/\s+/g, ' ')
  .toLowerCase();

// Normalised text of each file plus a map back to line numbers.
const corpus = files.map((f) => {
  const raw = fs.readFileSync(f, 'utf8');
  const lines = raw.split('\n');
  let text = '';
  const lineAt = [];
  lines.forEach((l, i) => { const n = norm(l) + ' '; text += n; for (let k = 0; k < n.length; k++) lineAt.push(i + 1); });
  return { f: path.relative(process.cwd(), f), text, lineAt };
});

function find(words) {
  const q = norm(words).trim();
  if (q.length < 2) return [];
  const hits = [];
  for (const c of corpus) {
    let i = c.text.indexOf(q);
    while (i >= 0 && hits.length < 8) { hits.push(`${c.f}:${c.lineAt[i]}`); i = c.text.indexOf(q, i + 1); }
  }
  return hits;
}

let n = 0;
for (const e of edits) {
  n++;
  console.log(`\n#${n} [${e.id}] ${e.page} ${e.selector}`);
  if (e.before !== e.after) console.log(`  "${e.before}"\n  → "${e.after}"`);
  for (const f of e.fields.filter((x) => x.kind === 'attr')) console.log(`  ${f.name}: "${f.before}" → "${f.after}"`);
  if (e.note) console.log(`  note: ${e.note}`);

  const whole = e.before ? find(e.before) : [];
  if (whole.length) { console.log(`  WHOLE   ${whole.join('  ')}`); }
  const pieces = e.fields.filter((f) => f.kind === 'text');
  if (!whole.length && e.before) {
    // Try each piece, and for one long piece, its sentences (JSX often splits around {variables}).
    const parts = pieces.length > 1 ? pieces.map((p) => p.before) : e.before.split(/(?<=[.!?:])\s+|\s*\{[^}]*\}\s*|\s*\d[\d,.]*\s*/).filter((s) => s.trim().length > 3);
    const found = parts.map((p) => [p, find(p)]);
    if (found.some(([, h]) => h.length)) {
      console.log('  PIECES');
      for (const [p, h] of found) console.log(`    "${p}"  ${h.length ? h.join('  ') : 'not found'}`);
    } else {
      console.log('  NOWHERE (likely data the page was showing, or built at runtime; ask before inventing a home)');
    }
  }
  for (const f of e.fields.filter((x) => x.kind === 'attr')) {
    const h = find(f.before);
    console.log(`  ${f.name} ${h.length ? h.join('  ') : 'not found'}`);
  }
  // Same words elsewhere (tests, docs, aria twins) need a look too.
  const others = e.before ? find(e.before).length : 0;
  if (others > 1) console.log(`  NOTE: appears ${others}× — check each (tests, docs, duplicates)`);
}
console.log(`\n${n} edit(s) from ${file}, searched ${files.length} files under ${path.relative(process.cwd(), ROOT) || '.'}`);
