# Techniques

19 recipes. Each has: **when**, **parameters** (starting values), **failures** (what goes wrong),
and **implementations**. "seek" is the `motion-runtime.js` version used for review and rendering. It is
always written first, and the shipped versions must reproduce it. Curve and spring names refer to
`curves.md`.

Conventions in code: `T` is a table of start times, `tween(t, start, dur, from, to, ease)`,
`springTo(t, start, from, to, spring)`, and `stagger(i, step, cap)`.

---

## 1. Masked text rise and per-word stagger

**When:** headlines and short phrases arriving (onboarding, hero, success). Not for body copy, which
fades or renders in place.

**Parameters:** split by word (by line for > 8 words). Each word sits in an `overflow:hidden` wrapper
and its inner span translates from 105–115% to 0. Stagger 35–60ms per word, total ≤ 400ms. Spring
k 380 / c 36 (ζ 0.92), or `out` over 500–650ms. Add 4px of padding-bottom with a matching negative
margin on the mask so descenders don't clip.

**Failures:** line breaks change mid-animation (always split after fonts load and lock the layout first);
descenders clipped; masks on letters (too busy above 3 words); opacity added on top (unnecessary: the
mask already hides it); scaling the text (never).

**seek:**
```js
words.forEach((w, i) => {
  const p = sWord(t - T.title - stagger(i, 0.045, 0.3));
  w.style.transform = `translateY(${mix(110, 0, p)}%)`;
});
```
**CSS/WAAPI:**
```js
words.forEach((w, i) => w.animate(
  [{ transform: "translateY(110%)" }, { transform: "translateY(0)" }],
  { duration: 560, delay: i * 45, easing: "cubic-bezier(0.16,1,0.3,1)", fill: "backwards" }));
```
**Motion (React):**
```jsx
<motion.span initial={{ y: "110%" }} animate={{ y: 0 }}
  transition={{ type: "spring", stiffness: 380, damping: 36, delay: i * 0.045 }} />
```
**SwiftUI:** split into `Text` views in an `HStack`. Each is `.offset(y: shown ? 0 : h)` with
`.clipped()` on a container sized to the line, and
`.animation(.spring(response: 0.32, dampingFraction: 0.92).delay(Double(i) * 0.045), value: shown)`.
**Compose:** per word, `val y by animateFloatAsState(if (shown) 0f else 1f, spring(0.92f, 380f))`, with
`Modifier.clipToBounds()` on the line `Row` and `graphicsLayer { translationY = y * size.height }`.

---

## 2. Variable-font axis animation

**When:** typographic emphasis without swapping fonts: weight on press or selection, width for
headline drama, optical size for scale changes, a "breathing" wordmark.

**Parameters:** animate `font-variation-settings` (or `font-weight` with variable fonts) over
150–400ms. Weight ranges 400 → 600 for state changes, up to 100 → 900 for hero typography. Pair with
letter-spacing compensation (−0.01em per +100 weight) so line width doesn't jump.

**Failures:** reflow. Weight and width change advance widths, so neighbouring text moves. Fix the
container width, use `font-variant-numeric: tabular-nums` for numbers, or animate only isolated words.
It triggers text layout every frame on the web, so keep it to short strings. A non-variable fallback
font snaps between weights.

**seek:** `el.style.fontVariationSettings = \`"wght" ${mix(400, 640, p)}\``.
**CSS:** `transition: font-variation-settings 200ms cubic-bezier(0.2,0,0,1)` (live only. Review via seek).
**SwiftUI:** `.fontWeight` isn't animatable continuously. Use `Font.custom(name, size:)` with
`.fontVariations` via `UIFont` descriptors, or animate a `@State var weight: CGFloat` that rebuilds the
font in a custom `Animatable` view.
**Compose:** `FontVariation.Settings(FontVariation.weight(w.toInt()))` with `w` from
`animateFloatAsState` (API 26+).
**Lottie:** not supported. Use Rive text runs, or bake to paths.

---

## 3. Shared-element morph

