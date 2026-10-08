#!/usr/bin/env node
// Serve a site with the text edit overlay injected, and save edits to a JSON file.
//
//   node serve.mjs --root .                         static files from a folder
//   node serve.mjs --proxy http://localhost:5173    in front of a running dev server
//
// Options: --port 8780  --out text-edits/edits.json  --open page.html
// No dependencies. Stop with Ctrl+C.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import net from 'node:net';
import { fileURLToPath } from 'node:url';

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, all) => {
    if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : true]);
    return acc;
  }, []),
);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const PORT = +(args.port || 8780);
const OUT = path.resolve(args.out || 'text-edits/edits.json');
const PROXY = args.proxy ? new URL(args.proxy) : null;
const ROOT = path.resolve(args.root || '.');
const TAG = '<script src="/__edit/overlay.js" data-text-edit></script>';

const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.gif': 'image/gif', '.webp': 'image/webp', '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.woff': 'font/woff',
  '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.ogg': 'audio/ogg', '.mp4': 'video/mp4', '.webm': 'video/webm', '.txt': 'text/plain',
};

// After <head> (never before the doctype: that drops the page into quirks mode).
function inject(html) {
  if (html.includes('data-text-edit')) return html;
  const head = html.match(/<head\b[^>]*>/i);
  if (head) return html.replace(head[0], head[0] + TAG);
  const body = html.match(/<body\b[^>]*>/i);
  if (body) return html.replace(body[0], body[0] + TAG);
  return html + TAG;
}

function readEdits() {
  try { return JSON.parse(fs.readFileSync(OUT, 'utf8')); } catch { return { edits: [] }; }
}

function api(req, res) {
  const url = new URL(req.url, 'http://x');
  if (url.pathname === '/__edit/overlay.js') {
    res.writeHead(200, { 'content-type': 'text/javascript', 'cache-control': 'no-store' });
    return fs.createReadStream(path.join(HERE, 'overlay.js')).pipe(res);
  }
  if (url.pathname === '/__edit/edits' && req.method === 'GET') {
    res.writeHead(200, { 'content-type': 'application/json', 'cache-control': 'no-store' });
    return res.end(JSON.stringify(readEdits()));
  }
  if (url.pathname === '/__edit/save' && req.method === 'POST') {
    // Only this page may save: refuse cross-site posts.
    const origin = req.headers.origin;
    if (origin && new URL(origin).host !== req.headers.host) {
      res.writeHead(403);
      return res.end('cross-origin save refused');
    }
    let body = '';
    req.on('data', (c) => { body += c; if (body.length > 5e6) req.destroy(); });
    req.on('end', () => {
      try {
        const data = JSON.parse(body);
        if (!Array.isArray(data.edits)) throw new Error('no edits array');
        fs.mkdirSync(path.dirname(OUT), { recursive: true });
        fs.writeFileSync(OUT, JSON.stringify(data, null, 2) + '\n');
        const rel = path.relative(process.cwd(), OUT) || OUT;
        console.log(`saved ${data.edits.length} edit(s) -> ${rel}`);
        res.writeHead(200, { 'content-type': 'application/json' });
        res.end(JSON.stringify({ ok: true, path: rel, count: data.edits.length }));
      } catch (e) {
        res.writeHead(400);
        res.end(String(e.message));
      }
    });
    return;
  }
  res.writeHead(404);
  res.end();
}

function serveStatic(req, res) {
  let p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  let file = path.join(ROOT, p);
  if (!file.startsWith(ROOT)) { res.writeHead(403); return res.end(); }
  try { if (fs.statSync(file).isDirectory()) file = path.join(file, 'index.html'); } catch {}
  fs.readFile(file, (err, buf) => {
    if (err) { res.writeHead(404, { 'content-type': 'text/plain' }); return res.end('not found'); }
    const type = TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream';
    if (type.startsWith('text/html')) buf = Buffer.from(inject(buf.toString('utf8')));
    res.writeHead(200, { 'content-type': type, 'cache-control': 'no-store' });
    res.end(buf);
  });
}

function proxy(req, res) {
  const headers = { ...req.headers, host: PROXY.host, 'accept-encoding': 'identity' };
  const up = http.request({ hostname: PROXY.hostname, port: PROXY.port, path: req.url, method: req.method, headers }, (r) => {
    const type = r.headers['content-type'] || '';
    if (!type.includes('text/html')) {
      res.writeHead(r.statusCode, r.headers);
      return r.pipe(res);
    }
    const chunks = [];
    r.on('data', (c) => chunks.push(c));
    r.on('end', () => {
      const out = Buffer.from(inject(Buffer.concat(chunks).toString('utf8')));
      const h = { ...r.headers, 'content-length': out.length };
      delete h['content-encoding'];
      // A strict CSP would block the overlay script; this is a local editing proxy only.
      delete h['content-security-policy'];
      res.writeHead(r.statusCode, h);
      res.end(out);
    });
  });
  up.on('error', (e) => { res.writeHead(502); res.end(`dev server not reachable at ${PROXY.href}: ${e.message}`); });
  req.pipe(up);
}

const server = http.createServer((req, res) => {
  if (req.url.startsWith('/__edit/')) return api(req, res);
  return PROXY ? proxy(req, res) : serveStatic(req, res);
});

// Pass websockets (dev-server hot reload) straight through.
server.on('upgrade', (req, sock, head) => {
  if (!PROXY) return sock.destroy();
  const up = net.connect(+PROXY.port || 80, PROXY.hostname, () => {
    up.write(`${req.method} ${req.url} HTTP/1.1\r\n` +
      Object.entries({ ...req.headers, host: PROXY.host }).map(([k, v]) => `${k}: ${v}`).join('\r\n') + '\r\n\r\n');
    up.write(head);
    sock.pipe(up).pipe(sock);
  });
  up.on('error', () => sock.destroy());
  sock.on('error', () => up.destroy());
});

server.listen(PORT, '127.0.0.1', () => {
  const start = `http://localhost:${PORT}/${typeof args.open === 'string' ? args.open.replace(/^\//, '') : ''}`;
  console.log(`text edit: ${start}`);
  console.log(`  serving ${PROXY ? 'proxy -> ' + PROXY.href : ROOT}`);
  console.log(`  edits save to ${path.relative(process.cwd(), OUT) || OUT}`);
  console.log('  turn on "✎ Edit text" (Alt+E), click any text, then Save.');
});
