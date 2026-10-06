#!/usr/bin/env node
/*
 * Device / mode matrix: capture a motion page at a moment across viewports, DPR,
 * colour scheme, reduced motion, RTL, pointer type and browsers, into one labelled grid.
 *
 *   node device_matrix.js <url|animation.html|project_dir> [--t 1.2]
 *        [--viewports 390x844,768x1024,1440x900] [--dpr 1,2,3]
 *        [--modes default,reduced,dark,rtl,touch] [--browsers chromium,webkit,firefox]
 *        [--out out/matrix.png]
 *
 * Seek pages (Motion.register) are seeked to --t after load; other pages are captured
 * after load (+ optional --wait ms). Missing browsers are skipped with a note
 * (install with: npx playwright install webkit firefox).
 * Also reports page errors and horizontal overflow per cell.
 */
"use strict";
const fs = require("fs");
const path = require("path");
const pw = require("playwright");
const { startServer, toUrl, resolveTarget } = require("./_serve_static");

function arg(name, def) {
  const i = process.argv.indexOf("--" + name);
  if (i < 0) return def;
  const v = process.argv[i + 1];
  return v === undefined || v.startsWith("--") ? true : v;
}

async function main() {
  const target = process.argv[2];
  if (!target || target.startsWith("--") || process.argv.includes("--help")) {
    console.log(fs.readFileSync(__filename, "utf8").split("\n").slice(2, 16).map((l) => l.replace(/^ \* ?/, "")).join("\n"));
    process.exit(target ? 0 : 2);
  }
  const t = +arg("t", 0);
  const viewports = String(arg("viewports", "390x844,768x1024,1440x900")).split(",").map((s) => s.split("x").map(Number));
  const dprs = String(arg("dpr", "1,2,3")).split(",").map(Number);
  const modes = String(arg("modes", "default,reduced,dark")).split(",");
  const browsers = String(arg("browsers", "chromium")).split(",");
  const wait = +arg("wait", 300);
  const local = resolveTarget(target);
  const outPath = arg("out", local.root ? path.join(local.root, "out", "matrix.png") : "out/matrix.png");
  const server = await startServer(target);

  const cells = [];
  for (const bname of browsers) {
    let browser;
    try { browser = await pw[bname].launch(); }
    catch (e) { console.warn(`skip ${bname}: not installed (npx playwright install ${bname})`); continue; }
    for (const [w, h] of viewports) for (const dpr of dprs) for (const mode of modes) {
      if (bname === "firefox" && dpr !== 1 && mode === "touch") continue;
      const ctx = await browser.newContext({
        viewport: { width: w, height: h }, deviceScaleFactor: dpr,
        colorScheme: mode === "dark" ? "dark" : "light",
        reducedMotion: mode === "reduced" ? "reduce" : "no-preference",
        hasTouch: mode === "touch", isMobile: mode === "touch" && bname === "chromium",
      });
      const page = await ctx.newPage();
      const errors = [];
      page.on("pageerror", (e) => errors.push(String(e)));
      const params = { t: t || 0 };
      if (mode === "reduced") params.reduced = 1;
      await page.goto(toUrl(server, target, params), { waitUntil: "load" });
      if (mode === "rtl") await page.evaluate(() => { document.documentElement.dir = "rtl"; });
      const isSeek = await page.evaluate(() => !!window.__motion);
      if (isSeek) {
        await page.evaluate(async (tt) => { await window.__motion.ready; window.__motion.seek(tt);
          await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))); }, t);
      } else await page.waitForTimeout(wait);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
      const png = await page.screenshot({ type: "png" });
      cells.push({ label: `${bname} · ${w}×${h} @${dpr}x · ${mode}`, png: png.toString("base64"), w, h, errors, overflow });
      if (errors.length || overflow) console.warn(`${bname} ${w}x${h}@${dpr} ${mode}: ${errors.length ? "errors: " + errors.join("; ") : ""}${overflow ? " horizontal overflow" : ""}`);
      await ctx.close();
    }
    await browser.close();
  }
  server && server.close();
  if (!cells.length) { console.error("error: no cells captured"); process.exit(2); }

  // Compose the grid by rendering an HTML page of the captures.
  const thumbW = 260;
  const html = `<html><body style="margin:0;padding:16px;background:#DCDCE0;font:12px ui-monospace,Menlo,monospace;color:#3F3F46">
    <div style="font-size:14px;margin-bottom:12px;color:#18181B">device matrix · t=${t}s · ${target}</div>
    <div style="display:flex;flex-wrap:wrap;gap:16px;align-items:flex-start">${cells.map((c) => `
      <figure style="margin:0;width:${thumbW}px"><img style="display:block;width:${thumbW}px;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.1);outline:${c.errors.length || c.overflow ? "2px solid #DC2626" : "0"}" src="data:image/png;base64,${c.png}">
      <figcaption style="margin-top:6px">${c.label}${c.errors.length ? " · ERR" : ""}${c.overflow ? " · OVERFLOW" : ""}</figcaption></figure>`).join("")}</div></body></html>`;
  const b = await pw.chromium.launch();
  const p = await b.newPage({ viewport: { width: Math.min(6, cells.length) * (thumbW + 16) + 32, height: 400 } });
  await p.setContent(html, { waitUntil: "load" });
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  await p.screenshot({ path: outPath, fullPage: true });
  await b.close();
  const bad = cells.filter((c) => c.errors.length || c.overflow).length;
  console.log(`device_matrix: ${cells.length} cells → ${outPath}${bad ? `  (${bad} flagged)` : ""}`);
  process.exit(bad ? 1 : 0);
}

main().catch((e) => { console.error("error:", e.message); process.exit(2); });
