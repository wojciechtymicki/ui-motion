#!/usr/bin/env node
/*
 * Playwright + Chrome trace performance test for a motion page.
 *
 *   node perf_test.js <url|animation.html|project_dir> [--cpu 4] [--passes 2] [--mode seek|live]
 *                     [--trigger "js to start the animation"] [--duration 2] [--out out/perf.json]
 *                     [--width 390 --height 844 --dpr 3]
 *
 * mode seek (default): plays the registered timeline in real time by calling
 *   window.__motion.seek(elapsed) from requestAnimationFrame: measures the cost of the
 *   page's own seek/style work, layout and paint, under CPU throttling.
 * mode live: loads the page as-is (no ?embed), optionally runs --trigger (e.g. a click),
 *   and records for --duration seconds: measures shipped runtime code.
 *
 * Reports frame-time p50/p95/p99, dropped frames, long tasks (>50 ms), and Layout,
 * Paint and style-recalc events per frame during the measured window.
 * Pass: no dropped frames and p95 <= 1.1 × vsync (rAF jitter tolerated), 0 long tasks,
 * layout cost <= 0.5 ms/frame, and Layout on <= 10% of frames. Pages whose text legitimately
 * changes (counters) declare it: Motion.register({ perf: { maxLayoutPerFrame: 0.3,
 * reason: "counter text" } }); the allowance and its reason are printed in the report.
 */
"use strict";
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");
const { startServer, toUrl } = require("./_serve_static");

function arg(name, def) {
  const i = process.argv.indexOf("--" + name);
  if (i < 0) return def;
  const v = process.argv[i + 1];
  return v === undefined || v.startsWith("--") ? true : isNaN(+v) ? v : +v;
}
const pct = (arr, p) => { if (!arr.length) return 0; const s = [...arr].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.floor(p / 100 * s.length))]; };