**When:** an object persists across states: thumbnail → detail, card → full screen, FAB → sheet, chip →
filter panel, search field → search screen.

**Parameters:** interpolate the frame (x, y, w, h) and corner radius together. Use the `smooth` or `page`
spring, or `emphasized` over 400–500ms. Content inside crossfades: old content fades out in the first
35%, new content fades in from 35–100%. The container never fades.

**Failures:** stretching content (scale the container, counter-scale the children, or crossfade content
at a fixed size); radius jumping at the end; z-order popping (the morphing element must sit above both
layouts for the whole transition); the destination layout not ready (measure first, then animate).

**seek (FLIP):**
```js
const from = thumbRect, to = heroRect;              // measured once
const p = sMorph(t - T.morph);
const x = mix(from.x, to.x, p), y = mix(from.y, to.y, p);
const w = mix(from.w, to.w, p), h = mix(from.h, to.h, p);
box.style.transform = `translate(${x}px, ${y}px)`;
box.style.width = w + "px"; box.style.height = h + "px";   // lint-motion-ignore: one small element; else scale + counter-scale
box.style.borderRadius = mix(12, 0, p) + "px";
```
**Web (live):** the View Transitions API, with `view-transition-name: hero` on both elements and
`::view-transition-group(hero) { animation-timing-function: cubic-bezier(0.3,0,0,1); animation-duration: 450ms }`.
Motion: `<motion.div layoutId="hero" transition={{ type: "spring", stiffness: 220, damping: 30 }}>`.
**SwiftUI:** `.matchedGeometryEffect(id: "hero", in: ns)` on both views, inside
`withAnimation(.spring(response: 0.42, dampingFraction: 1))`. On iOS 18+,
`.navigationTransition(.zoom(sourceID:in:))` for push transitions.
**Compose:** `SharedTransitionLayout { … Modifier.sharedElement(rememberSharedContentState("hero"), animatedVisibilityScope, boundsTransform = { _, _ -> spring(1f, 220f) }) }`.

---

## 4. Label morph inside a shape

**When:** a button or pill changes its label ("Add" → "Added", "Follow" → "Following", "Pay" → spinner →
✓). The shape stays and the content changes.

**Parameters:** the old label exits up 6–10px plus fades over 120ms (`in`). The new label enters from
+6–10px below over 220ms (`out`), starting at 60% of the exit. If widths differ, animate the
container width with `snappy`, measured from the new label, so it starts with the exit. The loading
state keeps the button's width (principle: no layout jumps).

**Failures:** container width snaps, then the label animates (animate width first or simultaneously);
both labels visible at full opacity at once; text scaling; reflow of surrounding layout (reserve the max
width, or let the container own its width).

**seek:**
```js
const out = tween(t, T.swap, 0.12, 0, 1, ease.in);
labelA.style.transform = `translateY(${-8 * out}px)`; labelA.style.opacity = 1 - out;
const inn = tween(t, T.swap + 0.07, 0.22, 0, 1, ease.out);
labelB.style.transform = `translateY(${8 * (1 - inn)}px)`; labelB.style.opacity = inn;
btn.style.width = springTo(t, T.swap, wA, wB, springs.snappy) + "px";
```
**Motion:** `<AnimatePresence mode="popLayout" initial={false}><motion.span key={label} initial={{y:8,opacity:0}} animate={{y:0,opacity:1}} exit={{y:-8,opacity:0}} /></AnimatePresence>` inside a `<motion.button layout>`.
**SwiftUI:** `Text(label).contentTransition(.interpolate)` (iOS 17) or `.id(label)` with
`.transition(.asymmetric(insertion: .move(edge: .bottom).combined(with: .opacity), removal: .move(edge: .top).combined(with: .opacity)))`.
**Compose:** `AnimatedContent(label, transitionSpec = { (slideInVertically { it / 3 } + fadeIn()) togetherWith (slideOutVertically { -it / 3 } + fadeOut()) using SizeTransform(clip = false) })`.

---

## 5. Stroke draw-on

**When:** checkmarks, line icons, signatures, chart lines, logo outlines, connector lines in explainers.

