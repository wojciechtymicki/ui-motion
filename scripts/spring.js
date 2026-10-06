#!/usr/bin/env node
/*
 * Closed-form spring solver: the same math as templates/motion-runtime.js.
 *
 *   node spring.js --stiffness 400 --damping 38 [--mass 1] [--velocity 0]
 *   node spring.js --response 0.31 --damping-ratio 0.95      # SwiftUI-style input
 *   node spring.js --duration 0.31 --bounce 0.05             # iOS 17 / Motion-style input
 *   node spring.js --settle 0.4 --damping-ratio 0.9          # solve stiffness for a settle time
 *   node spring.js ... --css                                 # also print a CSS linear() easing
 *   node spring.js ... --json
 *
 * Prints: damping ratio ζ, natural frequency, t90 (looks done), settle (0.1%), overshoot,
 * and the equivalent config for SwiftUI, iOS 17, UIKit, Compose, Motion, Reanimated.
 */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

function loadRuntime() {
  const src = fs.readFileSync(path.join(__dirname, "..", "templates", "motion-runtime.js"), "utf8");
  const sandbox = { window: { location: { search: "" } }, document: undefined, URLSearchParams };
  sandbox.window.window = sandbox.window;
  vm.runInNewContext(src, sandbox);
  return sandbox.window.Motion;
}

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith("--")) continue;
    const k = a.slice(2);
    const v = argv[i + 1];
    if (v === undefined || v.startsWith("--")) out[k] = true;
    else { out[k] = isNaN(+v) ? v : +v; i++; }
  }
  return out;
}

function analyse(Motion, cfg) {
  const s = Motion.spring(cfg);
  const z = s.zeta, w0 = s.omega;
  let t90 = null, peak = 0;
  for (let t = 0; t <= Math.max(s.settle, 0.001) + 0.001; t += 0.0005) {
    const x = s(t);
    if (t90 === null && x >= 0.9) t90 = t;
    peak = Math.max(peak, x);
  }
  const response = (2 * Math.PI) / w0;
  return {
    stiffness: cfg.stiffness, damping: cfg.damping, mass: cfg.mass, velocity: cfg.velocity,
    dampingRatio: +z.toFixed(4), omega: +w0.toFixed(3),
    t90: t90 === null ? null : +t90.toFixed(3), settle: s.settle,
    overshootPct: +(Math.max(0, peak - 1) * 100).toFixed(2),
    swiftui: { response: +response.toFixed(3), dampingFraction: +z.toFixed(3) },
    ios17: { duration: +response.toFixed(3), bounce: +Math.max(0, 1 - z).toFixed(3) },
    uikit: { mass: cfg.mass, stiffness: cfg.stiffness, damping: cfg.damping },
    compose: { dampingRatio: +z.toFixed(3), stiffness: +(cfg.stiffness / cfg.mass).toFixed(1) },
    motion: { type: "spring", stiffness: cfg.stiffness, damping: cfg.damping, mass: cfg.mass },
    reanimated: { stiffness: cfg.stiffness, damping: cfg.damping, mass: cfg.mass },
    fn: s,
  };
}

function cssLinear(s, points = 40) {
  const pts = [];
  for (let i = 0; i <= points; i++) pts.push(+s(s.settle * i / points).toFixed(4));
  return { easing: `linear(${pts.join(", ")})`, durationMs: Math.round(s.settle * 1000) };
}

function main() {
  const a = parseArgs(process.argv.slice(2));
  if (a.help || a.h || Object.keys(a).length === 0) {
    console.log(fs.readFileSync(__filename, "utf8").split("\n").slice(2, 15).map((l) => l.replace(/^ \* ?/, "")).join("\n"));
    process.exit(0);
  }
  const Motion = loadRuntime();
  const mass = a.mass || 1;
  let k, c;
  const zeta = a["damping-ratio"] ?? a.zeta ?? (a.bounce != null ? 1 - a.bounce : undefined);
  if (a.stiffness != null && a.damping != null) { k = a.stiffness; c = a.damping; }
  else if ((a.response != null || a.duration != null) && zeta != null) {
    const resp = a.response ?? a.duration;
    const w0 = (2 * Math.PI) / resp;
    k = w0 * w0 * mass; c = 2 * zeta * Math.sqrt(k * mass);
  } else if (a.settle != null && zeta != null) {
    // Bisection on stiffness for the requested 0.1% settle time.
    let lo = 1, hi = 20000;
    for (let i = 0; i < 60; i++) {
      const mid = Math.sqrt(lo * hi);
      const s = Motion.spring({ stiffness: mid, damping: 2 * zeta * Math.sqrt(mid * mass), mass });
      if (s.settle > a.settle) lo = mid; else hi = mid;
    }
    k = hi; c = 2 * zeta * Math.sqrt(k * mass);
  } else {
    console.error("error: give --stiffness + --damping, or --response/--duration + --damping-ratio/--bounce, or --settle + --damping-ratio");
    process.exit(2);
  }
  k = +k.toFixed(2); c = +c.toFixed(3);
  const r = analyse(Motion, { stiffness: k, damping: c, mass, velocity: a.velocity || 0 });
  const css = a.css ? cssLinear(r.fn) : null;
  delete r.fn;
  if (css) r.css = css;
  if (a.json) { console.log(JSON.stringify(r, null, 2)); return; }
  console.log(`spring  k=${k}  c=${c}  m=${mass}${a.velocity ? `  v0=${a.velocity}` : ""}`);
  console.log(`  ζ ${r.dampingRatio}   ω0 ${r.omega} rad/s   t90 ${r.t90}s   settle ${r.settle}s   overshoot ${r.overshootPct}%`);
  console.log(`  SwiftUI   .spring(response: ${r.swiftui.response}, dampingFraction: ${r.swiftui.dampingFraction})`);
  console.log(`  iOS 17    .spring(duration: ${r.ios17.duration}, bounce: ${r.ios17.bounce})`);
  console.log(`  UIKit     UISpringTimingParameters(mass: ${mass}, stiffness: ${k}, damping: ${c}, initialVelocity: …)`);
  console.log(`  Compose   spring(dampingRatio = ${r.compose.dampingRatio}f, stiffness = ${r.compose.stiffness}f)`);
  console.log(`  Motion    { type: "spring", stiffness: ${k}, damping: ${c}, mass: ${mass} }`);
  console.log(`  Reanimated withSpring(to, { stiffness: ${k}, damping: ${c}, mass: ${mass} })`);
  if (css) console.log(`  CSS       transition: transform ${css.durationMs}ms ${css.easing}`);
}

if (require.main === module) main();
module.exports = { loadRuntime, analyse, cssLinear };
