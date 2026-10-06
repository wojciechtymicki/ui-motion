/*!
 * motion-runtime.js — the seek(t) contract for ui-motion.
 *
 * Every animation is a pure function of time. A page registers itself once:
 *
 *   Motion.register({
 *     name: "onboarding-2", version: 3, duration: 2.4, fps: 60,
 *     width: 390, height: 844,
 *     seek(t) { ... set every element's state for time t ... },
 *     ready: Promise,          // optional; fonts are always awaited
 *     holds: [[2.4, 3.0]],     // optional; intentional still intervals (justify them in the spec)
 *     perf: { maxLayoutPerFrame: 0.3, reason: "counter text" },  // optional; declared layout allowance
 *     live() { ... }           // optional; wires real input outside the player
 *   });
 *
 * The player, render.py, contact_sheet.py and every test drive the same
 * window.__motion.seek(t). Nothing here uses wall-clock timers to decide what
 * a frame looks like; the only clock is the optional standalone preview loop,
 * which just calls seek(t) with elapsed time.
 *
 * Modes (from the query string):
 *   ?embed=1    loaded by the player or a capture script: no autoplay, stage at 0,0
 *   ?render=1   capture mode (implies embed): transparent page background
 *   ?reduced=1  force the reduced-motion version (also read from the media query)
 *   ?t=1.2      standalone: start paused at this time
 */