async function main() {
  const target = process.argv[2];
  if (!target || target.startsWith("--") || process.argv.includes("--help")) {
    console.log(fs.readFileSync(__filename, "utf8").split("\n").slice(2, 20).map((l) => l.replace(/^ \* ?/, "")).join("\n"));
    process.exit(target ? 0 : 2);
  }
  const cpu = arg("cpu", 4), passes = arg("passes", 2), mode = arg("mode", "seek");
  const server = await startServer(target);
  const url = toUrl(server, target, mode === "seek" ? { embed: 1 } : {});
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: arg("width", 1280), height: arg("height", 900) },
    deviceScaleFactor: arg("dpr", 1),
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(url, { waitUntil: "load" });
  let meta = null;
  if (mode === "seek") {
    await page.waitForFunction(() => window.__motion, null, { timeout: 10000 });
    meta = await page.evaluate(async () => { await window.__motion.ready; const m = window.__motion;
      return { name: m.name, version: m.version, duration: m.duration, width: m.width, height: m.height, perf: (m.def && m.def.perf) || null }; });
    await page.setViewportSize({ width: meta.width, height: meta.height });
  }
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: cpu });

  const categories = ["devtools.timeline", "disabled-by-default-devtools.timeline", "disabled-by-default-devtools.timeline.frame", "blink.user_timing", "toplevel"];
  await browser.startTracing(page, { categories });
  const duration = mode === "seek" ? meta.duration * passes : arg("duration", 2);
  const frames = await page.evaluate(async ({ mode, duration, trigger, passes }) => {
    const intervals = [];
    performance.mark("motion-start");
    if (mode === "live" && trigger) (0, eval)(trigger);
    await new Promise((resolve) => {
      let t0 = null, last = null;
      const step = (now) => {
        if (t0 === null) t0 = now;
        if (last !== null) intervals.push(now - last);
        last = now;
        const el = (now - t0) / 1000;
        if (mode === "seek") window.__motion.seek(el % window.__motion.duration);
        if (el < duration) requestAnimationFrame(step); else resolve();
      };
      requestAnimationFrame(step);
    });
    performance.mark("motion-end");
    return intervals;
  }, { mode, duration, trigger: arg("trigger", null), passes });
  const trace = JSON.parse((await browser.stopTracing()).toString());
  await browser.close();
  server && server.close();

  const ev = trace.traceEvents || trace;
  const mark = (n) => (ev.find((e) => e.name === n) || {}).ts;
  const a = mark("motion-start"), b = mark("motion-end");
  const inWin = ev.filter((e) => a && b && e.ts >= a && e.ts <= b);
  const count = (names) => inWin.filter((e) => names.includes(e.name) && (e.ph === "X" || e.ph === "B" || e.ph === "I")).length;
  const layoutMs = inWin.filter((e) => e.name === "Layout" && e.ph === "X").reduce((a, e) => a + (e.dur || 0), 0) / 1000;
  const longTasks = inWin.filter((e) => (e.name === "RunTask" || e.name === "ThreadControllerImpl::RunTask") && e.dur > 50000).map((e) => +(e.dur / 1000).toFixed(1));
  const n = frames.length || 1;
  const vsync = pct(frames, 50);
  const dropped = frames.filter((f) => f > vsync * 1.5).length;
  const report = {
    target, mode, cpuThrottle: cpu, frames: frames.length,
    frameMs: { p50: +pct(frames, 50).toFixed(2), p95: +pct(frames, 95).toFixed(2), p99: +pct(frames, 99).toFixed(2), max: +Math.max(...frames, 0).toFixed(2) },
    droppedFrames: dropped,
    longTasksMs: longTasks,
    perFrame: {
      layout: +(count(["Layout"]) / n).toFixed(3),
      layoutMs: +(layoutMs / n).toFixed(3),
      styleRecalc: +(count(["UpdateLayoutTree", "RecalculateStyles"]) / n).toFixed(3),
      paint: +(count(["Paint"]) / n).toFixed(3),
    },
    pageErrors: errors,
  };
  const fails = [];
  if (dropped > 0) fails.push(`${dropped} dropped frame(s)`);
  if (report.frameMs.p95 > vsync * 1.1) fails.push(`p95 frame ${report.frameMs.p95}ms > 1.1 × vsync (${vsync.toFixed(1)}ms)`);
  if (longTasks.length) fails.push(`${longTasks.length} long task(s) during motion`);
  const allowance = meta && meta.perf && meta.perf.maxLayoutPerFrame != null ? meta.perf : null;
  const maxLayout = allowance ? allowance.maxLayoutPerFrame : 0.1;
  if (allowance) report.layoutAllowance = allowance;
  if (report.perFrame.layoutMs > 0.5) fails.push(`layout costs ${report.perFrame.layoutMs}ms/frame`);
  if (report.perFrame.layout > maxLayout) fails.push(`layout on ${report.perFrame.layout} of frames (max ${maxLayout}): something animates a layout property (SVG child transforms count)`);
  if (errors.length) fails.push("page errors");
  report.pass = fails.length === 0;
  report.failures = fails;

  const out = arg("out", null);
  if (out) { fs.mkdirSync(path.dirname(out), { recursive: true }); fs.writeFileSync(out, JSON.stringify(report, null, 2)); }
  console.log(`perf_test ${meta ? meta.name + " v" + meta.version : target}  (${mode}, CPU ${cpu}×, ${report.frames} frames)`);
  console.log(`  frame ms  p50 ${report.frameMs.p50}  p95 ${report.frameMs.p95}  p99 ${report.frameMs.p99}  max ${report.frameMs.max}  dropped ${dropped}`);
  console.log(`  per frame  layout ${report.perFrame.layout} (${report.perFrame.layoutMs}ms)  style ${report.perFrame.styleRecalc}  paint ${report.perFrame.paint}   long tasks ${longTasks.length}`);
  if (allowance) console.log(`  layout allowance ${allowance.maxLayoutPerFrame}/frame declared by the page: ${allowance.reason || "(no reason given)"}`);
  console.log(report.pass ? "PASS" : "FAIL " + fails.join("; "));
  process.exit(report.pass ? 0 : 1);
}

main().catch((e) => { console.error("error:", e.message); process.exit(2); });
