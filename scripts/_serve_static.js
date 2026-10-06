"use strict";
// Tiny static server for the Node test scripts: serves a local project folder on a
// random localhost port (with motion-runtime.js fallback), or passes URLs through.
const http = require("http");
const fs = require("fs");
const path = require("path");

const RUNTIME = path.join(__dirname, "..", "templates", "motion-runtime.js");
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
  ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".woff2": "font/woff2", ".mp4": "video/mp4", ".webm": "video/webm" };

function resolveTarget(target) {
  if (/^https?:\/\//.test(target)) return { url: target };
  let p = path.resolve(target);
  if (fs.existsSync(p) && fs.statSync(p).isDirectory()) p = path.join(p, "animation.html");
  if (!fs.existsSync(p)) throw new Error(`${target} is not a URL, an .html file, or a folder with animation.html`);
  return { root: path.dirname(p), file: path.basename(p) };
}

function startServer(target) {
  const t = resolveTarget(target);
  if (t.url) return Promise.resolve(null);
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      const u = decodeURIComponent(new URL(req.url, "http://x").pathname);
      let f = path.join(t.root, u);
      if (!f.startsWith(t.root)) { res.writeHead(403); return res.end(); }
      if (!fs.existsSync(f) && u.endsWith("/motion-runtime.js")) f = RUNTIME;
      fs.readFile(f, (err, data) => {
        if (err) { res.writeHead(404); return res.end(); }
        res.writeHead(200, { "Content-Type": TYPES[path.extname(f)] || "application/octet-stream", "Cache-Control": "no-store" });
        res.end(data);
      });
    });
    srv.listen(0, "127.0.0.1", () => { srv.target = t; resolve(srv); });
  });
}

function toUrl(server, target, params = {}) {
  const base = server ? `http://127.0.0.1:${server.address().port}/${server.target.file}` : target;
  const u = new URL(base);
  for (const [k, v] of Object.entries(params)) if (v != null) u.searchParams.set(k, v);
  return u.toString();
}

module.exports = { startServer, toUrl, resolveTarget };
