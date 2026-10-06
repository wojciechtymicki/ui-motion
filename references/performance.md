# Performance

Smooth motion is a budget, not a feeling. Measure with `perf_test.js` (web) and the native profilers
in `testing.md`.

## Frame budgets

| Display | Frame budget | Usable for your work (browser/OS overhead taken) |
|---|---|---|
| 60Hz | 16.7ms | ≈ 10ms |
| 90Hz | 11.1ms | ≈ 7ms |
| 120Hz (ProMotion, flagship Android, many laptops) | 8.3ms | ≈ 5ms |

A dropped frame during motion is visible as a hitch, especially on a constant-velocity move. Target
zero dropped frames on mid-range devices with 4× CPU throttling (web) or on a 3-year-old mid-range
Android (native).

## Variable refresh

- **ProMotion (iOS/macOS):** the system raises the rate during animation and touch. Core Animation and
  SwiftUI animations run at 120Hz automatically. Custom `CADisplayLink` needs
  `preferredFrameRateRange` plus the `CADisableMinimumFrameDurationOnPhone` Info.plist key.
- **Android adaptive refresh:** the rate may drop to 60 or lower when idle and rise on touch. Use
  `Choreographer` / the Compose frame clock, and never assume 16ms.
- **Web:** `requestAnimationFrame` fires at the display rate (60–240Hz). All motion must be
  time-based (`t` from timestamps), never per-frame increments. seek(t) code is rate-independent by
  construction.
- **Low Power Mode (iOS)** caps at 60Hz and may throttle. **Battery saver (Android)** can reduce the
  animator scale. Design must hold up at 60Hz.

## Layer and `will-change` hygiene (web)

- Only `transform` and `opacity` (and `filter` on small layers) run on the compositor. Everything else
  re-runs layout and/or paint each frame.
- `will-change: transform` promotes a layer, costing GPU memory of roughly width × height × 4 bytes ×
  DPR². A full-screen layer at DPR 3 on a 430×932pt phone ≈ 14 MB. Promote just before the animation,
  remove after. Never put `will-change` on dozens of list items permanently.
- Layer explosion: implicit promotion happens when something overlaps a composited layer. Check the
  layer count in DevTools → Layers. More than about 30 is a smell.
- Avoid animating: `box-shadow` (crossfade a shadow layer instead), `filter: blur()` with large radius
  on large layers, `backdrop-filter` on moving elements, `clip-path` on large complex content (paint),
  `border-radius` on large images (paint), and anything forcing layout (`width`, `height`, `top`,
  `left`, `font-size`, `margin`).
- **SVG:** a CSS `transform` on an SVG *child* (`<circle>`, `<path>`, `<g>`) forces Layout every
  frame in Chromium. Rotate or translate the `<svg>` element itself (or an HTML wrapper), and keep
  child animations to paint-only attributes (`stroke-dashoffset`, `stroke-dasharray`, `opacity`).
  Found in practice: a spinner rotating its `<circle>` caused layout on 76% of frames; rotating the
  `<svg>` box brought it to 0.
- **Sub-pixel text ticks:** text in a non-composited element snaps to whole pixels, so a slow
  spring tail (0.05–0.1px/frame) moves text in visible 1px ticks while its box glides. Promote
  moving text containers (`will-change: transform`) for the duration of the motion. Found in
  practice: chips settling after a lift ticked at 2.1s and 2.2s.
- Don't promote text that animates **inside an overflow mask** (masked word rises): its layer keeps
  the raster from the masked phase, and the final glyphs differ from a fresh render. Found in
  practice when an entrance's last frame stopped matching the idle loop's first frame. Promote only
  unmasked moving containers, and always diff end frames against the next state.
- Writing `textContent` (counters) re-runs layout, so write only when the string changes.
- Reading layout in an animation loop (`offsetWidth`, `getBoundingClientRect`) after writing styles
  forces synchronous layout (thrash). Read everything first, then write.

## Native

- **iOS:** offscreen rendering (shadows without `shadowPath`, `masksToBounds` + `cornerRadius` on
  many layers, group opacity) is the usual hitch source. Rasterize static complex subtrees
  (`shouldRasterize` with care, or `drawingGroup()` in SwiftUI). Keep the main thread free during
  animations: Core Animation runs on the render server, but layout and commits happen on main.
- **Android/Compose:** read animated values in the layout or draw phase (lambda modifiers), not in
  composition. Avoid allocations per frame. Use `Modifier.graphicsLayer` for transform and alpha.
  Baseline Profiles cut first-run jank.
- **React Native:** animations on the UI thread (Reanimated). JS-thread animations drop frames whenever
  JS is busy.

## Lottie and Rive complexity

- **Lottie:** cost scales with shape count × mask/matte area × layer count. Budgets for mobile: ≤ 30
  layers, no Gaussian blur, few mattes, merge paths off. Use the hardware or canvas renderer for heavy
  files on web, and SVG for crisp small ones. Test on a low-end Android device: it's the slowest
  renderer.
- **Rive:** cheap per frame (GPU renderer), but mesh deformations and many bones add up. Watch
  artboard count when several instances are on screen.

## Video decode cost

- Hardware decode handles H.264 and HEVC efficiently, and VP9 on most modern hardware. Alpha video
  doubles the decode work (two planes).
- Several simultaneous autoplaying videos on mobile Safari can stall. Play the visible one, pause the
  others (IntersectionObserver).
- Always set a `poster`. Use `preload="metadata"` for below-the-fold video. Use `playsinline muted`
  for iOS autoplay.
- Don't scale video in CSS to a very different size: encode at the display size × DPR.

## Low-power behaviour

Reduce or stop ambient loops when the battery saver is on, when the tab is hidden
(`visibilitychange` pauses rAF automatically, but videos and Lottie need explicit pause), and when
off-screen. Infinite loops in background tabs waste battery.
