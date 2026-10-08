// Text edit overlay: click any text on the page, rewrite it, save the edits for Claude to apply.
// Injected by serve.mjs. Changes only the value of existing text nodes and attributes, never the
// DOM structure, so frameworks that own the page (React, Vue) keep working.
(() => {
  if (window.__textEdit) return;
  window.__textEdit = true;

  const API = '/__edit';
  const STORE = 'text-edit:edits';
  const DIRTY = 'text-edit:dirty';
  const ATTRS = ['placeholder', 'alt', 'aria-label', 'title', 'value'];
  const page = () => location.pathname + location.hash;

  let edits = [];
  let editing = false;
  let open = null; // { el, record }
  let serverOk = false;

  // ---------- storage ----------
  const local = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch {} },
  };
  function persist(dirty = true) {
    local.set(STORE, JSON.stringify(edits));
    local.set(DIRTY, dirty ? '1' : '');
    renderPanel();
  }
  async function loadEdits() {
    let fromServer = null;
    try {
      const r = await fetch(API + '/edits', { cache: 'no-store' });
      if (r.ok) { serverOk = true; fromServer = (await r.json()).edits || []; }
    } catch {}
    let fromLocal = [];
    try { fromLocal = JSON.parse(local.get(STORE) || '[]'); } catch {}
    edits = local.get(DIRTY) || !fromServer ? fromLocal : fromServer;
    persist(!!local.get(DIRTY));
    reapply();
  }

  // ---------- DOM helpers ----------
  const isOurs = (n) => n && (n === host || host.contains(n));
  const INLINE = new Set(['inline', 'inline-block', 'contents']);
  const BLOCKY = new Set(['BUTTON', 'A', 'LABEL', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'P', 'LI', 'TD', 'TH', 'OPTION', 'SUMMARY', 'FIGCAPTION', 'LEGEND', 'DT', 'DD']);

  function textNodes(el) {
    const out = [];
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => {
        const p = n.parentElement;
        if (!p || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(p.tagName)) return NodeFilter.FILTER_REJECT;
        return n.nodeValue.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      },
    });
    while (w.nextNode()) out.push(w.currentNode);
    return out;
  }
  function editableAttrs(el) {
    return ATTRS.filter((a) => {
      const v = el.getAttribute(a);
      if (!v || !v.trim()) return false;
      if (a === 'value') return el.tagName === 'INPUT' && /^(button|submit|reset)$/i.test(el.type);
      return true;
    });
  }
  // The clicked element, widened to its text block so "<b>Label:</b> rest" edits as one sentence.
  function blockFor(target) {
    let el = target;
    while (el && el !== document.body) {
      const disp = getComputedStyle(el).display;
      if (BLOCKY.has(el.tagName) || !INLINE.has(disp)) break;
      el = el.parentElement;
    }
    if (!el || el === document.body) el = target;
    // Too big a block (a whole card): fall back to what was clicked.
    if (textNodes(el).length > 12 && textNodes(target).length) el = target;
    return el;
  }
  function selectorFor(el) {
    const parts = [];
    while (el && el.nodeType === 1 && el !== document.documentElement) {
      if (el.id && document.querySelectorAll('#' + CSS.escape(el.id)).length === 1) {
        parts.unshift('#' + CSS.escape(el.id));
        break;
      }
      let s = el.tagName.toLowerCase();
      const sibs = el.parentElement ? [...el.parentElement.children].filter((c) => c.tagName === el.tagName) : [];
      if (sibs.length > 1) s += `:nth-of-type(${sibs.indexOf(el) + 1})`;
      parts.unshift(s);
      el = el.parentElement;
    }
    return parts.join(' > ');
  }
  // Surrounding words, so Claude can tell identical strings apart: the nearest ancestor with a bit more text.
  function contextFor(el) {
    const own = clean(el.innerText || '');
    let p = el.parentElement;
    while (p && p !== document.body && clean(p.innerText || '').length < own.length + 40) p = p.parentElement;
    const t = p && p !== document.body ? clean(p.innerText || '') : own;
    return t.length > 300 ? t.slice(0, 300) + '…' : t;
  }
  const clean = (s) => s.replace(/\s+/g, ' ').trim();
  const tagOf = (n) => {
    const p = n.parentElement;
    return p ? p.tagName.toLowerCase() : '';
  };
  // Replace a text node's words but keep its leading/trailing whitespace.
  function setText(node, words) {
    const m = node.nodeValue.match(/^(\s*)[\s\S]*?(\s*)$/);
    const next = m[1] + words + m[2];
    if (node.nodeValue !== next) node.nodeValue = next;
  }

  // ---------- applying edits to the live page ----------
  function applyRecord(rec) {
    const el = document.querySelector(rec.selector);
    if (!el) return false;
    const nodes = textNodes(el);
    let hit = false;
    for (const f of rec.fields) {
      if (f.kind === 'text') {
        // Match by original words first (survives re-renders), then by position.
        const n = nodes.find((x) => clean(x.nodeValue) === f.before) ||
          (nodes[f.index] && clean(nodes[f.index].nodeValue) === f.after ? nodes[f.index] : null);
        if (n) { setText(n, f.after); hit = true; }
      } else if (el.getAttribute(f.name) === f.before || el.getAttribute(f.name) === f.after) {
        if (el.getAttribute(f.name) !== f.after) el.setAttribute(f.name, f.after);
        if (f.name === 'value') el.value = f.after;
        hit = true;
      }
    }
    return hit;
  }
  let applying = false;
  function reapply() {
    if (applying) return;
    applying = true;
    try { for (const r of edits) if (r.page === page()) applyRecord(r); } finally { applying = false; }
  }
  let t = 0;
  new MutationObserver((muts) => {
    if (applying || muts.every((m) => isOurs(m.target))) return;
    clearTimeout(t);
    t = setTimeout(reapply, 50);
  }).observe(document.documentElement, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  addEventListener('hashchange', reapply);
  addEventListener('popstate', reapply);

  // ---------- UI ----------
  const host = document.createElement('text-edit-overlay');
  host.style.cssText = 'all:initial;position:fixed;inset:0;pointer-events:none;z-index:2147483647';
  const root = host.attachShadow({ mode: 'open' });
  root.innerHTML = `
  <style>
    :host { --ink:#16161a; --paper:#fffdf6; --accent:#ff5a1f; --muted:#6b6b76; --line:#d9d6cc; }
    * { box-sizing:border-box; font:13px/1.4 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; }
    .box { position:fixed; pointer-events:none; outline:2px solid var(--accent); outline-offset:2px; border-radius:3px;
           background:color-mix(in srgb, var(--accent) 8%, transparent); display:none; }
    .box.edited { outline-style:dashed; }
    .panel { position:fixed; right:16px; bottom:16px; max-width:calc(100vw - 32px); flex-wrap:wrap; pointer-events:auto; background:var(--ink); color:#fff;
             border-radius:12px; padding:6px; display:flex; gap:6px; align-items:center; box-shadow:0 8px 30px #0005; }
    button { cursor:pointer; border:0; border-radius:8px; padding:7px 11px; background:#ffffff1a; color:inherit; font-weight:600; }
    button:hover { background:#ffffff33; }
    button.on { background:var(--accent); color:#fff; }
    button.primary { background:#fff; color:var(--ink); }
    .status { color:#cfcfd6; padding:0 6px; flex:1 1 140px; }
    .status:empty { display:none; }
    .card { position:fixed; pointer-events:auto; width:min(420px, calc(100vw - 32px)); background:var(--paper); color:var(--ink);
            border:1px solid var(--line); border-radius:12px; padding:12px; box-shadow:0 12px 40px #0004; display:none; }
    .card h4 { margin:0 0 8px; font-weight:700; font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }
    .field { margin-bottom:8px; }
    .field label { display:block; font-size:11px; color:var(--muted); margin-bottom:3px; }
    .field label s { color:#a33; }
    textarea { width:100%; resize:vertical; min-height:38px; border:1px solid var(--line); border-radius:8px; padding:7px 8px;
               background:#fff; color:var(--ink); }
    textarea:focus { outline:2px solid var(--accent); outline-offset:0; border-color:transparent; }
    .row { display:flex; gap:6px; justify-content:flex-end; margin-top:4px; }
    .card button { background:#eceae2; color:var(--ink); }
    .card button.primary { background:var(--ink); color:#fff; }
    .list { position:fixed; right:16px; bottom:70px; pointer-events:auto; width:min(440px, calc(100vw - 32px)); max-height:60vh;
            overflow:auto; background:var(--paper); color:var(--ink); border:1px solid var(--line); border-radius:12px;
            padding:8px; box-shadow:0 12px 40px #0004; display:none; }
    .item { padding:8px; border-bottom:1px solid var(--line); }
    .item:last-child { border-bottom:0; }
    .item .old { color:#a33; text-decoration:line-through; }
    .item .new { color:#176b3a; }
    .item .meta { color:var(--muted); font-size:11px; display:flex; justify-content:space-between; gap:8px; margin-top:4px; }
    .item .meta button { padding:2px 8px; font-size:11px; background:#eceae2; color:var(--ink); }
    .empty { color:var(--muted); padding:8px; }
  </style>
  <div class="box" id="hover"></div>
  <div class="box" id="sel"></div>
  <div class="card" id="card"></div>
  <div class="list" id="list"></div>
  <div class="panel">
    <button id="toggle" title="Alt+E">✎ Edit text</button>
    <button id="count">0 edits</button>
    <button id="save" class="primary">Save</button>
    <span class="status" id="status"></span>
  </div>`;
  const $ = (id) => root.getElementById(id);
  // Keep the page's keyboard shortcuts away from our text fields.
  for (const type of ['keydown', 'keyup', 'keypress']) host.addEventListener(type, (e) => e.stopPropagation());

  function place(box, el) {
    const r = el.getBoundingClientRect();
    Object.assign(box.style, { display: 'block', left: r.left + 'px', top: r.top + 'px', width: r.width + 'px', height: r.height + 'px' });
  }
  function status(msg) { $('status').textContent = msg; }
  function renderPanel() {
    const n = edits.length;
    $('count').textContent = `${n} edit${n === 1 ? '' : 's'}`;
    $('toggle').classList.toggle('on', editing);
    if ($('list').style.display === 'block') renderList();
  }

  function setEditing(v) {
    editing = v;
    if (!v) { $('hover').style.display = 'none'; closeCard(); }
    status(v ? 'Click any text' : '');
    renderPanel();
  }
  $('toggle').onclick = () => setEditing(!editing);
  addEventListener('keydown', (e) => {
    if (e.altKey && e.code === 'KeyE') { e.preventDefault(); setEditing(!editing); }
    if (e.key === 'Escape' && editing) { open ? closeCard() : setEditing(false); }
  }, true);

  addEventListener('mousemove', (e) => {
    if (!editing || open || isOurs(e.target)) return;
    const el = e.target.nodeType === 1 ? blockFor(e.target) : null;
    if (!el || (!textNodes(el).length && !editableAttrs(el).length)) { $('hover').style.display = 'none'; return; }
    place($('hover'), el);
    $('hover').classList.toggle('edited', edits.some((r) => r.page === page() && r.selector === selectorFor(el)));
  }, true);

  // Swallow the page's own reaction to clicks while editing.
  for (const type of ['pointerdown', 'mousedown', 'mouseup', 'click', 'dblclick', 'submit']) {
    addEventListener(type, (e) => {
      if (!editing || isOurs(e.target)) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      if (type === 'click') {
        const el = blockFor(e.target);
        if (textNodes(el).length || editableAttrs(el).length) openCard(el);
      }
    }, true);
  }

  // ---------- the edit card ----------
  function openCard(el) {
    const sel = selectorFor(el);
    const existing = edits.find((r) => r.page === page() && r.selector === sel);
    const nodes = textNodes(el);
    const attrs = editableAttrs(el);
    open = { el, sel, nodes, attrs, existing };
    $('hover').style.display = 'none';
    place($('sel'), el);

    const fieldFor = (key) => existing && existing.fields.find((f) => f.key === key);
    const many = nodes.length > 1;
    let html = `<h4>${many ? 'Edit each piece (keeps bold, links and colour)' : 'Edit text'}</h4>`;
    nodes.forEach((n, i) => {
      const prior = fieldFor('t' + i);
      const before = prior ? prior.before : clean(n.nodeValue);
      const tag = tagOf(n);
      const label = many ? `Piece ${i + 1}${tag && tag !== el.tagName.toLowerCase() ? ` · &lt;${tag}&gt;` : ''}` : '';
      html += `<div class="field">${label ? `<label>${label}${prior ? ` · was <s>${esc(before)}</s>` : ''}</label>` : prior ? `<label>was <s>${esc(before)}</s></label>` : ''}
        <textarea data-key="t${i}" data-before="${esc(before)}" rows="${Math.min(6, Math.ceil(before.length / 48) || 1)}">${esc(clean(n.nodeValue))}</textarea></div>`;
    });
    for (const a of attrs) {
      const prior = fieldFor('a:' + a);
      const before = prior ? prior.before : el.getAttribute(a);
      html += `<div class="field"><label>${a} attribute${prior ? ` · was <s>${esc(before)}</s>` : ''}</label>
        <textarea data-key="a:${a}" data-before="${esc(before)}" rows="1">${esc(el.getAttribute(a))}</textarea></div>`;
    }
    html += `<div class="field"><label>Note for Claude (optional, e.g. “make it bold”, “shorter on mobile”)</label>
        <textarea data-key="note" rows="1">${esc(existing?.note || '')}</textarea></div>
      <div class="row">
        ${existing ? '<button id="revert">Revert</button>' : ''}
        <button id="cancel">Cancel</button><button id="ok" class="primary">Done</button>
      </div>`;
    const card = $('card');
    card.innerHTML = html;
    card.style.display = 'block';
    const r = el.getBoundingClientRect();
    const h = card.offsetHeight;
    const top = r.bottom + 10 + h < innerHeight ? r.bottom + 10 : Math.max(10, r.top - h - 10);
    card.style.top = top + 'px';
    card.style.left = Math.min(Math.max(10, r.left), innerWidth - card.offsetWidth - 10) + 'px';
    const first = card.querySelector('textarea');
    first.focus();
    first.select();
    card.querySelectorAll('textarea').forEach((ta) => ta.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) commit();
    }));
    $('ok').onclick = commit;
    $('cancel').onclick = closeCard;
    if (existing) $('revert').onclick = () => revert(existing);
  }
  function closeCard() {
    open = null;
    $('card').style.display = 'none';
    $('sel').style.display = 'none';
  }
  function commit() {
    const { el, sel, nodes, existing } = open;
    const fields = [];
    let note = '';
    $('card').querySelectorAll('textarea').forEach((ta) => {
      const key = ta.dataset.key;
      const after = key === 'note' ? ta.value.trim() : clean(ta.value);
      if (key === 'note') { note = after; return; }
      const before = ta.dataset.before;
      if (after === before) return;
      if (key.startsWith('t')) {
        const i = +key.slice(1);
        fields.push({ key, kind: 'text', index: i, tag: tagOf(nodes[i]), before, after });
      } else {
        fields.push({ key, kind: 'attr', name: key.slice(2), before, after });
      }
    });
    const all = (k) => nodes.map((n, i) => {
      const f = fields.find((x) => x.key === 't' + i);
      return f ? f[k] : clean(n.nodeValue);
    }).join(' ');
    const beforeText = nodes.map((n, i) => {
      const f = fields.find((x) => x.key === 't' + i) || existing?.fields.find((x) => x.key === 't' + i);
      return f ? f.before : clean(n.nodeValue);
    }).join(' ');
    edits = edits.filter((r) => r !== existing);
    if (existing) applyRecord({ ...existing, fields: existing.fields.map((f) => ({ ...f, after: f.before, before: f.after })) });
    if (fields.length || note) {
      const rec = {
        id: existing?.id || Math.random().toString(36).slice(2, 10),
        page: page(),
        url: location.href,
        selector: sel,
        element: el.tagName.toLowerCase(),
        before: clean(beforeText),
        after: clean(all('after')),
        fields,
        note,
        context: contextFor(el),
        viewport: `${innerWidth}x${innerHeight}`,
        at: new Date().toISOString(),
      };
      edits.push(rec);
      applyRecord(rec);
      status('Edited · not saved yet');
    }
    persist();
    closeCard();
  }
  function revert(rec) {
    applyRecord({ ...rec, fields: rec.fields.map((f) => ({ ...f, before: f.after, after: f.before })) });
    edits = edits.filter((r) => r !== rec);
    persist();
    closeCard();
    status('Reverted · not saved yet');
  }

  // ---------- list of edits ----------
  $('count').onclick = () => {
    const l = $('list');
    l.style.display = l.style.display === 'block' ? 'none' : 'block';
    renderList();
  };
  function renderList() {
    const l = $('list');
    if (!edits.length) { l.innerHTML = '<div class="empty">No edits yet. Turn on ✎ Edit text and click any text.</div>'; return; }
    l.innerHTML = edits.map((r, i) => `<div class="item">
      ${r.before !== r.after ? `<div class="old">${esc(r.before)}</div><div class="new">${esc(r.after)}</div>` : ''}
      ${r.fields.filter((f) => f.kind === 'attr').map((f) => `<div>${f.name}: <span class="old">${esc(f.before)}</span> → <span class="new">${esc(f.after)}</span></div>`).join('')}
      ${r.note ? `<div>📝 ${esc(r.note)}</div>` : ''}
      <div class="meta"><span>${esc(r.page)}</span><span><button data-go="${i}">Show</button> <button data-undo="${i}">Undo</button></span></div>
    </div>`).join('');
    l.querySelectorAll('[data-undo]').forEach((b) => (b.onclick = () => {
      const rec = edits[+b.dataset.undo];
      if (rec.page === page()) applyRecord({ ...rec, fields: rec.fields.map((f) => ({ ...f, before: f.after, after: f.before })) });
      edits.splice(+b.dataset.undo, 1);
      persist();
    }));
    l.querySelectorAll('[data-go]').forEach((b) => (b.onclick = () => {
      const rec = edits[+b.dataset.go];
      if (rec.page !== page()) { location.href = rec.url; return; }
      const el = document.querySelector(rec.selector);
      if (!el) { status('Not on screen right now'); return; }
      el.scrollIntoView({ block: 'center' });
      setTimeout(() => { place($('sel'), el); setTimeout(() => ($('sel').style.display = 'none'), 1500); }, 300);
    }));
  }

  // ---------- save ----------
  $('save').onclick = async () => {
    const body = JSON.stringify({ origin: location.origin, savedAt: new Date().toISOString(), edits }, null, 2);
    try {
      const r = await fetch(API + '/save', { method: 'POST', headers: { 'content-type': 'application/json' }, body });
      if (!r.ok) throw new Error(r.status);
      const { path } = await r.json();
      persist(false);
      status(`Saved ${edits.length} → ${path}. Ask Claude: /text-edit apply`);
    } catch {
      // No server (e.g. bookmarklet on another site): hand over a file instead.
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([body], { type: 'application/json' }));
      a.download = 'edits.json';
      root.appendChild(a);
      a.click();
      a.remove();
      status('Downloaded edits.json — put it in text-edits/ and run /text-edit apply');
    }
  };
  window.addEventListener('beforeunload', (e) => {
    if (local.get(DIRTY) && edits.length && serverOk) { e.preventDefault(); e.returnValue = ''; }
  });

  function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  const mount = () => { document.documentElement.appendChild(host); renderPanel(); loadEdits(); };
  document.readyState === 'loading' ? addEventListener('DOMContentLoaded', mount) : mount();
})();
