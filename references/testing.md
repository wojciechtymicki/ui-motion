# Testing

Scale testing to what ships. A rendered asset needs frame checks. Runtime code needs the browser,
device, mode and interaction matrices. Produce a **pass / fail / waived report** (format at the end).

## Always (every piece)

- `jank_check.py <project>`: no pops, off-path frames, flashes, or stalls. Also run with `--reduced`.
- `loop_check.py <project>` if it loops.
- **Spec match:** for 3–5 rows of the timing table, render the frame at the row's start and end
  (`contact_sheet.py --times`) and confirm the property values (inspect via
  `page.evaluate(() => getComputedStyle(el).transform)` or by eye on the sheet).
- No page errors (`render.py` and `contact_sheet.py` report `page_errors`).

## Browser matrix (runtime web code)

| Browser | Engine | Must check |
|---|---|---|
| Chrome / Edge (latest) | Blink | baseline; View Transitions, scroll-driven animations |
| Safari (latest, iOS + macOS) | WebKit | `backdrop-filter` cost, View Transitions (18+), no scroll-driven animations (pre-26), HEVC alpha video |
| Firefox (latest) | Gecko | no View Transitions cross-document; VP9 alpha |
| Safari iOS one major back | WebKit | users lag on iOS updates |

**Feature-detect, never UA-sniff.** Every fallback is designed (and in the spec):

```js
if (!document.startViewTransition) { /* plain crossfade */ }
CSS.supports("animation-timeline: view()")       // scroll-driven: else IntersectionObserver entrance
CSS.supports("transition-timing-function: linear(0, 1)")   // spring linear(): else cubic-bezier approximation
```

Playwright can run all three engines: `npx playwright install webkit firefox`, then
`device_matrix.js --browsers chromium,webkit,firefox`.

## Device matrix

| Axis | Values |
|---|---|
| Viewports | 360×800 (small Android), 390×844 (iPhone), 430×932 (Pro Max), 768×1024 (tablet), 1280×800, 1440×900, 1920×1080 |
| DPR | 1, 2, 3: text crispness at rest, hairline strokes, sub-pixel snapping at the end frame |
| Refresh | 60 Hz and 120 Hz: time-based motion is identical; no per-frame logic; no 60 Hz–tuned hacks |
| Safe areas / notches | `env(safe-area-inset-*)` respected at every frame (sheets don't slide under the home indicator) |
| Foldables | 2 postures (folded ~ 360 wide, unfolded ~ 700–840 wide); hinge-aware layout doesn't animate across the hinge |
| Orientation | portrait ↔ landscape mid-animation: no stuck transforms; re-measure after resize |

`device_matrix.js` captures the stage at a chosen time across viewports × DPR × modes into a grid.

## Mode matrix

| Mode | Check |
|---|---|
| Reduced motion | designed alternative renders; no travel or zoom; state readable (`--reduced`, player toggle) |
| Dark mode | colours in motion (scrims, shadows, glows) work on dark; no white flash frames |
| RTL | direction-aware motion mirrors (push from left, stagger right → left); icons that imply direction flip |
| Low power | iOS Low Power Mode at 60 Hz; Android battery saver (animator scale 0.5 / 0); ambient loops stop |
| Hover vs touch | `(hover: hover)` gating works; no sticky hover after tap; touch gets press feedback |
| Zoom / large text | 200% browser zoom and Dynamic Type XXL: masked text rises still clip correctly, no overlaps |

## Performance traces

- **Web:** `perf_test.js <url> --cpu 4` plays the animation in real time under 4× CPU throttling (and
  1×), records a Chrome trace, and reports frame-time percentiles, dropped frames, long tasks
  (> 50ms), and Layout / Paint event counts and cost during motion. Pass: **0 dropped frames and
  p95 ≤ 1.1 × vsync at 4×** (8.3ms vsync target for 120 Hz on 1×), 0 long tasks during motion, and
  **layout ≤ 0.5ms per frame** (layout events from text changes like counters are fine; layout from
  animated geometry is not, and shows as cost).
- `lint_motion.js` before tracing: catches layout-property animation, timers, and missing
  reduced-motion handling statically.

## Interaction stress tests (runtime code)

| Test | Expected |
|---|---|
| Rapid re-trigger (tap 5× in 500ms) | retargets from current value each time; no queue; no stuck state |
| Interrupt mid-animation (open → close at 40%) | reverses from the current position with continuous velocity |
| Reverse gesture (drag down, then back up before release) | follows 1:1; release velocity picks the right detent |
| Keyboard only (Tab, Enter, Space, Esc) | every state reachable; focus visible and correctly placed after transitions |
| Release outside / pointer cancel | press state clears; no action fired |
| Background → foreground mid-animation | lands in the correct end state; no half-finished transforms |
| Resize / rotate mid-animation | re-measured; no stale FLIP transforms |

Script these with Playwright (web) or XCUITest / Espresso / Compose UI tests (native), and assert
final computed transforms and state.

## Native profiling checklists

**iOS (Instruments)**
- [ ] *Animation Hitches* template: hitch ratio < 5 ms/s during the animation on the oldest supported device
- [ ] *Core Animation* / *Time Profiler*: main thread free during transitions (no layout or decoding)
- [ ] Debug → Color Offscreen-Rendered: no yellow on animated layers (add `shadowPath`, avoid masks)
- [ ] ProMotion device: animation runs at 120 Hz (`CADisableMinimumFrameDurationOnPhone` for custom display links)
- [ ] Reduce Motion on: alternative path verified

**Android**
- [ ] Macrobenchmark `FrameTimingMetric`: `frameOverrunMs` p95 < 0 (no overruns) on a mid-range device
- [ ] Perfetto trace: no long `Choreographer#doFrame`; no recomposition in animation frames (Layout Inspector recomposition counts)
- [ ] Developer options → Profile GPU rendering (bars under the green line)
- [ ] `adb shell settings put global animator_duration_scale 0`: end states correct with animations removed
- [ ] 90/120 Hz device: no assumptions of 16 ms

**Lottie / Rive on device**
- [ ] Low-end Android: steady frame rate with the animation on screen alongside real content
- [ ] Memory: no growth across 50 plays (leak check)

## Report format

Save as `out/test-report.md` and include it in handoff:

```
# Test report: onboarding-2 v4                      2026-10-05
Track: runtime (web, Motion)  ·  Spec: motion-spec.md v4

| Check                         | Result  | Evidence / note                               |
|-------------------------------|---------|-----------------------------------------------|
| jank_check (full)             | PASS    | 0 issues, motion 0.02→1.84s                   |
| jank_check (reduced)          | PASS    | 1 hold (expected), 0 issues                   |
| loop_check                    | n/a     | not a loop                                    |
| Spec match (5 rows)           | PASS    | out/sheet-onboarding-2-v4-spec.png            |
| perf_test 4× CPU              | PASS    | p95 11.2 ms, 0 long tasks, 0 layout/frame     |
| lint_motion                   | PASS    |                                               |
| Browsers: Chrome/Safari/FF    | PASS    | device_matrix grid out/matrix-v4.png          |
| DPR 1/2/3                     | PASS    |                                               |
| Dark / RTL                    | PASS / WAIVED | RTL: product ships LTR only (brief)     |
| Rapid re-trigger / interrupt  | PASS    | playwright: tests/interaction.spec            |
| Keyboard only                 | PASS    |                                               |
| Native profiling              | WAIVED  | web-only deliverable                          |
```

Every WAIVED needs a reason. FAILs block handoff unless the user accepts them explicitly.
