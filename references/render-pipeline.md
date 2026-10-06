# Render pipeline

How seek(t) pages become frames, contact sheets and deliverables. Implemented in
`scripts/_capture.py` and `scripts/render.py`. Read this when rendering, when a render doesn't match
the player, or when adding a seek adapter.

## The seek(t) engine

`motion-runtime.js` exposes `window.__motion`:

```
name, version, duration, fps, width, height, loops, reduced, frames
holds           declared intentional stills [[a, b], …], which jank_check accepts (justify them in the spec)
def.perf        optional { maxLayoutPerFrame, reason }: declared layout allowance for perf_test
                (e.g. counters that change text). Printed in the report
seek(t)         sets every element for time t (pure, clamped to [0, duration])
seekFrame(n)    seek(n / fps)
frameOf(t)      floor(t * fps + 1e-6), the one frame rule, 0-based
ready           Promise: fonts loaded + the page's own `ready`
errors          exceptions thrown inside seek
```

The player, `render.py`, `contact_sheet.py`, `jank_check.py`, `loop_check.py` and `perf_test.js` all
call the same `seek`. A frame number copied from the player renders identically in every tool.

Projects carry a copy of `motion-runtime.js`. Capture scripts warn when it's older than the
template (`Motion.runtimeVersion`). Update it with `python scripts/new_project.py --refresh <project>`.

**Page contract:** no CSS transitions or animations on elements that `seek` controls (they'd
interpolate between seeks); no `Date.now`, `performance.now`, `setTimeout` or `Math.random` in visual
logic; all layout measurement done once before the first seek (or memoised); `#stage` is the capture
region.

## Capture procedure (per frame)

1. Load with `?embed=1&render=1` (plus `&reduced=1` for the reduced version). This gives an
   embedded layout with a transparent page background.
2. Await `__motion.ready` and `document.fonts.ready`. Wait for every `<img>` to finish loading.
3. **Pause all CSS and WAAPI animations:** `document.getAnimations().forEach(a => a.pause())`, so only
   seek decides the frame.
4. For each frame: `__motion.seek(t)`, then **wait two `requestAnimationFrame`s**. The first lets
   style and layout commit; the second guarantees the frame was painted before the screenshot.
5. Screenshot `#stage` with `animations: "disabled"`, `caret: "hide"`, and `omit_background` for alpha.

## Deterministic Chromium flags

```
--deterministic-mode                       # stable timing and scheduling
--run-all-compositor-stages-before-draw    # every compositor stage completes before a frame is drawn
--disable-threaded-animation               # no compositor-thread animations racing seek
--disable-threaded-scrolling
--disable-checker-imaging                  # images are decoded before draw, never checkerboarded
--font-render-hinting=none                 # identical glyph rasterization across machines
--force-color-profile=srgb                 # no display-profile colour shifts
--hide-scrollbars
```

Verified: two renders of the same range produce byte-identical PNGs (`tests/test_analysis.py`).

## Supersampling (2× by default for video)

Text and thin strokes alias at 1×, and video compression amplifies that. `render.py` captures at
`device_scale_factor = scale × 2` and downsamples with Lanczos to the output size. Use `--supersample 1`
for fast previews and PNG sequences meant for further compositing.

## Adaptive subframe motion blur

Real cameras integrate over the shutter, and fast UI motion at 60fps can strobe. `--motion-blur N`:

- For each output frame, compare t with t + shutter/fps (180° shutter = 0.5 frame by default).
- **Hard cut inside the shutter** (> 35% of pixels change significantly): don't blur, use the
  sharp frame. Blur must never mix two different shots.
- Otherwise the subframe count is proportional to the motion (mean difference), capped at N. Static
  frames get 1 sample (stay perfectly sharp), and fast frames get up to N, averaged.

Use blur for rendered explainers and marketing at 30fps or for very fast moves. Never use it on
review renders, which must show exact frames.

## Seek adapters for other engines

| Engine | Adapter inside `Motion.register({ seek })` |
|---|---|
| GSAP | `tl.pause(); seek: t => tl.totalTime(t)` (`totalTime` includes repeats/delays) |
| WAAPI / CSS animations | `const anims = el.getAnimations({ subtree: true }); anims.forEach(a => a.pause()); seek: t => anims.forEach(a => a.currentTime = t * 1000)` |
| Motion (motion.dev) | `const c = animate(...); c.pause(); seek: t => (c.time = t)` |
| Lottie-web | `seek: t => anim.goToAndStop(t * 1000, false)` (svg renderer) |
| Rive | `seek: t => rive.scrub("Timeline", t)`; state machines: reset, then advance in 1/fps steps |
| Three.js / canvas | render the scene from t: `seek: t => { update(t); renderer.render(scene, cam) }` with `preserveDrawingBuffer: true` |
| Video element | `seek: t => new Promise(r => { v.currentTime = t; v.onseeked = r })` (make `seek` async-aware via `ready`) |

## Export settings

| Format | Settings (`render.py`) |
|---|---|
| MP4 | H.264 `libx264 -preset slow -crf 16`, **yuv420p**, **BT.709 TV range** (`scale=out_color_matrix=bt709:out_range=tv` + `setparams` primaries/trc/matrix), `-movflags +faststart` (moov atom first, so playback starts before download finishes), even dimensions (padded) |
| WebM alpha | VP9 `-pix_fmt yuva420p -crf 24 -b:v 0 -auto-alt-ref 0` (alt-ref breaks alpha) |
| HEVC alpha | `hevc_videotoolbox -alpha_quality 0.75 -tag:v hvc1` in .mov (macOS only) |
| ProRes 4444 | `prores_ks -profile:v 4444 -pix_fmt yuva444p10le` |
| GIF | two-pass palette (`palettegen=stats_mode=diff`, `paletteuse=dither=sierra2_4a:diff_mode=rectangle`), 25fps default (GIF delays are in 10ms steps) |
| APNG | `-plays 0`, RGBA |
| PNG sequence | `frame_00000.png…`, RGBA with `--alpha` |

Frame range: non-looping pieces render frames 0…N (the resting final state is included). Loops render
0…N−1, because frame N equals frame 0 and repeating it would stutter at the seam.

## Poster

Every render writes `<name>-v<version>-poster.png`: the final frame for non-loops, frame 0 for loops
(override with `--poster t`). **Design frame 0 to work as a poster** for anything delivered as video:
many players, social platforms and store listings show the first frame before playback. If the
animation starts from empty, choose a poster time explicitly and set it as the `<video poster>`.

## When a render doesn't match the player

1. Same version? The player shows `vN`. `render.py` names files with `-vN`.
2. Fonts: a font that loads late in the player but not in capture (or the reverse). Make `ready`
   await it explicitly.
3. CSS transitions on seeked elements: they interpolate in the player but not in capture. Remove them.
4. Viewport-dependent layout: capture uses exactly width × height. The player scales the iframe with a
   transform (layout unchanged). Media queries inside the page should key off the stage, not the
   window.
