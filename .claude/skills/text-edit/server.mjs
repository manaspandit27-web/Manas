#!/usr/bin/env node
/* server.mjs — ANY WEBSITE WITH EVERY WORD EDITABLE. Ported from the Snack Arena text editor (tools/text-edit/server.mjs).

   WHAT IT IS. The real site, byte for byte, inside a frame with a toolbar above it (shell.html). Click any text to rewrite it;
   SAVE writes every edit to text-edits/edits.json — the words as they were, the words as they should be, and where on the page
   they stood — which is what gets applied to the source afterwards. Nothing in the site is changed by this tool.

   WHAT IT RUNS ON. Either a folder of static files (--root) or the site's own running dev server (--proxy), passed through
   unchanged. Because the frame is the same origin as the editor, the editor reads and writes the frame's page directly.

     node server.mjs --proxy http://localhost:5173     a running app (Vite, Next, CRA, a gateway…)
     node server.mjs --root .                          a folder of HTML files
     options: --port 8780 (or PORT)   --out text-edits/edits.json (or EDITS)
     then open http://localhost:8780/ in Chrome.

   Run it as a long-lived terminal process, not as an app's preview server (those get stopped mid-session). */
import { createServer, request } from "node:http";
import { request as httpsRequest } from "node:https";
import { readFileSync, writeFileSync, existsSync, mkdirSync, renameSync, copyFileSync, statSync } from "node:fs";
import { dirname, join, resolve, extname, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import net from "node:net";
import tls from "node:tls";

const here = dirname(fileURLToPath(import.meta.url));
const args = {}; for (let i = 2; i < process.argv.length; i++) { const a = process.argv[i]; if (a.startsWith("--")) { const v = process.argv[i + 1]; args[a.slice(2)] = v && !v.startsWith("--") ? (i++, v) : true; } }
const PORT = Number(args.port ?? process.env.PORT ?? 8780);
const EDITS = resolve(args.out || process.env.EDITS || join("text-edits", "edits.json"));
const UP = args.proxy ? new URL(args.proxy) : null;
const ROOT = UP ? null : resolve(args.root || ".");

/* ---- the edits file: written whole or not at all, the one before kept as .bak ---- */
const readEdits = () => { try { const j = JSON.parse(readFileSync(EDITS, "utf8")); return Array.isArray(j.edits) ? j.edits : []; } catch (e) { return []; } };
function writeEdits(edits) {
  mkdirSync(dirname(EDITS), { recursive: true });
  if (existsSync(EDITS)) copyFileSync(EDITS, `${EDITS}.bak`); // the file as it was before this save
  const tmp = `${EDITS}.tmp`; writeFileSync(tmp, JSON.stringify({ savedAt: new Date().toISOString(), note: "Written by the text editor (/text-edit). original = the words as the page showed them; text = the words they should be; note = an instruction about that place.", edits }, null, 2)); renameSync(tmp, EDITS);
}

/* ---- the site behind the frame ---- */
const TYPES = { ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp", ".avif": "image/avif", ".ico": "image/x-icon", ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg", ".mp4": "video/mp4", ".webm": "video/webm", ".pdf": "application/pdf", ".txt": "text/plain; charset=utf-8", ".xml": "application/xml", ".wasm": "application/wasm" };
function serveFile(req, res) {
  let p; try { p = decodeURIComponent(req.url.split("?")[0]); } catch (e) { return send(res, 400, "text/plain", "bad address"); }
  let f = resolve(ROOT, "." + p);
  if (f !== ROOT && !f.startsWith(ROOT + sep)) return send(res, 403, "text/plain", "outside the site");
  try { if (statSync(f).isDirectory()) f = join(f, "index.html"); } catch (e) { /* a missing file is a 404 below */ }
  if (!existsSync(f) && existsSync(f + ".html")) f += ".html";
  if (!existsSync(f)) return send(res, 404, "text/plain", "not found");
  send(res, 200, TYPES[extname(f).toLowerCase()] || "application/octet-stream", readFileSync(f));
}
/* passed on as it comes (streams included); only the headers that forbid framing are dropped, since the frame is the point */
function pass(req, res) {
  const go = UP.protocol === "https:" ? httpsRequest : request;
  const up = go({ hostname: UP.hostname, port: UP.port || (UP.protocol === "https:" ? 443 : 80), path: req.url, method: req.method, headers: { ...req.headers, host: UP.host } }, (ans) => {
    const h = { ...ans.headers }; delete h["x-frame-options"];
    if (h["content-security-policy"]) { h["content-security-policy"] = String(h["content-security-policy"]).split(";").filter((d) => !/^\s*frame-ancestors\b/i.test(d)).join(";"); if (!h["content-security-policy"].trim()) delete h["content-security-policy"]; }
    if (h.location) { try { const l = new URL(h.location, UP); if (l.host === UP.host) h.location = l.pathname + l.search + l.hash; } catch (e) { /* left as sent */ } } // a redirect to the app's own address stays inside the editor
    res.writeHead(ans.statusCode, h); ans.pipe(res);
  });
  up.on("error", (e) => { if (!res.headersSent) res.writeHead(502, { "content-type": "text/plain" }); res.end(`the site is not answering at ${UP.href}: ${e.message}`); });
  req.pipe(up);
}

/* ---- the server in front of it ---- */
const send = (res, code, type, body) => { res.writeHead(code, { "content-type": type, "cache-control": "no-store" }); res.end(body); };
const json = (res, code, obj) => send(res, code, "application/json; charset=utf-8", JSON.stringify(obj));
const bodyOf = (req, max = 8e6) => new Promise((ok, no) => { const parts = []; let n = 0; req.on("data", (c) => { n += c.length; if (n > max) { no(new Error("too large")); req.destroy(); } else parts.push(c); }); req.on("end", () => { try { ok(JSON.parse(Buffer.concat(parts).toString("utf8") || "{}")); } catch (e) { no(new Error("not JSON")); } }); req.on("error", no); });
const shown = (p) => relative(process.cwd(), p) || p;
const server = createServer(async (req, res) => {
  const path = req.url.split("?")[0];
  try {
    /* an address typed in the browser opens the editor on that page; the frame inside it (Sec-Fetch-Dest: iframe) gets the page itself */
    if (!path.startsWith("/__edit") && req.method === "GET" && req.headers["sec-fetch-dest"] === "document") { res.writeHead(302, { location: `/__edit/?page=${encodeURIComponent(req.url)}` }); return res.end(); }
    if (path === "/__edit" || path === "/__edit/") return send(res, 200, "text/html; charset=utf-8", readFileSync(join(here, "shell.html")));
    if (path === "/__edit/shell.js") return send(res, 200, "text/javascript; charset=utf-8", readFileSync(join(here, "shell.js")));
    if (path === "/__edit/api/state") return json(res, 200, { edits: readEdits(), file: shown(EDITS), site: UP ? UP.href : shown(ROOT) || "." });
    if (path === "/__edit/api/edits" && req.method === "POST") {
      const origin = req.headers.origin; if (origin && new URL(origin).host !== req.headers.host) return json(res, 403, { error: "only the editor saves here" });
      const b = await bodyOf(req); if (!Array.isArray(b.edits)) return json(res, 400, { error: "edits must be a list" });
      writeEdits(b.edits); console.log(`[text-edit] saved ${b.edits.length} edit(s) to ${shown(EDITS)}`); return json(res, 200, { ok: true, count: b.edits.length, file: shown(EDITS) });
    }
    if (path.startsWith("/__edit/")) return send(res, 404, "text/plain", "not found");
    return UP ? pass(req, res) : serveFile(req, res);
  } catch (e) { console.error(`[text-edit] ${path}: ${e.message}`); if (!res.headersSent) json(res, 500, { error: e.message }); else res.end(); }
});
/* websockets (a dev server's hot reload) go straight through */
server.on("upgrade", (req, sock, head) => {
  if (!UP) return sock.destroy();
  const port = Number(UP.port || (UP.protocol === "https:" ? 443 : 80)), up = UP.protocol === "https:" ? tls.connect(port, UP.hostname, { servername: UP.hostname }) : net.connect(port, UP.hostname);
  up.on(UP.protocol === "https:" ? "secureConnect" : "connect", () => {
    up.write(`${req.method} ${req.url} HTTP/1.1\r\n${Object.entries({ ...req.headers, host: UP.host }).map(([k, v]) => `${k}: ${v}`).join("\r\n")}\r\n\r\n`); up.write(head); sock.pipe(up).pipe(sock);
  });
  up.on("error", () => sock.destroy()); sock.on("error", () => up.destroy());
});
server.on("error", (e) => { console.error(e.code === "EADDRINUSE" ? `[text-edit] port ${PORT} is taken: start it with --port ${PORT + 1}` : `[text-edit] ${e.message}`); process.exit(1); });
server.listen(PORT, () => console.log(`text editor on http://localhost:${server.address().port}/  ·  the site: ${UP ? UP.href : shown(ROOT) || "."}  ·  edits are saved to ${shown(EDITS)}`));
const stop = () => { server.close(); process.exit(0); };
process.on("SIGTERM", stop); process.on("SIGINT", stop);
