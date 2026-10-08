/* shell.js — the editor round the site (server.mjs says what this is for). Ported from the Snack Arena text editor.

   THE PAGE IN THE FRAME IS NEVER REBUILT BY THIS SCRIPT. React owns every node of it, and a node it did not make, or one that
   has gone missing, breaks its next update. So a rewrite changes exactly one thing: the VALUE of text nodes that are already
   there (`spread` says which node takes which words, so a bold label stays the only bold thing in its sentence). React never looks at a text node's value
   unless its own text for that node changes, so the page keeps working under the rewrites, and when it does write new text
   into a node, that text is the new original.

   A UNIT is what one click opens: a run of text as a reader sees it — the nearest box that is not inline (a paragraph, a
   heading, a button, a table cell), with the words of every inline element inside it (<b>, <span>, a link). An edit is keyed
   by the unit's words as the page first showed them, so the same words are rewritten wherever they appear, on this screen or
   another, and again after the page draws them anew. */
(() => {
  const $ = (id) => document.getElementById(id);
  const frame = $("frame"), hover = $("hover"), hoverTag = $("hoverTag"), ed = $("editor"), ta = $("edText"), was = $("edWas"), noteBox = $("edNote");
  const LOCAL = "text-edit-edits";
  const norm = (s) => String(s == null ? "" : s).replace(/\s+/g, " ").trim();
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  const keyOf = (kind, original) => `${kind}\u0001${original}`;
  let fwin = null, fdoc = null, observer = null, on = true, editing = null, dirty = false, file = "text-edits/edits.json";
  const edits = new Map(); // key → { key, kind, original, text, note, page, screen, layer, where, tag, path, html, at }
  let applied = new WeakMap(), phOrig = new WeakMap(), inlineCache = new WeakMap(), preCache = new WeakMap(), anyApplied = false;

  /* ---------- what a unit is ---------- */
  const SKIP = "script,style,noscript,textarea,select,option,title";
  const isInline = (el) => { let v = inlineCache.get(el); if (v === undefined) { const d = fwin.getComputedStyle(el).display; v = d === "inline" || d === "contents"; inlineCache.set(el, v); } return v; };
  const isPre = (el) => { let v = preCache.get(el); if (v === undefined) { v = /^pre/.test(fwin.getComputedStyle(el).whiteSpace); preCache.set(el, v); } return v; };
  const unitOf = (node) => { let el = node.nodeType === 3 ? node.parentElement : node; while (el && el !== fdoc.body && isInline(el)) el = el.parentElement; return el; };
  const origOf = (n) => { const a = applied.get(n); if (a) { if (n.nodeValue === a.shown) return a.orig; applied.delete(n); } return n.nodeValue; }; // a value that is no longer the one put there is the page's own new text
  const textsIn = (unit) => { const out = [], w = fdoc.createTreeWalker(unit, 4); for (let n = w.nextNode(); n; n = w.nextNode()) { if (n.parentElement.closest(SKIP)) continue; if (unitOf(n) === unit) out.push(n); } return out; };
  const readUnit = (unit, texts = textsIn(unit)) => { const raw = texts.map(origOf).join(""), pre = isPre(unit); return { el: unit, texts, raw, pre, kind: pre ? "pre" : "text", original: pre ? raw : norm(raw) }; };

  /* ---------- the rewrites, shown on the page ---------- */
  /* WHICH NODE TAKES WHICH WORDS. A sentence is often several text nodes: a label set in bold ahead of it (<strong>Shoppers:</strong>
     about 111 a day…), a word in colour, a number the page writes in. The first build put the WHOLE rewrite in the first node — so
     a sentence that began with a bold label came out bold from end to end (owner, 2026-10-08: "something in the text editor made a
     bunch of text bold i think because the first word of the sentence was bold"). Now:
       · a label first (the first node sits in an inline element whose words end in a colon) keeps its own node: the rewrite's
         words up to its first colon go there, in the label's type, and the rest goes on;
       · of the rest, whatever still stands at the start and at the end stays in the nodes it was in (their bold, their colour);
       · the words that changed go into ONE node among those the change touches — a plain one (a direct child of the unit, in
         the sentence's own type) where there is one — and what the others held of the changed stretch is emptied.
     Only values of nodes that exist are written, as everywhere here. */
  function spread(u, text) {
    const o = u.texts.map(origOf), want = o.map(() => ""), plain = (i) => u.texts[i].parentElement === u.el, clamp = (x, a, b) => Math.max(a, Math.min(b, x));
    let T = u.pre ? text : (u.raw.match(/^\s*/) || [""])[0] + text + (u.raw.match(/\s*$/) || [""])[0], from = 0;
    const first = u.texts[0].parentElement, lab = first !== u.el ? u.texts.filter((n) => first.contains(n)).length : 0;
    if (lab && lab < o.length && /:\s*$/.test(o.slice(0, lab).join(""))) { const cut = T.indexOf(":"); if (cut >= 0 && cut < 80) { want[0] = T.slice(0, cut + 1); T = T.slice(cut + 1); from = lab; } }
    /* a stretch of the new words over a run of nodes: what still stands at its start and end stays where it was, the change goes into one node (a plain one first) */
    const lay = (nodes, G) => {
      if (!nodes.length) return false;
      const O = nodes.map((i) => o[i]).join(""); let p = 0, s = 0;
      while (p < O.length && p < G.length && O[p] === G[p]) p++;
      while (s < O.length - p && s < G.length - p && O[O.length - 1 - s] === G[G.length - 1 - s]) s++;
      const inWord = (S, i) => i > 0 && i < S.length && /\S/.test(S[i - 1]) && /\S/.test(S[i]); // the change is whole words: AGENTS → ROBOTS is not "ROBO" and a kept "TS"
      while (p > 0 && (inWord(O, p) || inWord(G, p))) p--;
      while (s > 0 && (inWord(O, O.length - s) || inWord(G, G.length - s))) s--;
      const q = O.length - s, mid = G.slice(p, G.length - s), spans = []; let at = 0, carrier = 0, best = -1;
      for (const i of nodes) { spans.push([at, at + o[i].length]); at += o[i].length; }
      spans.forEach(([a, b], k) => { if (b < p || a > q) return; const score = (plain(nodes[k]) ? 1e6 : 0) + Math.max(0, Math.min(b, q) - Math.max(a, p)); if (score > best) { best = score; carrier = k; } });
      spans.forEach(([a, b], k) => { want[nodes[k]] = k < carrier ? O.slice(a, clamp(p, a, b)) : k > carrier ? O.slice(clamp(q, a, b), b) : O.slice(a, clamp(p, a, b)) + mid + O.slice(clamp(q, a, b), b); });
      return true;
    };
    /* a word in bold or in colour that the rewrite still holds stays in its own node, and the words between two of those go to the nodes between them */
    let pos = 0, run = [], last = -1;
    for (let i = from; i < o.length; i++) {
      let at = !plain(i) && o[i].trim().length >= 3 ? T.indexOf(o[i], pos) : -1;
      if (at >= 0 && ((/[\p{L}\p{N}]$/u.test(o[i]) && /^[\p{L}\p{N}]/u.test(T.slice(at + o[i].length))) || (/^[\p{L}\p{N}]/u.test(o[i]) && /[\p{L}\p{N}]$/u.test(T.slice(0, at))))) at = -1; // found inside a longer word (Download in Downloads): not the same word
      if (at < 0) { run.push(i); continue; }
      if (!lay(run, T.slice(pos, at)) && at > pos) { if (last >= 0) want[last] += T.slice(pos, at); else { want[i] = T.slice(pos, at); } }
      want[i] += o[i]; pos = at + o[i].length; run = []; last = i;
    }
    if (!lay(run, T.slice(pos)) && pos < T.length && last >= 0) want[last] += T.slice(pos);
    return want;
  }
  function showUnit(u, marked) {
    const e = edits.get(keyOf(u.kind, u.original));
    if (e && e.text !== e.original) {
      const want = spread(u, e.text);
      u.texts.forEach((n, i) => { if (n.nodeValue !== want[i]) { const orig = origOf(n); applied.set(n, { orig, shown: want[i] }); n.nodeValue = want[i]; anyApplied = true; } });
    } else u.texts.forEach((n) => { const a = applied.get(n); if (a && n.nodeValue === a.shown) { n.nodeValue = a.orig; applied.delete(n); } });
    if (e) { marked.add(u.el); if (u.el.getAttribute("data-te") !== "1") u.el.setAttribute("data-te", "1"); }
  }
  function sweep() {
    if (!fdoc || !fdoc.body) return;
    if (!edits.size && !anyApplied) return;
    const units = new Map(), marked = new Set(), w = fdoc.createTreeWalker(fdoc.body, 4);
    for (let n = w.nextNode(); n; n = w.nextNode()) { if (!n.nodeValue && !applied.has(n)) continue; const p = n.parentElement; if (!p || p.closest(SKIP)) continue; const u = unitOf(n); if (!u) continue; let list = units.get(u); if (!list) units.set(u, list = []); list.push(n); }
    for (const [unit, texts] of units) { const u = readUnit(unit, texts); if (u.raw.trim()) showUnit(u, marked); }
    for (const el of fdoc.querySelectorAll("[placeholder]")) {
      let o = phOrig.get(el); if (o && el.getAttribute("placeholder") !== o.shown) { phOrig.delete(el); o = null; }
      const original = o ? o.orig : el.getAttribute("placeholder"), e = edits.get(keyOf("placeholder", original));
      if (e && e.text !== e.original) { if (el.getAttribute("placeholder") !== e.text) { phOrig.set(el, { orig: original, shown: e.text }); el.setAttribute("placeholder", e.text); } }
      else if (o) { el.setAttribute("placeholder", o.orig); phOrig.delete(el); }
      if (e) { marked.add(el); if (el.getAttribute("data-te") !== "1") el.setAttribute("data-te", "1"); }
    }
    for (const el of fdoc.querySelectorAll("[data-te]")) if (!marked.has(el)) el.removeAttribute("data-te");
    if (observer) observer.takeRecords(); // what this pass wrote is not news
  }

  /* ---------- what is under the pointer ---------- */
  const INTERACTIVE = "button,a[href],input,select,textarea,label,summary,[role=button],[role=application],[role=tab],[role=link],[role=checkbox],[role=radio]";
  const isInteractive = (el) => { if (el.closest(INTERACTIVE)) return true; for (let n = el; n && n !== fdoc.documentElement; n = n.parentElement) if (fwin.getComputedStyle(n).cursor === "pointer") return true; return false; };
  function textAt(x, y) {
    let n = null;
    if (fdoc.caretRangeFromPoint) { const r = fdoc.caretRangeFromPoint(x, y); n = r && r.startContainer; } else if (fdoc.caretPositionFromPoint) { const p = fdoc.caretPositionFromPoint(x, y); n = p && p.offsetNode; }
    if (!n || n.nodeType !== 3 || !n.nodeValue.trim()) return null;
    const rg = fdoc.createRange(); rg.selectNodeContents(n);
    for (const q of rg.getClientRects()) if (x >= q.left - 3 && x <= q.right + 3 && y >= q.top - 3 && y <= q.bottom + 3) return n; // on the words themselves, not the empty end of their line
    return null;
  }
  function hit(e) {
    const t = e.target && e.target.nodeType === 1 ? e.target : null; if (!t || !fdoc.body.contains(t)) return null;
    if (t.tagName === "INPUT" || t.tagName === "TEXTAREA") return t.getAttribute("placeholder") && !t.value ? { kind: "placeholder", el: t, interactive: true } : null;
    let n = textAt(e.clientX, e.clientY); if (n && n.parentElement.closest(SKIP)) n = null;
    if (!n) { // the padding of a button or a box: its words are the first text inside it
      if (!e.altKey) return null;
      const holder = t.closest("button,a,label,[role=button]") || (t.children.length <= 3 ? t : null); if (!holder) return null;
      const w = fdoc.createTreeWalker(holder, 4); for (let k = w.nextNode(); k; k = w.nextNode()) if (k.nodeValue.trim() && !k.parentElement.closest(SKIP)) { n = k; break; }
      if (!n) return null;
    }
    const unit = unitOf(n); return unit ? { kind: "text", unit, interactive: isInteractive(n.parentElement) } : null;
  }

  /* ---------- where on the page a rewrite was made (for whoever applies it) ---------- */
  function originalHtml(x) {
    const mine = new Set(x.texts);
    const walk = (node) => { let s = ""; for (const c of node.childNodes) { if (c.nodeType === 3) s += mine.has(c) ? esc(origOf(c)) : ""; else if (c.nodeType === 1) { if (isInline(c)) { const t = c.tagName.toLowerCase(); s += `<${t}>${walk(c)}</${t}>`; } else s += "<…>"; } } return s; };
    return walk(x.el).slice(0, 1500);
  }
  function describe(x) {
    const el = x.el, d = fdoc, head = d.querySelector("[data-screen-title]") || d.querySelector("h1");
    const box = el.closest("dialog,[role=dialog],[role=alertdialog],[aria-modal=true]");
    const layer = box ? `the dialog${box.getAttribute("aria-label") ? ` “${norm(box.getAttribute("aria-label"))}”` : ""}` : el.closest("nav,[role=navigation]") ? "the navigation" : el.closest("aside,[role=complementary]") ? "the side panel" : el.closest("footer,[role=contentinfo]") ? "the footer" : el.closest("header,[role=banner]") ? "the header" : undefined;
    const where = [];
    for (let a = el.parentElement; a && a !== d.body && where.length < 3; a = a.parentElement) { const h = a.querySelector("h1,h2,h3,h4,[data-screen-title]"), words = h ? norm(h.textContent).slice(0, 90) : ""; if (h && h !== el && !el.contains(h) && !h.contains(el) && (h.compareDocumentPosition(el) & 4) && words && !where.includes(words)) where.push(words); }
    const path = [];
    for (let a = el; a && a !== d.body && path.length < 5; a = a.parentElement) path.unshift(a.tagName.toLowerCase() + (typeof a.className === "string" && a.className.trim() ? "." + a.className.trim().split(/\s+/).join(".") : "") + [...a.attributes].filter((t) => /^data-(?!te$)/.test(t.name)).map((t) => `[${t.name}]`).join(""));
    const loc = fwin.location;
    return { page: loc.pathname + loc.search + loc.hash, title: norm(d.title) || undefined, screen: (head && norm(head.textContent).slice(0, 90)) || "", layer, where, viewport: `${fwin.innerWidth}x${fwin.innerHeight}`, tag: el.tagName.toLowerCase(), path: path.join(" > "), html: x.kind === "placeholder" ? undefined : originalHtml(x) };
  }

  /* ---------- the editor over the words ---------- */
  function place() {
    if (!editing) return;
    const r = editing.el.getBoundingClientRect(), W = frame.clientWidth, H = frame.clientHeight, w = Math.min(W - 16, Math.max(380, Math.min(r.width + 20, 780)));
    ed.style.width = `${w}px`; ed.style.left = `${Math.max(8, Math.min(r.left - 10, W - w - 8))}px`;
    const h = ed.offsetHeight; ed.style.top = `${Math.max(8, Math.min(r.top - 10, H - h - 8))}px`;
  }
  const grow = () => { ta.style.height = "auto"; ta.style.height = `${Math.min(ta.scrollHeight + 2, 340)}px`; place(); };
  function open(h) {
    hideHover();
    if (h.kind === "placeholder") { const o = phOrig.get(h.el), original = o && h.el.getAttribute("placeholder") === o.shown ? o.orig : h.el.getAttribute("placeholder"); editing = { kind: "placeholder", el: h.el, texts: [], original, key: keyOf("placeholder", original) }; }
    else { const u = readUnit(h.unit); if (!u.original.trim()) return; editing = { ...u, key: keyOf(u.kind, u.original) }; }
    const e = edits.get(editing.key);
    ta.value = e ? e.text : editing.original; noteBox.value = (e && e.note) || "";
    was.textContent = ""; if (e && e.text !== e.original) { const b = document.createElement("b"); b.textContent = editing.kind === "placeholder" ? "THE HINT WAS  " : "WAS  "; was.append(b, editing.original); was.style.display = ""; } else was.style.display = "none";
    $("edReset").style.display = e ? "" : "none";
    $("edDone").innerHTML = editing.kind === "pre" ? "DONE <small>⌘⏎</small>" : "DONE <small>⏎</small>";
    const cs = fwin.getComputedStyle(editing.kind === "placeholder" ? editing.el : (editing.texts[0] && editing.texts[0].parentElement) || editing.el); // the type the words are set in, so a rewrite is judged at its size
    ta.style.fontFamily = cs.fontFamily; ta.style.fontSize = `${Math.max(13, Math.min(24, parseFloat(cs.fontSize) || 15))}px`; ta.style.fontWeight = cs.fontWeight; ta.style.letterSpacing = cs.letterSpacing; ta.style.lineHeight = "1.35"; ta.style.whiteSpace = editing.kind === "pre" ? "pre-wrap" : "normal";
    ed.style.display = "block"; place(); grow(); ta.focus(); ta.select(); // the width first: the height is that of the words at that width
  }
  function commit() {
    if (!editing) return;
    const x = editing; editing = null; ed.style.display = "none";
    const text = x.kind === "text" ? norm(ta.value) : ta.value.replace(/\r\n/g, "\n"), note = noteBox.value.trim(), had = edits.get(x.key);
    if (text === x.original && !note) { if (had) { edits.delete(x.key); touched(); } }
    else if (!had || had.text !== text || (had.note || "") !== note) { edits.set(x.key, { ...(had || describe(x)), key: x.key, kind: x.kind, original: x.original, text, note: note || undefined, at: new Date().toISOString() }); touched(); if (!text) toast("Those words are gone from the page. ALL EDITS has them, with UNDO."); }
    sweep();
  }
  const cancel = () => { editing = null; ed.style.display = "none"; };
  ta.addEventListener("input", grow);
  ta.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.preventDefault(); cancel(); } else if (e.key === "Enter" && !e.shiftKey && (editing && editing.kind !== "pre" || e.metaKey || e.ctrlKey)) { e.preventDefault(); commit(); } });
  noteBox.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.preventDefault(); cancel(); } else if (e.key === "Enter") { e.preventDefault(); commit(); } });
  $("edDone").onclick = commit; $("edCancel").onclick = cancel;
  $("edReset").onclick = () => { if (!editing) return; const k = editing.key; cancel(); if (edits.delete(k)) touched(); sweep(); };

  /* ---------- the frame: what a press on it does ---------- */
  const stopIt = (e) => { e.preventDefault(); e.stopImmediatePropagation(); };
  function onPress(e) {
    if (!on) return;
    const h = hit(e), mine = !!h && (e.altKey || !h.interactive); // plain text opens at a click; a button keeps working, and opens with ⌥
    if (e.type === "click") { if (editing) commit(); if (mine) { stopIt(e); open(h); } return; }
    if (mine) stopIt(e);
  }
  const hideHover = () => { hover.style.display = "none"; hoverTag.style.display = "none"; };
  let raf = 0, lastMove = null;
  function onMove(e) {
    lastMove = e; if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0; const ev = lastMove; if (!on || editing || !ev) return hideHover();
      const h = hit({ target: ev.target, clientX: ev.clientX, clientY: ev.clientY, altKey: true }); if (!h) return hideHover();
      const r = (h.kind === "placeholder" ? h.el : h.unit).getBoundingClientRect(); if (r.width < 2 || r.height < 2 || r.height > frame.clientHeight * 1.5) return hideHover();
      hover.style.cssText = `display:block;left:${r.left - 3}px;top:${r.top - 3}px;width:${r.width + 6}px;height:${r.height + 6}px;border-style:${h.interactive ? "dashed" : "solid"}`;
      hoverTag.textContent = h.kind === "placeholder" ? "⌥ CLICK · THE HINT IN THIS BOX" : h.interactive ? "⌥ CLICK TO REWRITE" : "CLICK TO REWRITE";
      hoverTag.style.cssText = `display:block;left:${Math.max(0, r.left - 3)}px;top:${r.top - 3 >= 16 ? r.top - 19 : r.bottom + 3}px`;
    });
  }
  function attach() {
    let doc; try { doc = frame.contentDocument; } catch (e) { return; }
    if (!doc || !doc.body || frame.contentWindow.location.href === "about:blank") return;
    fwin = frame.contentWindow; fdoc = doc; applied = new WeakMap(); phOrig = new WeakMap(); inlineCache = new WeakMap(); preCache = new WeakMap(); anyApplied = false; editing = null; ed.style.display = "none"; hideHover();
    const style = fdoc.createElement("style"); style.textContent = "[data-te]{outline:2px dashed #2D6CDF!important;outline-offset:2px}"; (fdoc.head || fdoc.documentElement).appendChild(style); // a blue few pages use: seen on light and dark alike
    observer = new fwin.MutationObserver(() => { if (editing && !editing.el.isConnected) cancel(); sweep(); }); // straight after the page's own change and before it is painted: the old words never flash
    observer.observe(fdoc.documentElement, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ["placeholder"] });
    for (const type of ["pointerdown", "mousedown", "pointerup", "mouseup", "click", "dblclick", "auxclick"]) fdoc.addEventListener(type, onPress, true);
    fdoc.addEventListener("mousemove", onMove, true);
    fwin.addEventListener("scroll", () => { hideHover(); place(); }, true);
    fdoc.addEventListener("keydown", (e) => { if (editing && e.key === "Escape") { stopIt(e); cancel(); } }, true);
    try { const loc = fwin.location, page = loc.pathname + loc.search + loc.hash; $("where").textContent = page; history.replaceState(null, "", `/__edit/?page=${encodeURIComponent(page)}`); } catch (e) { /* the label is only a convenience */ }
    sweep();
  }
  frame.addEventListener("load", attach);
  frame.addEventListener("mouseleave", hideHover);
  window.addEventListener("resize", () => { hideHover(); place(); });

  /* ---------- kept, saved, listed ---------- */
  const persist = () => { try { localStorage.setItem(LOCAL, JSON.stringify({ dirty, edits: [...edits.values()] })); } catch (e) { /* the browser's store is full: SAVE still writes the file */ } };
  function touched() { dirty = true; persist(); render(); }
  function render() {
    const s = $("save"); s.textContent = dirty ? "SAVE THIS PAGE" : "SAVED ✓"; s.classList.toggle("clean", !dirty); s.disabled = !dirty;
    $("list").textContent = `ALL EDITS · ${edits.size}`;
    if ($("drawer").style.display === "flex") drawList();
  }
  async function api(name, body) {
    const r = await fetch(`/__edit/api/${name}`, body === undefined ? {} : { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
    const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error(j.error || `HTTP ${r.status}`); return j;
  }
  $("save").onclick = async () => {
    if (editing) commit();
    try { const r = await api("edits", { edits: [...edits.values()] }); dirty = false; persist(); render(); toast(`Saved · ${r.count} edit${r.count === 1 ? "" : "s"} in ${r.file}. Tell Claude: /text-edit apply`); }
    catch (e) { toast(`NOT SAVED: ${e.message}. Your edits are still kept by this browser.`); }
  };
  function drawList() {
    const body = $("drawerBody"); body.textContent = "";
    if (!edits.size) { const p = document.createElement("p"); p.textContent = "Nothing rewritten yet. Click any text on the page."; p.style.color = "#4A554E"; body.append(p); return; }
    for (const e of [...edits.values()].reverse()) {
      const row = document.createElement("div"); row.className = "ed";
      const where = document.createElement("div"); where.className = "where"; const sp = document.createElement("span"); sp.textContent = [e.page, e.screen, e.layer].filter(Boolean).join(" · ") || "—";
      const un = document.createElement("button"); un.className = "eb"; un.textContent = "UNDO"; un.onclick = () => { edits.delete(e.key); touched(); sweep(); };
      where.append(sp, un); row.append(where);
      if (e.text !== e.original) { const o = document.createElement("div"); o.className = "old"; o.textContent = e.kind === "placeholder" ? `(hint) ${e.original}` : e.original; const n = document.createElement("div"); n.className = "new"; n.textContent = e.text || "(removed)"; row.append(o, n); }
      else { const n = document.createElement("div"); n.className = "new"; n.textContent = e.original; row.append(n); }
      if (e.note) { const t = document.createElement("div"); t.className = "note"; t.textContent = `Note: ${e.note}`; row.append(t); }
      body.append(row);
    }
  }
  $("list").onclick = () => { const d = $("drawer"), open = d.style.display !== "flex"; d.style.display = open ? "flex" : "none"; if (open) drawList(); };
  $("closeDrawer").onclick = () => { $("drawer").style.display = "none"; };
  $("dlBtn").onclick = () => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify({ savedAt: new Date().toISOString(), edits: [...edits.values()] }, null, 2)], { type: "application/json" })); a.download = "edits.json"; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000); };
  let toastT = 0; const toast = (words) => { const t = $("toast"); t.textContent = words; t.style.display = "block"; clearTimeout(toastT); toastT = setTimeout(() => { t.style.display = "none"; }, 4200); };
  window.addEventListener("beforeunload", (e) => { if (dirty) { e.preventDefault(); e.returnValue = ""; } });

  /* ---------- the toolbar ---------- */
  $("mode").onclick = () => { on = !on; if (!on) { if (editing) commit(); hideHover(); } $("mode").textContent = on ? "✎ EDITING: ON" : "EDITING: OFF"; $("mode").classList.toggle("on", on); $("hint").innerHTML = on ? "<b>Click</b> text to rewrite it · <b>⌥ click</b> for a button’s words" : "The page as a visitor has it. Turn editing on to rewrite."; };
  $("helpBtn").onclick = () => { $("help").style.display = "flex"; }; $("helpClose").onclick = () => { $("help").style.display = "none"; try { localStorage.setItem(`${LOCAL}-help`, "1"); } catch (e) { /* shown again next time */ } };
  $("help").addEventListener("click", (e) => { if (e.target === $("help")) $("helpClose").onclick(); });

  /* ---------- start ---------- */
  (async () => {
    let state = { edits: [] };
    try { state = await api("state"); } catch (e) { toast(`The editor's server is not answering: ${e.message}`); }
    file = state.file || file; $("fileName").textContent = file;
    let kept = null; try { kept = JSON.parse(localStorage.getItem(LOCAL) || "null"); } catch (e) { /* none */ }
    const from = kept && kept.dirty && Array.isArray(kept.edits) ? kept.edits : state.edits || []; dirty = !!(kept && kept.dirty && Array.isArray(kept.edits)); // rewrites made and not yet saved come back; otherwise the file is what stands
    for (const e of from) if (e && e.key && typeof e.original === "string" && typeof e.text === "string") edits.set(e.key, e);
    render();
    const page = new URLSearchParams(location.search).get("page") || "/"; frame.src = page.startsWith("/") && !page.startsWith("//") ? page : "/";
    try { if (!localStorage.getItem(`${LOCAL}-help`)) $("help").style.display = "flex"; } catch (e) { /* */ }
  })();
})();