**Parameters:** `stroke-dasharray = L`, `stroke-dashoffset` from L → 0 (L = `getTotalLength()`).
Icons take 250–400ms with `out`. Long paths scale with length (about 1px per ms, capped at 900ms).
Multi-segment icons: stagger segments by 60–100ms in drawing order (the way a hand would draw it).

**Failures:** wrong direction (the path starts at the wrong end, so reverse it in the SVG); round caps
showing a dot at length 0 (set opacity 0 until progress > 0.01); non-scaling strokes with transforms
(`vector-effect: non-scaling-stroke` changes the length); dash artifacts at joins with `L` slightly
too small (use `L + 1`).

**seek:**
```js
const L = path.getTotalLength() + 1;
path.style.strokeDasharray = L;
const p = tween(t, T.check, 0.32, 0, 1, ease.out);
path.style.strokeDashoffset = L * (1 - p);
path.style.opacity = p > 0.01 ? 1 : 0;
```
**CSS:** `@keyframes draw { from { stroke-dashoffset: var(--L) } to { stroke-dashoffset: 0 } }`, or
with `pathLength="1"` on the path, use `stroke-dasharray: 1` and animate the offset from 1 → 0. No
JS measurement needed.
**Motion:** `<motion.path initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.32, ease: [0.16,1,0.3,1] }} />`.
**SwiftUI:** `checkPath.trim(from: 0, to: p).stroke(style: StrokeStyle(lineWidth: 2.5, lineCap: .round))`.
**Compose:** `PathMeasure().apply { setPath(path, false) }.getSegment(0f, length * p, dst, true)`, then
`drawPath(dst, …)`.
**Lottie:** shape layer plus Trim Paths (End 0 → 100%). **Rive:** trim path on the stroke, keyed in
a state.

---

## 6. Path and shape morphing

**When:** icon state changes (play ↔ pause, menu ↔ close, plus ↔ x), blob backgrounds, logo
transformations.

**Parameters:** both shapes need the **same number of points and commands in compatible order**. Author
them that way: menu ↔ close is 3 lines → 2 lines + 1 collapsing line, not a path library guess. Duration
250–350ms for icons (`standard` or `snappy`). Combine with a rotation of 90–180° for a "turn into"
feel.

**Failures:** points twisting through each other (wrong correspondence or winding); a midpoint shape that
looks like garbage (check the 50% frame on a contact sheet); stroke-width changes in scaled SVG.

**seek** (menu ↔ close, 24×24, three lines):
```js
const p = springTo(t, T.toggle, 0, 1, springs.snappy);
// top: (4,7)-(20,7) → (6,6)-(18,18); middle fades and shrinks to centre; bottom mirrors top
top.setAttribute("d", `M${mix(4,6,p)} ${mix(7,6,p)} L${mix(20,18,p)} ${mix(7,18,p)}`);
mid.setAttribute("d", `M${mix(4,12,p)} 12 L${mix(20,12,p)} 12`); mid.style.opacity = 1 - p;
bot.setAttribute("d", `M${mix(4,6,p)} ${mix(17,18,p)} L${mix(20,18,p)} ${mix(17,6,p)}`);
```
**Web:** same math with Motion values, or the `flubber` library for arbitrary paths (check the
midpoints). CSS `d: path()` transitions work in Chromium only. Avoid them for cross-browser use.
**SwiftUI:** a custom `Shape` with `animatableData` (an `AnimatablePair` of progress) builds the path
from `p`. **Compose:** `PathParser` plus `lerp` of nodes (`androidx.compose.ui.graphics.vector.lerp`),
or `AnimatedVectorDrawable` with `pathData` morphs. **Lottie/Rive:** keyframe the shape vertices
(Rive handles vertex correspondence best).

---

## 7. Circular reveal that clears the farthest corner

**When:** a state floods from a point (theme switch from a toggle, FAB → screen, a "connected" status
filling a card, transitioning to a photo).

