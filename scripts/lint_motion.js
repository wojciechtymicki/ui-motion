#!/usr/bin/env node
/*
 * Static checks on shipped motion code (web, SwiftUI, Compose, React Native).
 *
 *   node lint_motion.js <file|dir> [...] [--tokens path/to/motion.tokens.ts] [--json]
 *
 * Errors (exit 1):
 *   layout-property     animating width/height/top/left/right/bottom/margin/padding/font-size
 *   transition-all      `transition: all` (animates layout properties by accident)
 *   timer-driven        setTimeout/setInterval in a file that writes transforms/animates
 *   random-in-motion    Math.random in animation code (non-deterministic)
 *   no-reduced-motion   animates but never checks a reduced-motion preference
 *   seek-impure         Date.now/performance.now inside a seek(t)
 * Warnings:
 *   magic-number        literal durations/springs outside the token module (CSS custom
 *                       property definitions `--x: 200ms` count as tokens)
 *   linear-movement     linear easing on translation (fine for rotation/progress/marquee)
 *   will-change-static  will-change in static CSS rules (promote just before animating)
 *   hover-ungated       :hover motion without an (hover: hover) media query
 *   js-thread-anim      React Native Animated without useNativeDriver / setState-driven animation
 */
"use strict";
const fs = require("fs");
const path = require("path");

const EXT = new Set([".js", ".jsx", ".ts", ".tsx", ".mjs", ".css", ".scss", ".html", ".vue", ".svelte", ".swift", ".kt"]);
const SKIP = new Set(["node_modules", ".git", "out", "dist", "build", ".venv", "__pycache__"]);

function walk(p, acc) {
  const st = fs.statSync(p);
  if (st.isDirectory()) {
    for (const n of fs.readdirSync(p)) if (!SKIP.has(n)) walk(path.join(p, n), acc);
  } else if (EXT.has(path.extname(p))) acc.push(p);
  return acc;
}