(function (global) {
  "use strict";

  // Bump when the runtime changes; capture scripts warn when a project's copy is older.
  var RUNTIME_VERSION = 2;

  var params = new URLSearchParams(global.location ? global.location.search : "");
  var EMBED = params.get("embed") === "1" || params.get("render") === "1";
  var RENDER = params.get("render") === "1";
  var REDUCED =
    params.get("reduced") === "1" ||
    (params.get("reduced") !== "0" &&
      !!(global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches));

  // ---------------------------------------------------------------- math

  function clamp(v, lo, hi) {
    if (lo === undefined) lo = 0;
    if (hi === undefined) hi = 1;
    return v < lo ? lo : v > hi ? hi : v;
  }
  function mix(a, b, p) { return a + (b - a) * p; }
  /** Normalised progress of t inside [start, start + dur], clamped to 0..1. */
  function progress(t, start, dur) {
    if (dur <= 0) return t >= start ? 1 : 0;
    return clamp((t - start) / dur);
  }

  // ---------------------------------------------------------------- easing
  // Every easing returns exactly 0 at p<=0 and exactly 1 at p>=1.

  function exact(f) {
    return function (p) { return p <= 0 ? 0 : p >= 1 ? 1 : f(p); };
  }

  /** CSS-equivalent cubic-bezier(x1, y1, x2, y2). Newton with bisection fallback. */
  function cubicBezier(x1, y1, x2, y2) {
    function bx(s) { return 3 * x1 * s * (1 - s) * (1 - s) + 3 * x2 * s * s * (1 - s) + s * s * s; }
    function by(s) { return 3 * y1 * s * (1 - s) * (1 - s) + 3 * y2 * s * s * (1 - s) + s * s * s; }
    function dx(s) { return 3 * x1 * (1 - s) * (1 - s) + 6 * (x2 - x1) * s * (1 - s) + 3 * (1 - x2) * s * s; }
    function solve(x) {
      var s = x, i;
      for (i = 0; i < 8; i++) {
        var err = bx(s) - x;
        if (Math.abs(err) < 1e-7) return s;
        var d = dx(s);
        if (Math.abs(d) < 1e-6) break;
        s -= err / d;
      }
      var lo = 0, hi = 1;
      s = x;
      for (i = 0; i < 40; i++) {
        var v = bx(s);
        if (Math.abs(v - x) < 1e-7) return s;
        if (v < x) lo = s; else hi = s;
        s = (lo + hi) / 2;
      }
      return s;
    }
    var f = exact(function (p) { return by(solve(p)); });
    f.css = "cubic-bezier(" + [x1, y1, x2, y2].join(", ") + ")";
    return f;
  }

  // Named curves. Values and character are documented in references/curves.md.
  var ease = {
    linear: exact(function (p) { return p; }),
    standard: cubicBezier(0.2, 0, 0, 1),        // decisive, settles softly
    out: cubicBezier(0.16, 1, 0.3, 1),          // expo-ish out, for entrances
    outQuart: cubicBezier(0.25, 1, 0.5, 1),
    outCubic: cubicBezier(0.33, 1, 0.68, 1),
    in: cubicBezier(0.55, 0, 1, 0.45),          // exits: leave accelerating
    inCubic: cubicBezier(0.32, 0, 0.67, 0),
    inOut: cubicBezier(0.65, 0, 0.35, 1),       // on-screen to on-screen travel
    inOutCubic: cubicBezier(0.65, 0, 0.35, 1),
    emphasized: cubicBezier(0.3, 0, 0, 1),
    emphasizedAccel: cubicBezier(0.3, 0, 0.8, 0.15),
    emphasizedDecel: cubicBezier(0.05, 0.7, 0.1, 1),
    anticipate: cubicBezier(0.36, 0, 0.66, -0.56),
    backOut: cubicBezier(0.34, 1.36, 0.64, 1),  // restrained overshoot (~6%)
    sine: exact(function (p) { return -(Math.cos(Math.PI * p) - 1) / 2; })
  };

  // ---------------------------------------------------------------- spring
  /**
   * Closed-form damped harmonic oscillator from 0 to 1.
   * spring({stiffness, damping, mass, velocity})(t) -> position (0 -> 1, may overshoot).
   * velocity is the initial velocity in "units of the full travel per second"
   * (a gesture moving 300px/s into a 150px travel => velocity 2).
   * The returned function also carries: .velocity(t), .settle (seconds to stay
   * within 0.1% of travel), .zeta (damping ratio), .omega (natural freq, rad/s).
   */
  function spring(cfg) {
    cfg = cfg || {};
    var k = cfg.stiffness != null ? cfg.stiffness : 300;
    var c = cfg.damping != null ? cfg.damping : 30;
    var m = cfg.mass != null ? cfg.mass : 1;
    var v0 = cfg.velocity || 0;
    var w0 = Math.sqrt(k / m);
    var z = c / (2 * Math.sqrt(k * m));
    var pos, vel;

    if (z < 1 - 1e-9) {
      var wd = w0 * Math.sqrt(1 - z * z);
      var A = -1, B = (v0 + z * w0 * A) / wd;
      pos = function (t) {
        var e = Math.exp(-z * w0 * t);
        return 1 + e * (A * Math.cos(wd * t) + B * Math.sin(wd * t));
      };
      vel = function (t) {
        var e = Math.exp(-z * w0 * t), cs = Math.cos(wd * t), sn = Math.sin(wd * t);
        return e * ((-z * w0) * (A * cs + B * sn) + (-A * wd * sn + B * wd * cs));
      };
    } else if (z <= 1 + 1e-9) {
      var A1 = -1, B1 = v0 + w0 * A1;
      pos = function (t) { return 1 + (A1 + B1 * t) * Math.exp(-w0 * t); };
      vel = function (t) { return Math.exp(-w0 * t) * (B1 - w0 * (A1 + B1 * t)); };
    } else {
      var sq = Math.sqrt(z * z - 1);
      var r1 = -w0 * (z - sq), r2 = -w0 * (z + sq);
      var C2 = (v0 + r1) / (r2 - r1), C1 = -1 - C2;
      pos = function (t) { return 1 + C1 * Math.exp(r1 * t) + C2 * Math.exp(r2 * t); };
      vel = function (t) { return C1 * r1 * Math.exp(r1 * t) + C2 * r2 * Math.exp(r2 * t); };
    }

    // Settle: last time |x-1| or |v|/w0 exceeds 0.1% of travel, scanned at 1ms.
    var settle = 0, eps = 0.001;
    for (var t = 0; t < 10; t += 0.001) {
      if (Math.abs(pos(t) - 1) > eps || Math.abs(vel(t)) / Math.max(w0, 1) > eps) settle = t;
    }
    settle = Math.round((settle + 0.001) * 1000) / 1000;

    var f = function (t) {
      if (t <= 0) return 0;
      if (t >= settle) return 1;
      return pos(t);
    };
    f.velocity = function (t) { return t <= 0 ? v0 : t >= settle ? 0 : vel(t); };
    f.settle = settle;
    f.zeta = z;
    f.omega = w0;
    f.config = { stiffness: k, damping: c, mass: m, velocity: v0 };
    return f;
  }

  /** Spring presets. Character notes live in references/curves.md. */
  var springs = {
    snappy: { stiffness: 520, damping: 42, mass: 1 },   // zeta 0.92
    smooth: { stiffness: 260, damping: 32, mass: 1 },   // zeta 0.99
    gentle: { stiffness: 170, damping: 24, mass: 1 },   // zeta 0.92
    lively: { stiffness: 380, damping: 26, mass: 1 },   // zeta 0.67, ~5% overshoot
    press:  { stiffness: 900, damping: 50, mass: 1 }    // zeta 0.83, touch-down
  };

  // ---------------------------------------------------------------- tweens

  /** tween(t, start, dur, from, to, easeFn) -> value. Holds `from` before, `to` after. */
  function tween(t, start, dur, from, to, e) {
    return mix(from, to, (e || ease.standard)(progress(t, start, dur)));
  }
  /** springTo(t, start, from, to, cfgOrSpring) -> value driven by a closed-form spring. */
  function springTo(t, start, from, to, s) {
    var f = typeof s === "function" ? s : spring(s);
    return mix(from, to, f(t - start));
  }
  /** Delay for the i-th follower. step in seconds; optional cap keeps a group inside a window. */
  function stagger(i, step, cap) {
    var d = i * step;
    return cap != null ? Math.min(d, cap) : d;
  }
  /**
   * Keyframes: kf(t, [[time, value, easeIntoThisKey?], ...]).
   * Holds the first value before the first key and the last value after the last.
   */
  function keyframes(t, keys) {
    if (t <= keys[0][0]) return keys[0][1];
    for (var i = 1; i < keys.length; i++) {
      if (t <= keys[i][0]) {
        var a = keys[i - 1], b = keys[i];
        return mix(a[1], b[1], (b[2] || ease.standard)(progress(t, a[0], b[0] - a[0])));
      }
    }
    return keys[keys.length - 1][1];
  }

  // ---------------------------------------------------------------- randomness

  /** Seeded PRNG. Never use Math.random in motion: renders must be deterministic. */
  function mulberry32(seed) {
    var a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) >>> 0;
      var r = Math.imul(a ^ (a >>> 15), 1 | a);
      r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
      return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
    };
  }

  // ---------------------------------------------------------------- demo timeline
  /**
   * For interactive pieces: a scripted sequence of states as a function of t,
   * so hover/press/drag responses are scrubbable in the player.
   *   var demo = [{at: 0, state: "idle"}, {at: 0.6, state: "hover"}, {at: 1.1, state: "press"}];
   *   var s = Motion.demoState(t, demo);  // {state, prev, since, at, index}
   * Animate each state change from `prev` to `state` using `since` (seconds in state).
   */
  function demoState(t, script) {
    var idx = 0;
    for (var i = 0; i < script.length; i++) if (t >= script[i].at) idx = i;
    var cur = script[idx];
    return {
      state: cur.state,
      prev: idx > 0 ? script[idx - 1].state : cur.state,
      since: Math.max(0, t - cur.at),
      at: cur.at,
      index: idx,
      data: cur
    };
  }
  /**
   * Pointer path for explainers: path(t, [[time, x, y], ...], easeFn) -> {x, y}.
   * Cursors move on curved, eased paths; never linear between targets.
   */
  function path(t, points, e) {
    return {
      x: keyframes(t, points.map(function (p) { return [p[0], p[1], e || ease.inOut]; })),
      y: keyframes(t, points.map(function (p) { return [p[0], p[2], e || ease.inOut]; }))
    };
  }

  // ---------------------------------------------------------------- registration

  var current = null;

  function register(def) {
    if (current) throw new Error("Motion.register called twice on one page");
    ["name", "duration", "seek"].forEach(function (k) {
      if (def[k] == null) throw new Error("Motion.register: missing '" + k + "'");
    });
    var fps = def.fps || 60;
    var duration = +def.duration;
    var t = 0;
    var errors = [];

    var fontsReady = global.document && document.fonts ? document.fonts.ready : Promise.resolve();
    var ready = Promise.all([fontsReady, def.ready || Promise.resolve()]).then(function () {
      api.seek(t);
      return true;
    });

    var api = {
      name: def.name,
      version: def.version || 1,
      duration: duration,
      fps: fps,
      width: def.width || 800,
      height: def.height || 600,
      loops: !!def.loops,
      // Intentional still intervals [[start, end], ...] (e.g. a result state on display in a
      // demo timeline). jank_check.py does not report dead frames inside them.
      holds: (def.holds || []).map(function (h) { return [+h[0], +h[1]]; }),
      reduced: REDUCED,
      frames: Math.round(duration * fps),
      ready: ready,
      errors: errors,
      seek: function (time) {
        t = clamp(+time || 0, 0, duration);
        try { def.seek(t); }
        catch (err) { errors.push(String(err && err.stack || err)); throw err; }
        return t;
      },
      seekFrame: function (frame) { return api.seek(frame / fps); },
      time: function () { return t; },
      frameOf: function (time) { return Math.floor(time * fps + 1e-6); },
      def: def
    };
    current = api;
    global.__motion = api;

    var stage = document.getElementById("stage");
    if (stage) {
      stage.style.width = api.width + "px";
      stage.style.height = api.height + "px";
    }
    document.documentElement.classList.toggle("motion-embed", EMBED);
    document.documentElement.classList.toggle("motion-render", RENDER);
    document.documentElement.classList.toggle("motion-reduced", REDUCED);
    document.title = def.name + " v" + api.version;

    // Initial frame right away so there is never an unstyled flash.
    api.seek(params.has("t") ? +params.get("t") : 0);

    if (!EMBED) ready.then(function () {
      if (typeof def.live === "function") def.live(api);
      else if (!params.has("t")) standalonePreview(api);
    });
    return api;
  }

  // Standalone preview (opening animation.html directly): loop the timeline.
  // Pause with Space. This is the only place a wall clock is used, and it only
  // chooses which t to seek to.
  function standalonePreview(api) {
    var start = null, paused = false, pausedAt = 0;
    function frame(now) {
      if (!paused) {
        if (start == null) start = now - pausedAt * 1000;
        var el = (now - start) / 1000;
        var hold = api.loops ? 0 : 0.8;
        var cycle = api.duration + hold;
        api.seek(Math.min(el % cycle, api.duration));
      }
      requestAnimationFrame(frame);
    }
    document.addEventListener("keydown", function (e) {
      if (e.code !== "Space") return;
      e.preventDefault();
      paused = !paused;
      if (paused) pausedAt = api.time(); else start = null;
    });
    requestAnimationFrame(frame);
  }

  global.Motion = {
    register: register,
    clamp: clamp, mix: mix, progress: progress,
    ease: ease, cubicBezier: cubicBezier,
    spring: spring, springs: springs, springTo: springTo,
    tween: tween, stagger: stagger, keyframes: keyframes,
    mulberry32: mulberry32,
    demoState: demoState, path: path,
    reduced: REDUCED, embed: EMBED, render: RENDER, runtimeVersion: RUNTIME_VERSION,
    get current() { return current; }
  };
})(window);