**Parameters:** radius from 0 to `hypot(max(x, W − x), max(y, H − y)) × 1.05`, measured from the
origin point to the **farthest** corner (the 1.05 hides antialiasing at the corner). Use `emphasized`
or `out` over 400–550ms. The reverse (close) uses `in` at 70% of the duration toward the original
point.

**Failures:** radius computed to the nearest edge (leaves corners uncovered); the origin isn't the
trigger (breaks spatial logic); clip-path on a huge layer with heavy content (paints every frame:
pre-render or keep the content simple); text under the reveal edge flickering (fine, the edge
is short-lived).

**seek:**
```js
const R = Math.hypot(Math.max(ox, W - ox), Math.max(oy, H - oy)) * 1.05;
const r = tween(t, T.reveal, 0.48, 0, R, ease.emphasized);
layer.style.clipPath = `circle(${r}px at ${ox}px ${oy}px)`;
```
**Web live:** the same `clip-path` with WAAPI. Or the View Transitions API with
`::view-transition-new(root) { animation: reveal 480ms cubic-bezier(0.3,0,0,1) }` and
`@keyframes reveal { from { clip-path: circle(0 at var(--x) var(--y)) } }`.
**SwiftUI:** `.mask(Circle().frame(width: 2*r, height: 2*r).position(origin))`.
**Compose:** `Modifier.drawWithContent { clipPath(Path().apply { addOval(Rect(origin, r)) }) { this@drawWithContent.drawContent() } }`.
On Android Views: `ViewAnimationUtils.createCircularReveal(view, x, y, 0f, R)`.
**Lottie:** an ellipse mask with expanding size keyframes.

---

## 8. Stagger cascade

**When:** lists, grids, groups of cards, menu items, icon rows arriving together.

**Parameters:** step 30–60ms (small items) or 60–90ms (cards). Total ≤ about 400ms (cap with
`stagger(i, step, cap)`). Travel 8–16px plus an opacity ramp over the first 120–160ms. Spring `smooth`
or `snappy`. Grids stagger by distance from the origin (`hypot(row, col)`) or by reading order, not by
index alone. Exits: no stagger, or reverse order at half the step.