const LAYOUT = "(?:width|height|top|left|right|bottom|margin(?:-\\w+)?|padding(?:-\\w+)?|font-size|fontSize|marginTop|marginLeft|paddingTop|paddingLeft)";
const RULES = [
  { id: "transition-all", level: "error", re: /transition(?:-property)?\s*:\s*all\b/, msg: "`transition: all` animates layout properties by accident; list transform/opacity explicitly" },
  { id: "layout-property", level: "error", re: new RegExp(`transition(?:-property)?\\s*:[^;{}]*\\b${LAYOUT}\\b`), msg: "transition on a layout property; animate transform/opacity (FLIP for size changes)" },
  { id: "layout-property", level: "error", re: new RegExp(`\\.animate\\(\\s*[\\[{][^)]*\\b${LAYOUT}\\s*:`), msg: "WAAPI/Motion animating a layout property; use transform (FLIP)" },
  { id: "layout-property", level: "error", re: new RegExp(`(?:animate|initial|exit|whileHover|whileTap)\\s*=\\s*\\{\\{[^}]*\\b(?:width|height|top|left)\\s*:`), msg: "Motion prop animating layout; use `layout` or transforms" },
  { id: "random-in-motion", level: "error", re: /Math\.random\s*\(/, onlyIf: /seek\s*\(|animate\(|requestAnimationFrame|keyframes|Motion\.register/, msg: "Math.random in animation code; use a seeded PRNG (mulberry32) created once" },
  { id: "linear-movement", level: "warn", re: /(translate|\bx\b|\by\b)[^;\n]{0,80}\blinear\b|\blinear\b[^;\n]{0,80}translate/, msg: "linear easing on movement; linear is for rotation/progress/marquees only" },
  { id: "linear-movement", level: "warn", re: /\.animation\(\.linear|withAnimation\(\.linear/, msg: "SwiftUI linear animation; use a spring or eased curve unless this is rotation/progress" },
  { id: "will-change-static", level: "warn", re: /will-change\s*:\s*(?!auto)/, cssOnly: true, msg: "static will-change keeps a layer forever; set it just before animating and remove after" },
  { id: "js-thread-anim", level: "warn", re: /Animated\.timing\((?![^)]*useNativeDriver\s*:\s*true)/, msg: "RN Animated without useNativeDriver: true runs on the JS thread; prefer Reanimated" },
];

const ANIMATES = /transition\s*:|@keyframes|\.animate\(|animate=\{|withAnimation|\.animation\(|animate\w*AsState|Animatable\(|withSpring|withTiming|Motion\.register|gsap\.|lottie|requestAnimationFrame|transform\s*=|style\.transform/;
const REDUCED = /prefers-reduced-motion|useReducedMotion|accessibilityReduceMotion|isReduceMotionEnabled|ReduceMotion|ANIMATOR_DURATION_SCALE|Motion\.reduced|\breduced\b|reduceMotion|shouldReduceMotion/;
const TIMERS = /\bset(?:Timeout|Interval)\s*\(/;
const WRITES_MOTION = /style\.(?:transform|opacity|left|top|right|bottom|width|height)\s*=|\.animate\(|transform\s*:|translate/;
const LAYOUT_WRITE = /style\.(?:width|height|top|left|right|bottom|margin\w*|padding\w*|fontSize)\s*=/;

function lintFile(file, tokensFile) {
  const text = fs.readFileSync(file, "utf8");
  const lines = text.split("\n");
  const isCss = /\.(css|scss)$/.test(file);
  // seek(t) review sources (pages and their scene modules built on motion-runtime helpers):
  // literal values there ARE the spec, so magic-number/will-change rules don't apply.
  const isReviewPage = /Motion\.register\(|=\s*Motion\s*;|Motion\.(?:tween|spring|ease)\b/.test(text);
  // HTML pages: include local <script src> modules when checking file-level rules.
  let withIncludes = text;
  if (/\.html$/.test(file)) {
    for (const m of text.matchAll(/<script[^>]+src=["']([^"':]+)["']/g)) {
      const inc = path.join(path.dirname(file), m[1]);
      if (fs.existsSync(inc) && !/motion-runtime\.js$/.test(inc)) withIncludes += "\n" + fs.readFileSync(inc, "utf8");
    }
  }
  const isTokens = tokensFile && path.resolve(file) === path.resolve(tokensFile) || /tokens?\.(ts|js|json|swift|kt)$/i.test(file);
  const out = [];
  const push = (line, level, id, msg) => out.push({ file, line, level, id, msg });

  lines.forEach((ln, i) => {
    if (/lint-motion-ignore/.test(ln)) return;
    for (const r of RULES) {
      if (r.cssOnly && !isCss && !/<style/.test(text)) continue;
      if (r.cssOnly && isReviewPage) continue;
      if (r.onlyIf && !r.onlyIf.test(text)) continue;
      if (r.re.test(ln)) push(i + 1, r.level, r.id, r.msg);
    }
    // Magic numbers: literal durations in animation calls outside tokens.
    if (!isTokens && !isReviewPage && !/^\s*--[\w-]+\s*:/.test(ln) && /(duration|delay)\s*[:=]\s*\d|\b\d{2,4}ms\b|response:\s*0?\.\d|stiffness\s*[:=]\s*\d|damping\s*[:=]\s*\d|tween\(\s*\d{2,4}/.test(ln)
        && !/Motion\.register|fps\s*:|duration:\s*\{\{/.test(ln))
      push(i + 1, "warn", "magic-number", "literal motion value; move it to the motion token module");
    // :hover motion without a hover media query
    if (/:hover\b/.test(ln) && /(transform|translate|scale)/.test(lines.slice(i, i + 4).join(" ")) && !/\(hover:\s*hover\)/.test(text))
      push(i + 1, "warn", "hover-ungated", ":hover motion without @media (hover: hover): sticks after tap on touch devices");
  });

  if (ANIMATES.test(text)) {
    const timerLine = lines.findIndex((l) => TIMERS.test(l) && !/lint-motion-ignore/.test(l));
    if (timerLine >= 0 && WRITES_MOTION.test(text)) {
      const ln = timerLine;
      push(ln + 1, "error", "timer-driven", "timers alongside motion writes: drive motion from time (rAF/seek(t)/animation APIs), not setTimeout/setInterval");
    }
    if (!REDUCED.test(withIncludes) && !isTokens)
      push(1, "error", "no-reduced-motion", "file animates but never checks reduced motion (prefers-reduced-motion / useReducedMotion / accessibilityReduceMotion)");
  }
  // Impure seek: wall clock inside seek(t) { ... }
  const seekMatch = /seek\s*\(\s*t\s*\)\s*\{/.exec(text);
  if (seekMatch) {
    let depth = 0, j = seekMatch.index + seekMatch[0].length - 1, start = j;
    for (; j < text.length; j++) { if (text[j] === "{") depth++; else if (text[j] === "}" && --depth === 0) break; }
    const body = text.slice(start, j);
    const ln0 = text.slice(0, start).split("\n").length;
    if (/Date\.now|performance\.now|new Date\(/.test(body))
      push(ln0, "error", "seek-impure", "seek(t) reads the wall clock; frames must depend on t only");
    body.split("\n").forEach((l, k) => {
      if (LAYOUT_WRITE.test(l) && !/lint-motion-ignore/.test(l))
        push(ln0 + k, "error", "layout-property", "seek(t) writes a layout property every frame; use transform (FLIP) or mark one small element with // lint-motion-ignore");
    });
  }
  return out;
}

function main() {
  const args = process.argv.slice(2);
  if (!args.length || args.includes("--help")) {
    console.log(fs.readFileSync(__filename, "utf8").split("\n").slice(2, 22).map((l) => l.replace(/^ \* ?/, "")).join("\n"));
    process.exit(args.length ? 0 : 2);
  }
  const json = args.includes("--json");
  const ti = args.indexOf("--tokens");
  const tokens = ti >= 0 ? args[ti + 1] : null;
  const targets = args.filter((a, i) => !a.startsWith("--") && !(ti >= 0 && i === ti + 1));
  const files = [];
  for (const t of targets) {
    if (!fs.existsSync(t)) { console.error(`error: ${t} not found`); process.exit(2); }
    walk(t, files);
  }
  const results = files.flatMap((f) => lintFile(f, tokens));
  if (json) console.log(JSON.stringify(results, null, 2));
  else {
    for (const r of results) console.log(`${r.file}:${r.line}  ${r.level.toUpperCase().padEnd(5)} ${r.id.padEnd(18)} ${r.msg}`);
    const e = results.filter((r) => r.level === "error").length, w = results.length - e;
    console.log(`\nlint_motion: ${files.length} files, ${e} errors, ${w} warnings`);
  }
  process.exit(results.some((r) => r.level === "error") ? 1 : 0);
}

if (require.main === module) main();
module.exports = { lintFile };
