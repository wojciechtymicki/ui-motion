/*
 * ui-motion review player.
 * Drives a same-origin iframe through iframe.contentWindow.__motion.seek(t).
 * Plain JS, no dependencies. Served by scripts/serve.py.
 *
 * Extension points (not built yet, keep these seams intact):
 *  - A/B version compare: loadAnim() takes a path; a second <iframe> can be
 *    driven by the same seek() in the "seek" event.
 *  - Comments stored in the player: hang them off copyText() output + "copy" event.
 *  - Pinning an element by clicking the stage: .stage.live enables pointer events
 *    on the iframe; read elementFromPoint inside the frame there.
 * Everything is reachable on window.__player.
 */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var el = {
    stageArea: $("stageArea"), stage: $("stage"), frame: $("frame"), stageError: $("stageError"),
    animName: $("animName"), animVersion: $("animVersion"), stageSize: $("stageSize"),
    picker: $("picker"), pickerWrap: $("pickerWrap"), reducedBtn: $("reducedBtn"),
    toast: $("toast"), toastLabel: $("toastLabel"), toastText: $("toastText"), toastInput: $("toastInput"),
    startBtn: $("startBtn"), playBtn: $("playBtn"), stopBtn: $("stopBtn"), loopBtn: $("loopBtn"),
    timeBtn: $("timeBtn"), timeText: $("timeText"), durText: $("durText"), fpsText: $("fpsText"),
    unitsGroup: $("unitsGroup"), speedGroup: $("speedGroup"),
    rangeBtn: $("rangeBtn"), rangeText: $("rangeText"), resetBtn: $("resetBtn"),
    track: $("track"), ruler: $("ruler"), dimBefore: $("dimBefore"), dimAfter: $("dimAfter"), ticks: $("ticks"),
    rangeLane: $("rangeLane"), rangeEmpty: $("rangeEmpty"), rangeBody: $("rangeBody"),
    inHandle: $("inHandle"), outHandle: $("outHandle"), playhead: $("playhead"), knob: $("knob")
  };

  var MIN_RANGE = 0.1; // seconds

  var S = { t: 0, playing: false, speed: 1, loop: true, range: null, units: "s", reduced: false };
  var meta = { name: "", version: 1, duration: 1, fps: 60, width: 800, height: 600 };
  var motion = null;       // iframe's window.__motion
  var animPath = null;     // project-relative path of the current animation
  var projects = [];
  var listeners = {};
  var lastCopied = null;
  var drag = null;
  var lastTick = null;
  var loadToken = 0;
  var version = null;
  var ticksKey = "";

  // ------------------------------------------------------------------ events

  function on(name, fn) { (listeners[name] = listeners[name] || []).push(fn); }
  function emit(name, data) { (listeners[name] || []).forEach(function (fn) { try { fn(data); } catch (e) { console.error(e); } }); }

  // ------------------------------------------------------------------ time math

  function dur() { return Math.max(0.01, meta.duration); }
  function fps() { return Math.max(1, meta.fps); }
  function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }
  /** The one frame rule used everywhere: 0-based, floor with epsilon. */
  function frameOf(t) { return Math.floor(t * fps() + 1e-6); }
  function totalFrames() { return Math.round(dur() * fps()); }
  /** Snap any time to the start of its frame. Scrubbing always lands on exact frames. */
  function snap(t) { return clamp(Math.min(frameOf(clamp(t, 0, dur())), totalFrames()) / fps(), 0, dur()); }
  function bounds() { return S.range ? { a: S.range.inT, b: S.range.outT } : { a: 0, b: dur() }; }

  function secStr(t) { return (Math.round(t * 100) / 100).toFixed(2); }
  function clock(t) {
    var cs = Math.round(t * 100);
    var m = Math.floor(cs / 6000), s = Math.floor(cs / 100) % 60, c = cs % 100;
    var p = function (n) { return String(n).padStart(2, "0"); };
    return p(m) + ":" + p(s) + "." + p(c);
  }
  function fmt(t) {
    if (S.units !== "f") return clock(t);
    var total = totalFrames();
    return String(Math.min(total, frameOf(t))).padStart(String(total).length, "0");
  }

  // ------------------------------------------------------------------ copy strings

  function timeValue() {
    var t = Math.min(S.t, dur());
    return S.units === "f" ? "frame " + frameOf(t) + " (" + fps() + "fps)" : secStr(t) + "s";
  }
  function rangeValue() {
    var r = S.range || { inT: 0, outT: dur() };   // default selection = the whole animation
    return S.units === "f"
      ? "frames " + frameOf(r.inT) + "–" + frameOf(r.outT) + " (" + fps() + "fps)"
      : secStr(r.inT) + "s–" + secStr(r.outT) + "s";
  }
  function prefix() { return meta.name + " v" + meta.version + " @ "; }
  function copyText(kind) {
    if (kind === "range") { var r = rangeValue(); return r ? prefix() + r : null; }
    return prefix() + timeValue();
  }

  var toastTimer = null;
  function showToast(label, text, manual) {
    clearTimeout(toastTimer);
    el.toastLabel.textContent = label;
    el.toast.hidden = false;
    el.toast.classList.toggle("manual", !!manual);
    el.toastText.hidden = !!manual;
    el.toastInput.hidden = !manual;
    if (manual) {
      el.toastInput.value = text;
      el.toastInput.style.width = Math.max(280, text.length * 8 + 16) + "px";
      el.toastInput.focus();
      el.toastInput.select();
    } else {
      el.toastText.textContent = text;
    }
    toastTimer = setTimeout(function () { el.toast.hidden = true; }, manual ? 6000 : 1600);
  }

  function copy(kind) {
    var text = copyText(kind);
    if (!text) return;
    var label = kind === "range" ? "Range copied" : "Time copied";
    lastCopied = text;
    emit("copy", { kind: kind, text: text });
    var done = function (ok) {
      if (ok) showToast(label, text, false);
      else showToast("Couldn’t copy. Select it:", text, true);
    };
    var fallback = function () {
      try {
        var ta = document.createElement("textarea");
        ta.value = text; ta.setAttribute("readonly", "");
        ta.style.position = "fixed"; ta.style.opacity = "0"; ta.style.left = "-9999px";
        document.body.appendChild(ta); ta.select();
        var ok = document.execCommand("copy");
        document.body.removeChild(ta);
        done(ok);
      } catch (e) { done(false); }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(function () { done(true); }, fallback);
    else fallback();
  }

  // ------------------------------------------------------------------ seek + render

  function seek(t) {
    S.t = clamp(t, 0, dur());
    if (motion) {
      try { motion.seek(S.t); }
      catch (e) { showError("seek(" + S.t.toFixed(3) + ") threw:\n" + (e && e.stack || e)); }
    }
    emit("seek", S.t);
    render();
  }

  function pct(v) { return (v / dur() * 100) + "%"; }

  function render() {
    var t = Math.min(S.t, dur());
    var frames = S.units === "f";
    el.timeText.textContent = fmt(t);
    el.durText.textContent = fmt(dur());
    el.fpsText.textContent = frames ? " f · " + fps() + " fps" : "";
    el.playhead.style.left = pct(t);

    el.playBtn.classList.toggle("playing", S.playing);
    el.playBtn.setAttribute("aria-label", S.playing ? "Pause" : "Play");
    el.loopBtn.setAttribute("aria-pressed", S.loop ? "true" : "false");
    el.reducedBtn.setAttribute("aria-pressed", S.reduced ? "true" : "false");
    el.startBtn.setAttribute("aria-label", S.range ? "Jump to range start" : "Jump to start");

    setPressed(el.unitsGroup, "units", S.units);
    setPressed(el.speedGroup, "speed", String(S.speed));

    // The selection always exists; by default it spans the whole animation (S.range === null).
    // A selection that has been dragged back to full length is the default again.
    if (S.range && S.range.inT <= 1e-6 && S.range.outT >= dur() - 1e-6) S.range = null;
    var r = S.range || { inT: 0, outT: dur() };
    el.rangeText.textContent = fmt(r.inT) + " – " + fmt(r.outT);
    el.rangeBtn.disabled = false;
    el.rangeBtn.title = "Click to copy the range";
    el.resetBtn.disabled = !S.range;               // active only when narrower than the animation
    el.rangeBody.hidden = false;
    el.rangeEmpty.hidden = true;
    el.rangeBody.classList.toggle("full", !S.range);
    el.rangeBody.style.left = pct(r.inT);
    el.rangeBody.style.width = pct(r.outT - r.inT);
    el.dimBefore.style.width = pct(r.inT);
    el.dimAfter.style.width = pct(dur() - r.outT);
    renderTicks();
    persist();
  }

  function setPressed(group, attr, value) {
    Array.prototype.forEach.call(group.querySelectorAll("button"), function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-" + attr) === value ? "true" : "false");
    });
  }

  // Adaptive ruler: ~4–8 labelled majors, minors between. Seconds or frame-based steps.
  function renderTicks() {
    var key = S.units + "|" + dur() + "|" + fps();
    if (key === ticksKey) return;
    ticksKey = key;
    var d = dur(), out = [], i, v;
    if (S.units === "f") {
      var total = totalFrames();
      var steps = [[1, 1], [2, 1], [5, 1], [10, 2], [20, 5], [50, 10], [100, 20], [200, 50], [500, 100], [1000, 200], [2000, 500]];
      var st = steps[steps.length - 1];
      for (i = 0; i < steps.length; i++) if (total / steps[i][0] <= 8) { st = steps[i]; break; }
      for (var f = 0; f <= total; f += st[1]) {
        var major = f % st[0] === 0;
        out.push('<div class="tick" style="left:' + pct(f / fps()) + ';height:' + (major ? 14 : 6) + 'px"></div>');
        if (major && f < total) out.push('<span class="tick-label" style="left:' + pct(f / fps()) + '">' + f + "</span>");
      }
    } else {
      var pairs = [[0.1, 0.02], [0.2, 0.05], [0.25, 0.05], [0.5, 0.1], [1, 0.25], [2, 0.5], [5, 1], [10, 2], [15, 5], [30, 5], [60, 10], [120, 30]];
      var p = pairs[pairs.length - 1];
      for (i = 0; i < pairs.length; i++) if (d / pairs[i][0] <= 8) { p = pairs[i]; break; }
      var n = Math.round(d / p[1]);
      for (i = 0; i <= n; i++) {
        v = i * p[1];
        if (v > d + 1e-6) break;
        var isMajor = Math.abs(v / p[0] - Math.round(v / p[0])) < 1e-6;
        out.push('<div class="tick" style="left:' + pct(v) + ';height:' + (isMajor ? 14 : 6) + 'px"></div>');
        if (isMajor && v < d - 1e-6) {
          var label = p[0] < 1 ? (Math.round(v * 100) / 100) + "s" : Math.round(v) + "s";
          out.push('<span class="tick-label" style="left:' + pct(v) + '">' + label + "</span>");
        }
      }
    }
    el.ticks.innerHTML = out.join("");
  }

  // ------------------------------------------------------------------ playback

  function tick(now) {
    if (S.playing && !drag && motion) {
      var dt = lastTick == null ? 0 : (now - lastTick) / 1000;
      var b = bounds();
      var t = S.t + dt * S.speed;
      if (t < b.a) t = b.a;
      if (t >= b.b) {
        if (S.loop) t = b.a + ((t - b.a) % Math.max(1e-6, b.b - b.a));
        else { S.playing = false; t = b.b; }
      }
      lastTick = now;
      seek(t);
    } else {
      lastTick = null;
    }
    requestAnimationFrame(tick);
  }

  function play() {
    var b = bounds();
    var t = S.t;
    if (t >= b.b - 0.001 || t < b.a) t = b.a;
    S.playing = true;
    lastTick = null;
    seek(t);
  }
  function pause() { S.playing = false; render(); }
  function togglePlay() { if (S.playing) pause(); else play(); }
  function stop() { S.playing = false; seek(bounds().a); }
  function toStart() { seek(bounds().a); }
  function step(frames) { S.playing = false; seek(clamp((frameOf(S.t) + frames) / fps(), 0, dur())); }
  function stepSeconds(sec) { S.playing = false; seek(snap(S.t + sec)); }

  function setRange(inT, outT) {
    if (inT == null) { S.range = null; render(); return; }
    var a = snap(Math.min(inT, outT)), b = snap(Math.max(inT, outT));
    if (b - a < MIN_RANGE - 1e-9) return;
    S.range = { inT: a, outT: b };
    render();
  }
  function resetRange() { S.range = null; render(); }
  function setIn() {
    var t = snap(S.t);
    if (S.range) { if (S.range.outT - t >= MIN_RANGE) S.range = { inT: t, outT: S.range.outT }; }
    else if (dur() - t >= MIN_RANGE) S.range = { inT: t, outT: dur() };
    render();
  }
  function setOut() {
    var t = snap(S.t);
    if (S.range) { if (t - S.range.inT >= MIN_RANGE) S.range = { inT: S.range.inT, outT: t }; }
    else if (t >= MIN_RANGE) S.range = { inT: 0, outT: t };
    render();
  }

  // ------------------------------------------------------------------ pointer

  function beginDrag(mode, e, opts) {
    opts = opts || {};
    e.preventDefault();
    var rect = el.ruler.getBoundingClientRect();
    var toT = function (x) { return clamp((x - rect.left) / rect.width, 0, 1) * dur(); };
    var r = S.range || { inT: 0, outT: dur() };
    drag = { mode: mode, toT: toT, startT: snap(toT(e.clientX)), in0: r.inT, out0: r.outT, x0: e.clientX, moved: false, knob: !!opts.knob };
    if (mode === "scrub" && !opts.knob) applyDrag(e.clientX);
    if (mode === "move") el.rangeBody.classList.add("dragging");
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
  }

  function applyDrag(x) {
    var g = drag; if (!g) return;
    var d = dur(), cur = snap(g.toT(x));
    if (g.mode === "scrub") { seek(cur); return; }
    if (g.mode === "in") S.range = { inT: Math.min(cur, snap(g.out0 - MIN_RANGE)), outT: g.out0 };
    else if (g.mode === "out") S.range = { inT: g.in0, outT: Math.max(cur, Math.min(d, g.in0 + MIN_RANGE)) };
    else if (g.mode === "move") {
      var len = g.out0 - g.in0;
      var ni = snap(clamp(g.in0 + (cur - g.startT), 0, d - len));
      S.range = { inT: ni, outT: Math.min(d, ni + len) };
    } else if (g.mode === "new") {
      var a = g.startT;
      if (Math.abs(cur - a) >= MIN_RANGE) S.range = { inT: Math.min(a, cur), outT: Math.max(a, cur) };
    }
    render();
  }

  function onMove(e) {
    if (!drag) return;
    if (Math.abs(e.clientX - drag.x0) > 3) drag.moved = true;
    if (drag.moved || (drag.mode === "scrub" && !drag.knob)) applyDrag(e.clientX);
  }

  function onUp() {
    var g = drag;
    drag = null;
    el.rangeBody.classList.remove("dragging");
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", onUp);
    window.removeEventListener("pointercancel", onUp);
    if (!g) return;
    if (!g.moved && g.knob) copy("time");
    if (!g.moved && g.mode === "move") copy("range");
    if (g.mode !== "scrub" && S.range && (S.t < S.range.inT || S.t > S.range.outT)) seek(S.range.inT);
    render();
  }

  el.ruler.addEventListener("pointerdown", function (e) { if (e.button === 0) beginDrag("scrub", e); });
  el.knob.addEventListener("pointerdown", function (e) { if (e.button === 0) beginDrag("scrub", e, { knob: true }); });
  el.rangeLane.addEventListener("pointerdown", function (e) { if (e.button === 0) beginDrag("new", e); });
  el.rangeBody.addEventListener("pointerdown", function (e) { if (e.button !== 0) return; e.stopPropagation(); beginDrag("move", e); });
  el.inHandle.addEventListener("pointerdown", function (e) { if (e.button !== 0) return; e.stopPropagation(); beginDrag("in", e); });
  el.outHandle.addEventListener("pointerdown", function (e) { if (e.button !== 0) return; e.stopPropagation(); beginDrag("out", e); });
  // Keyboard activation of the knob (Enter) copies the time.
  el.knob.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); copy("time"); } });

  // ------------------------------------------------------------------ buttons

  el.playBtn.addEventListener("click", togglePlay);
  el.startBtn.addEventListener("click", toStart);
  el.stopBtn.addEventListener("click", stop);
  el.loopBtn.addEventListener("click", function () { S.loop = !S.loop; render(); });
  el.timeBtn.addEventListener("click", function () { copy("time"); });
  el.rangeBtn.addEventListener("click", function () { copy("range"); });
  el.resetBtn.addEventListener("click", resetRange);
  el.unitsGroup.addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    S.units = b.getAttribute("data-units"); render();
  });
  el.speedGroup.addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    S.speed = +b.getAttribute("data-speed"); render();
  });
  el.reducedBtn.addEventListener("click", function () { S.reduced = !S.reduced; persist(); loadAnim(animPath); });
  el.picker.addEventListener("change", function () {
    if (el.picker.value === animPath) return;     // re-selecting the current animation keeps its state
    S.playing = false;
    loadAnim(el.picker.value, { fresh: true });
  });

  // ------------------------------------------------------------------ keyboard

  document.addEventListener("keydown", function (e) {
    var tag = e.target && e.target.tagName;
    if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    var k = e.key, handled = true;
    if (k === " " || e.code === "Space") togglePlay();
    else if (k === "ArrowLeft") e.shiftKey ? stepSeconds(-1) : step(-1);
    else if (k === "ArrowRight") e.shiftKey ? stepSeconds(1) : step(1);
    else if (k === "Home") { S.playing = false; seek(bounds().a); }
    else if (k === "End") { S.playing = false; seek(bounds().b); }
    else if (k === "l" || k === "L") { S.loop = !S.loop; render(); }
    else if (k === "r" || k === "R") resetRange();
    else if (k === "c" || k === "C") copy(S.range ? "range" : "time");
    else if (k === "i" || k === "I") setIn();
    else if (k === "o" || k === "O") setOut();
    else handled = false;
    if (handled) e.preventDefault();
  });
  // Space must not also "click" a focused button on keyup.
  document.addEventListener("keyup", function (e) {
    if ((e.key === " " || e.code === "Space") && e.target && e.target.tagName === "BUTTON") e.preventDefault();
  });

  // ------------------------------------------------------------------ persistence

  function storeKey() { return "ui-motion-player:" + (animPath || ""); }
  function persist() {
    if (!animPath) return;
    try {
      sessionStorage.setItem(storeKey(), JSON.stringify({ t: S.t, range: S.range, speed: S.speed, loop: S.loop, units: S.units, reduced: S.reduced, playing: S.playing }));
      sessionStorage.setItem("ui-motion-player:last", animPath);
    } catch (e) { /* storage blocked: state just won't survive a full reload */ }
  }
  function restore(path) {
    try { return JSON.parse(sessionStorage.getItem("ui-motion-player:" + path) || "null"); }
    catch (e) { return null; }
  }

  // ------------------------------------------------------------------ loading

  function showError(msg) {
    el.stageError.textContent = msg;
    el.stageError.hidden = false;
  }

  function layout() {
    var w = meta.width, h = meta.height;
    var cs = getComputedStyle(el.stageArea);
    var availW = el.stageArea.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    var availH = el.stageArea.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom) - 40;
    var fit = Math.min(availW / w, availH / h);
    var maxScale = (w <= 360 && h <= 360) ? 2 : 1; // small pieces (icons, buttons) get room to be seen
    var scale = Math.max(0.1, Math.min(maxScale, fit));
    el.stage.style.width = Math.round(w * scale) + "px";
    el.stage.style.height = Math.round(h * scale) + "px";
    el.frame.style.width = w + "px";
    el.frame.style.height = h + "px";
    el.frame.style.transform = "scale(" + scale + ")";
    el.stageSize.textContent = w + " × " + h + (Math.abs(scale - 1) > 0.005 ? " · " + Math.round(scale * 100) + "%" : "");
  }
  window.addEventListener("resize", layout);

  function waitForMotion(win, timeoutMs) {
    return new Promise(function (resolve, reject) {
      var t0 = performance.now();
      (function poll() {
        var m = null;
        try { m = win.__motion; } catch (e) { return reject(new Error("Animation is not same-origin")); }
        if (m) return resolve(m);
        if (performance.now() - t0 > timeoutMs) return reject(new Error("No Motion.register() found within " + timeoutMs + "ms.\nDoes the page include motion-runtime.js and call Motion.register({...})?"));
        setTimeout(poll, 30);
      })();
    });
  }

  /**
   * Load (or reload) an animation into the iframe.
   * opts.fresh: ignore stored state (switching animations from the picker).
   * Without fresh, the playhead, range, speed and units carry over.
   */
  function loadAnim(path, opts) {
    opts = opts || {};
    if (!path) return Promise.resolve();
    var token = ++loadToken;
    var keep = opts.fresh ? (restore(path) || {}) : { t: S.t, range: S.range, speed: S.speed, loop: S.loop, units: S.units, reduced: S.reduced, playing: S.playing };
    if (opts.fresh) persist();
    animPath = path;
    el.stageError.hidden = true;
    if (el.picker.value !== path) el.picker.value = path;
    var url = new URL(location.href);
    url.searchParams.set("a", path);
    history.replaceState(null, "", url);

    return new Promise(function (resolve) {
      el.frame.onload = function () {
        if (token !== loadToken) return;
        waitForMotion(el.frame.contentWindow, 5000).then(function (m) {
          return Promise.resolve(m.ready).then(function () { return m; });
        }).then(function (m) {
          if (token !== loadToken) return;
          motion = m;
          meta = { name: m.name, version: m.version, duration: m.duration, fps: m.fps, width: m.width, height: m.height };
          el.animName.textContent = m.name;
          el.animVersion.textContent = "v" + m.version;
          document.title = m.name + " v" + m.version + " · Motion review";
          if (m.errors && m.errors.length) showError(m.errors.join("\n\n"));
          S.speed = keep.speed || S.speed;
          S.loop = keep.loop != null ? keep.loop : S.loop;
          S.units = keep.units || S.units;
          S.reduced = !!keep.reduced;
          S.range = keep.range && keep.range.outT <= m.duration + 1e-9 ? keep.range : (keep.range ? { inT: Math.min(keep.range.inT, Math.max(0, m.duration - MIN_RANGE)), outT: m.duration } : null);
          if (S.range && S.range.outT - S.range.inT < MIN_RANGE - 1e-9) S.range = null;
          S.playing = !!keep.playing && !opts.fresh;
          ticksKey = "";
          layout();
          seek(keep.t != null ? Math.min(keep.t, m.duration) : 0);
          emit("load", { path: path, meta: meta });
          resolve();
        }).catch(function (err) {
          if (token !== loadToken) return;
          motion = null;
          showError(String(err && err.message || err));
          resolve();
        });
      };
      var reduced = (opts.fresh ? keep.reduced : S.reduced) ? "&reduced=1" : "";
      el.frame.src = "/" + path.split("/").map(encodeURIComponent).join("/") + "?embed=1" + reduced + "&_=" + Date.now();
    });
  }

  function loadProjects() {
    return fetch("/__projects", { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (data) {
      projects = data.animations || [];
      var prev = el.picker.value;
      el.picker.innerHTML = projects.map(function (p) {
        return '<option value="' + p.path.replace(/"/g, "&quot;") + '">' + p.label.replace(/</g, "&lt;") + "</option>";
      }).join("");
      el.pickerWrap.hidden = projects.length < 2;
      if (prev) el.picker.value = prev;
      return projects;
    });
  }

  // Auto-reload: poll serve.py for a hash of the project files' mtimes.
  function pollVersion() {
    fetch("/__version", { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (data) {
      if (version != null && data.version !== version) {
        loadProjects().then(function () {
          var still = projects.some(function (p) { return p.path === animPath; });
          loadAnim(still ? animPath : (projects[0] && projects[0].path), { fresh: !still });
        });
      }
      version = data.version;
    }).catch(function () { /* server restarting; keep polling */ })
      .then(function () { setTimeout(pollVersion, 1000); });
  }

  // ------------------------------------------------------------------ boot

  window.__player = {
    get state() { return JSON.parse(JSON.stringify(S)); },
    get meta() { return Object.assign({}, meta); },
    get lastCopied() { return lastCopied; },
    seek: function (t) { seek(t); }, play: play, pause: pause, stop: stop, step: step,
    setRange: setRange, resetRange: resetRange, copy: copy, copyText: copyText,
    frameOf: frameOf, load: loadAnim, on: on
  };

  loadProjects().then(function (list) {
    if (!list.length) { showError("No animations found.\nAn animation is an .html file that calls Motion.register({...})."); return; }
    var q = new URL(location.href).searchParams.get("a");
    var last = null;
    try { last = sessionStorage.getItem("ui-motion-player:last"); } catch (e) {}
    var pick = [q, last].filter(function (p) { return p && list.some(function (x) { return x.path === p; }); })[0] || list[0].path;
    el.picker.value = pick;
    return loadAnim(pick, { fresh: true });
  }).catch(function (err) {
    showError("Could not reach serve.py: " + err);
  }).then(function () {
    pollVersion();
  });

  render();
  requestAnimationFrame(tick);
})();