**Failures:** a constant step across 20 items (the last one lands at 1.2s); offscreen items
staggering (only stagger what's visible; the rest render in place); every item with large travel (busy);
stagger on re-renders (only on first appearance or real inserts).

**seek:**
```js
items.forEach((el, i) => {
  const s = T.list + stagger(i, 0.05, 0.25);
  el.style.opacity = tween(t, s, 0.14, 0, 1, ease.linear);
  el.style.transform = `translateY(${mix(14, 0, sItem(t - s))}px)`;
});
```
**Motion:** `variants` with `transition: { staggerChildren: 0.05, delayChildren: 0.1 }` on the parent.
Or `animate(items, { y: [14, 0], opacity: [0, 1] }, { delay: stagger(0.05, { startDelay: 0.1 }) })`.
**SwiftUI:** `.transition(.move(edge: .bottom).combined(with: .opacity))` per row, with
`.animation(.spring(response: 0.39, dampingFraction: 1).delay(min(Double(i) * 0.05, 0.25)), value: shown)`.
**Compose:** `LazyColumn` with `Modifier.animateItem()` for inserts. For first appearance, per-item
`AnimatedVisibility` with `tween(delayMillis = min(i * 50, 250))`.

---

## 9. Depth parallax

**When:** layered illustrations, onboarding hero art, scroll-linked headers, gyroscope-subtle
wallpapers.

**Parameters:** 2–4 layers. Foreground moves 1.0× the reference motion, mid 0.6×, background
0.25–0.35×. Keep total background travel ≤ 24px for UI (more for explainers). Scroll-linked: linear
mapping to scroll, so no easing between scroll and layer. A spring follow (`gentle`) only for pointer
or gyro parallax.

**Failures:** vestibular discomfort (disable under reduced motion: layers move together or not at all);
layers revealing edges (bleed artwork by max travel); too many layers (mush); parallax on text
(readability).

**seek:** `layers.forEach(l => l.el.style.transform = \`translate3d(0, ${-scroll * l.depth}px, 0)\`)`,
where `scroll` is itself a function of t in demos.
**CSS live:** scroll-driven animations:
`animation: drift linear both; animation-timeline: scroll(root); @keyframes drift { to { transform: translateY(calc(var(--depth) * -120px)) } }`.
**SwiftUI:** `GeometryReader` or `.visualEffect { content, proxy in content.offset(y: proxy.frame(in: .scrollView).minY * -0.3) }` (iOS 17).
**Compose:** read `LazyListState.firstVisibleItemScrollOffset` inside `graphicsLayer { translationY = -offset * depth }` (read in the layer block to avoid recomposition).
**Rive:** a scroll input driving layer translation through a state machine.

---

## 10. Spring follow-through on release (velocity handoff)

**When:** anything dragged and then released: sheets, cards, carousels, sliders, pull-to-refresh,
draggable FABs.

**Parameters:** track pointer samples over the last 80ms. Velocity = Δposition / Δtime (px/s) at
release. Pick the target by projecting momentum: `projected = pos + v * 0.2` (iOS-like deceleration,
or `v² / (2 · 3000px/s²)`). Snap to the nearest detent of the projected point. Hand velocity to the spring
in units of remaining travel per second: `v0 = v / (target - pos)`. Spring `sheet` or `drag`, with
ζ ≥ 0.95 when overshooting a boundary would look broken.

**Failures:** velocity from only the last event (noisy: use a short window or a least-squares fit);
choosing a target by position alone (a flick with short travel doesn't commit); restarting the spring at
velocity 0 (the "dead stop then ease" feel); velocity sign errors on reverse flicks.

**seek (demo timeline):** script the release at `T.release` with a known velocity, so the review shows
the handoff:
```js
const sRel = spring({ stiffness: 400, damping: 38, velocity: 1200 / (target - releaseY) });
y = t < T.release ? dragPath(t) : mix(releaseY, target, sRel(t - T.release));
```
**Motion:** `drag="y" dragConstraints={…} dragTransition={{ bounceStiffness: 400, bounceDamping: 38 }}`.
Or `animate(y, target, { type: "spring", velocity: info.velocity.y, stiffness: 400, damping: 38 })` in
`onDragEnd`.
**SwiftUI:** `DragGesture().onEnded { v in withAnimation(.interpolatingSpring(stiffness: 400, damping: 38, initialVelocity: v.velocity.height / remaining)) { offset = target } }`.
On iOS 17+, `value.velocity` is available directly.
**Compose:** `Animatable.animateTo(target, spring(0.95f, 400f), initialVelocity = velocityTracker.calculateVelocity().y)`.
`AnchoredDraggable` handles detents and velocity for you.

---

## 11. Rubber-banding

**When:** dragging past a boundary (overscroll, a sheet pulled above its top detent, a slider past
its end).

**Parameters:** the iOS formula `b(x) = (1 − 1/(x·c/d + 1)) · d`, where x is the overshoot distance,
d is the dimension (view height) and c ≈ 0.55. Release springs back with `drag` (ζ 0.82) carrying the
release velocity.

**Failures:** linear resistance (feels like hitting a wall); no resistance (feels broken); the spring-back
ignoring velocity.

**seek / any platform:**
```js
const rubber = (x, d, c = 0.55) => Math.sign(x) * (1 - 1 / (Math.abs(x) * c / d + 1)) * d;
sheetY = dragY < topDetent ? topDetent + rubber(dragY - topDetent, H) : dragY;
```
**Native:** iOS `UIScrollView` does this natively. Compose `overscroll` effects (Android 12+ stretch),
or apply the same formula in `pointerInput`.

---

## 12. Press squash

**When:** buttons, cards, tappable rows. Any tap target that should feel physical.

**Parameters:** on **touch-down** (not release), scale to 0.96–0.98 (buttons) or 0.98–0.99 (large
cards), using the `press` spring or 80–100ms `out`. Release: spring back with `press` (ζ 0.83, a tiny
overshoot is fine). Optional: brightness 0.96 or a 2% darker fill. Hold scale while pressed. A cancelled
press (finger drags away) releases without firing.

**Failures:** feedback on release (feels laggy); a large squash (0.9 reads as broken); scaling the text
blurry (scale the container. Text scales with it but stays crisp at ≥ 0.96); press state stuck after a
scroll-cancel.

**seek (demo timeline):**
```js
const st = Motion.demoState(t, [{ at: 0, state: "idle" }, { at: 0.5, state: "down" }, { at: 0.62, state: "up" }]);
const target = st.state === "down" ? 0.97 : 1;
const from = st.prev === "down" ? 0.97 : 1;
btn.style.transform = `scale(${springTo(st.since, 0, from, target, springs.press)})`;
```
**CSS live:** `.btn:active { transform: scale(0.97) } .btn { transition: transform 160ms cubic-bezier(0.34,1.36,0.64,1) }`. Use `:active` plus `touch-action: manipulation`, and `@media (hover: hover)` for hover styles only.
**SwiftUI:** a custom `ButtonStyle` with `.scaleEffect(configuration.isPressed ? 0.97 : 1).animation(.spring(response: 0.21, dampingFraction: 0.83), value: configuration.isPressed)`.
**Compose:** `val pressed by interactionSource.collectIsPressedAsState()`, then `graphicsLayer { scaleX = s; scaleY = s }`, where `s = animateFloatAsState(if (pressed) 0.97f else 1f, spring(0.83f, 900f))`.

---

## 13. Magnetic hover

**When:** prominent CTAs and cursor-driven desktop or web UI, **pointer devices only**
(`@media (hover: hover) and (pointer: fine)`).

**Parameters:** inside an activation radius (element size + 40px), translate the element toward the
cursor by 15–30% of the offset, capped at 6–10px. Inner content (icon or label) moves an extra 30%
for depth. Use the `drag` spring for follow, and `snappy` to return on leave.

**Failures:** on touch devices (no hover: it fires on tap and sticks); large pull (the button chases the
cursor and is hard to click); jitter from unsmoothed pointer events (always spring-follow, never set
position directly); moving the hit target so far that the click misses.

**seek (demo timeline):** a cursor path (`Motion.path`) defines the pointer position. The element offset
is `clamp(0.25 * (cursor − centre), ±8px)`, followed with a spring evaluated from the last target change.
For review, script 2–3 cursor passes.
**Motion:** `useMotionValue` x/y set from `onPointerMove`, smoothed with `useSpring(x, { stiffness: 600, damping: 40 })`.
**SwiftUI (macOS/iPadOS):** `.onContinuousHover { phase in … }` driving an offset with
`.spring(response: 0.26, dampingFraction: 0.82)`. On iPadOS, `.hoverEffect(.lift)` is the native
equivalent: prefer it there.

---

## 14. Number counters

**When:** stats, prices, scores, totals and progress percentages that change or reveal.

**Parameters:** tween the **value**, not the digits, with `outQuart` over 600–1200ms (bigger change →
longer, capped). Format every frame with the final format (same decimals and separators), using
`font-variant-numeric: tabular-nums` so width doesn't jitter. Optional: odometer per-digit roll for
small integer changes (each digit column slides with `snappy`).

**Failures:** proportional digits jittering; counting through thousands of values with no visible
meaning (cap the duration); rounding direction flip-flopping at the end (use floor for ascending
counters, and land exactly on the final value at p = 1); counters on numbers the user must trust
mid-motion, like a bank balance (show the final value immediately and animate a highlight instead).

**seek:** `el.textContent = fmt(Math.floor(mix(from, to, tween(t, T.count, 0.9, 0, 1, ease.outQuart))))`.
**Web:** the same in rAF, or Motion `animate(0, 1284, { duration: 0.9, ease: [0.25,1,0.5,1], onUpdate: v => el.textContent = fmt(v) })`.
**SwiftUI:** `Text(value, format: .number).contentTransition(.numericText(value: value))` with
`withAnimation(.snappy) { value = new }` (iOS 17). This is the native odometer.
**Compose:** `AnimatedContent(targetState = count, transitionSpec = { slideInVertically { it } togetherWith slideOutVertically { -it } })` per digit, or `animateIntAsState`.

---

## 15. Skeleton-to-content handoff

**When:** any loading state with known layout.

**Parameters:** skeleton blocks **match the final layout's geometry** (same heights, line counts,
radii). Optional shimmer: a linear gradient sweep, 1.2–1.6s period, linear, low contrast (4–6%). When
content arrives: crossfade skeleton → content **per block** over 180–240ms, no travel (the positions
already match), with a light stagger (30ms) in reading order. Minimum skeleton display time 300–500ms
if it appeared at all, so it never flashes for 80ms. Don't show a skeleton for loads under about 200ms:
use a delay before showing.

**Failures:** skeleton shapes that don't match (content jumps on arrival); shimmer that's too strong
or too fast (anxious); everything popping in at once; a spinner inside a skeleton.

**seek:**
```js
blocks.forEach((b, i) => {
  const p = tween(t, T.loaded + stagger(i, 0.03, 0.15), 0.2, 0, 1, ease.standard);
  b.skeleton.style.opacity = 1 - p; b.content.style.opacity = p;
});
shimmer.style.transform = `translateX(${mix(-100, 100, (t % 1.4) / 1.4)}%)`; // linear loop
```
**Web:** `@keyframes shimmer { to { transform: translateX(100%) } }` at `1.4s linear infinite`. Use
`@media (prefers-reduced-motion: reduce)` to make the shimmer a static block.
**SwiftUI:** `.redacted(reason: .placeholder)` for the skeleton, with
`.transition(.opacity.animation(.easeOut(duration: 0.2)))` on content.
**Compose:** the `placeholder` modifier (accompanist-style), or a `Brush.linearGradient` with an animated
offset from `rememberInfiniteTransition`. Use `Crossfade(loaded)` for the handoff.

---

## 16. Chart draw-in and data-state transitions

**When:** charts entering, data updating, a filter or time range changing.

**Parameters:**
- **Draw-in:** line charts use a stroke draw-on (recipe 5) along x over 600–900ms with `outCubic`. Bars
  grow from the baseline (scaleY with `transform-origin: bottom`), staggered by 20–30ms in x order,
  capped at 300ms total. Axes and gridlines fade in first (120ms), then data.
- **State transition:** **interpolate data values, not screen positions**. Each point keeps its
  identity (key by id/date). Domain or axis changes animate the scale at the same time as the data, so
  marks never lie mid-motion. 350–500ms with `standard`. Entering points grow from the baseline or a
  neighbour. Exiting points collapse to the baseline.

**Failures:** misrepresenting values mid-motion (a bar briefly longer than either its old or new value
because the axis animates separately); points swapping identity (sorted by index instead of id);
y-axis labels changing instantly while bars animate; pie slices interpolating start/end angles
independently (interpolate the underlying values and recompute angles).

**seek:**
```js
const p = tween(t, T.update, 0.42, 0, 1, ease.standard);
const yMax = mix(oldMax, newMax, p);                         // the axis animates with the data
data.forEach(d => {
  const v = mix(d.old ?? 0, d.new ?? 0, p);                  // value space, not pixels
  d.el.style.transform = `scaleY(${v / yMax})`;
});
```
**Web:** D3 `transition().duration(420).ease(d3.easeCubicOut)` with keyed joins (`.data(rows, d => d.id)`).
**SwiftUI:** Swift Charts animates keyed marks automatically inside `withAnimation(.smooth)`. Keep `id`s
stable. **Compose:** Vico or custom `Canvas` drawing from `animateFloatAsState` per value.

---

## 17. Logo assembly and mask reveal

**When:** splash, app intro, video bumpers, loading-to-brand moments.

**Parameters:** three deliverables from one source: a **sting** (0.8–1.6s), a **full reveal**
(2–3s, for video), and an **idle** (seamless loop, optional). The final frame matches the static mark
**exactly** (overlay the SVG to verify, pixel diff = 0). Techniques: per-part assembly along each
part's natural axis, stroke draw-on then fill, mask wipe along the mark's dominant direction, letter
rises for the wordmark (recipe 1). The lead part enters first. The last 300ms is a settle, then hold.

**Failures:** distortion (non-uniform scale on the mark); the end frame not matching (sub-pixel
offsets, a rounding difference); clear-space violations during motion (the mark overflows its safe
area); gratuitous particles or glow; the wordmark blurry because it was scaled.

**seek:** each part gets `springTo` or `tween` from an offset to identity. At `t >= T.end` every
transform is exactly `none`:
```js
if (t >= T.end) { parts.forEach(p => (p.el.style.transform = "none")); return; }
```
**Formats:** Lottie (vector, recolourable) for in-app. Rive if it needs states (idle → hover → pressed).
MP4 and WebM alpha for marketing. SVG plus CSS for the web hero.

---

## 18. Seamless loop construction

**When:** loading loops, ambient illustrations, idle states, animated backgrounds, GIF/video loops.

**Parameters:**
- Choose the loop period T so duration × fps is an integer (2.0s, 2.4s or 3.0s at 60fps).
- Every moving property is a periodic function with an **integer number of cycles** in T:
  `sin(2π·n·t/T + φ)`. Different elements use different n (1, 2, 3) and phases for organic variety.
- Piecewise tweens must start and end at zero velocity at the seam (`sine`, `inOut`) **and** match
  values. The seam frame (t = T) is not rendered (`frame_times` excludes it for loops).
- Random variation comes from `mulberry32(seed)` at load, never per frame.

**Failures:** the position matches but the velocity doesn't (a visible "bounce" off the seam); a
non-integer cycle count (a jump); rotation of a non-symmetric object by a non-multiple of its symmetry
angle; noise functions that aren't periodic (wrap them on a circle: sample 2D noise at
`(cos 2πt/T, sin 2πt/T) · r`).

