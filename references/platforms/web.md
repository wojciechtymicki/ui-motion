# Web

## Stack choice

- **CSS transitions / keyframes:** hover, focus, press, simple enter/exit. Compositor-run when limited
  to `transform`/`opacity`.
- **WAAPI** (`el.animate()`): imperative control, sequencing, scrubbing via `currentTime`, `finished`
  promises, `commitStyles()`.
- **Motion** (motion.dev): springs with velocity, gestures, layout and shared-layout animation,
  `AnimatePresence` exits. Use the `animate()` core (≈ 5 KB) outside React.
- **GSAP:** long timelines, ScrollTrigger stories and SVG morph on marketing sites. Overkill for product
  micro-interactions.
- **View Transitions API:** page and state swaps with shared elements (`view-transition-name`).
  Same-document in Chromium and Safari 18+. Feature-detect `document.startViewTransition`.
- **Scroll-driven animations:** `animation-timeline: scroll()` / `view()` (Chromium; Safari 26
  preview). Feature-detect with `@supports (animation-timeline: view())`, with a fallback of a static
  or IntersectionObserver-triggered entrance.

## Conventions

- **Pointer vs touch:** hover styles only under `@media (hover: hover) and (pointer: fine)`. Touch
  gets `:active` feedback and `touch-action: manipulation` (removes the 300ms tap delay; avoid
  double-tap zoom on controls).
- **Pointer Events everywhere** (`pointerdown/move/up`, `setPointerCapture`), not mouse plus touch pairs.
- **Springs in CSS:** generate a `linear()` easing by sampling `Motion.spring()` at about 40 points over
  its settle time. Set `transition-duration` = settle. Good for non-interactive spring looks.
  ```js
  const s = Motion.spring({ stiffness: 400, damping: 38 });
  const pts = Array.from({ length: 41 }, (_, i) => +s(s.settle * i / 40).toFixed(4));
  const css = `linear(${pts.join(", ")})`;   // with duration: s.settle * 1000 + "ms"
  ```
  **WAAPI throws a TypeError on an easing string it doesn't understand** (CSS just ignores the
  declaration). Feature-detect, and keep a bezier stand-in per spring:
  `CSS.supports("transition-timing-function", "linear(0, 1)") ? spring.easing : spring.fallback`
  (`linear()`: Chrome 113, Safari 17.2, Firefox 112).
- **Interruption:** WAAPI and CSS transitions retarget from the current computed value but lose
  velocity. For gesture-driven or rapidly re-triggered motion, use Motion (it carries velocity).
- **Layout changes:** FLIP. Measure first (`getBoundingClientRect`), apply the change, invert with
  transform, then animate to identity. Motion's `layout` prop does this. Never animate `width/height/top/left`
  on anything big.
- **Exit animations** need the element to stay mounted until done: `AnimatePresence`, or
  `el.animate(...).finished.then(remove)`.
- **`will-change`:** add it just before animating, remove it after. Permanent `will-change` on many
  elements wastes memory (one layer each). See `performance.md`.
- **Reduced motion:** `@media (prefers-reduced-motion: reduce)` in CSS; `matchMedia(...)` in JS
  (listen for changes); Motion's `useReducedMotion()` or `MotionConfig reducedMotion="user"`.

## Exposing seek for review

Every web animation has a seek(t) twin in the project's `animation.html` (the review source of truth).
Shipped code reproduces those values. To make **shipped** code scrubbable:

- **WAAPI:** keep the `Animation` objects. `seek(t)` sets `anim.pause(); anim.currentTime = t * 1000 - delay`
  for each (`document.getAnimations()` collects them).
- **CSS animations:** `el.getAnimations()` returns CSSAnimations too, so the same approach works.
- **GSAP:** `tl.pause(); tl.totalTime(t)` (`totalTime` includes repeats and delays).
- **Motion:** `const controls = animate(...); controls.pause(); controls.time = t`.
- **Lottie-web:** `anim.goToAndStop(t * 1000, false)`.
- Then register it: `Motion.register({ ..., seek: t => tl.totalTime(t) })`. The player, `render.py` and
  the tests now drive the production code itself.

## Performance notes

Stay on compositor properties. Avoid animating `filter: blur()` beyond about 8px on large layers, and
`backdrop-filter` on moving elements (very expensive on mobile Safari). Use `content-visibility: auto`
for long lists. Check for layout thrash with `perf_test.js` (Layout/Paint events per frame).