**seek:**
```js
const TAU = Math.PI * 2;
blobs.forEach((b, i) => {
  const n = b.cycles, ph = b.phase;                  // integers / seeded phases
  b.el.style.transform = `translate(${b.ax * Math.sin(TAU * n * t / T + ph)}px, ${b.ay * Math.sin(TAU * n * t / T + ph + 1.3)}px)`;
});
```
Verify with `loop_check.py` (position and velocity).

---

## 19. Cursor and finger choreography for explainers

**When:** feature explainers, onboarding demos, App Store and Google Play previews, marketing videos of
real UI.

**Parameters:**
- **Cursor paths are curved and eased**, never straight and linear: an arc through a control point
  offset 10–20% perpendicular to the travel, `inOut` over 400–900ms (longer for longer distances: about
  `250 + 0.6 · distance` ms).
- **Aim, then act:** arrive, settle 120–200ms, press (cursor scales 0.9 for 80ms, then the target's
  press squash), release, wait 150ms, and only then the UI responds. Never click on arrival.
- Finger (touch): a 44px translucent dot (white 70% with a soft shadow), press = scale 0.85 plus
  opacity 90%. Swipes follow the content 1:1, then release with velocity (recipe 10).
- The cursor never crosses text the viewer is reading. Park it after use, out of the focal area.
- Readable muted: every action leaves a visible result for ≥ 600ms before the next.

**Failures:** robotic straight-line moves; clicking mid-flight; too fast to follow (watch at 1× with no
context); the cursor covering the result; scripted UI that is a video of the real UI rather than a
rebuild (rebuild in code so it's crisp at every resolution and editable).

**seek:**
```js
const c = Motion.path(t, [[0, 120, 600], [0.8, 260, 420], [1.6, 260, 420], [2.3, 330, 180]], ease.inOut);
cursor.style.transform = `translate(${c.x}px, ${c.y}px) scale(${pressAt(t, 1.0) ? 0.9 : 1})`;
```
Add a perpendicular bow by mixing in `sin(π · segmentProgress) · bow` on the normal axis.
