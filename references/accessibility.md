# Accessibility

Motion is optional decoration on top of a UI that must work without it. Every spec has a
**reduced-motion section**, and every build implements it.

## Reduced motion on every platform

| Platform | Setting | Read it |
|---|---|---|
| Web | OS setting → `prefers-reduced-motion: reduce` | CSS `@media (prefers-reduced-motion: reduce)`; JS `matchMedia('(prefers-reduced-motion: reduce)')` (listen for `change`); Motion `useReducedMotion()` |
| iOS / iPadOS | Settings → Accessibility → Motion → Reduce Motion (+ Prefer Cross-Fade Transitions, Auto-Play Animated Images) | SwiftUI `@Environment(\.accessibilityReduceMotion)`; UIKit `UIAccessibility.isReduceMotionEnabled` + `reduceMotionStatusDidChangeNotification` |
| macOS | System Settings → Accessibility → Display → Reduce motion | `NSWorkspace.shared.accessibilityDisplayShouldReduceMotion` |
| Android | Settings → Accessibility → Remove animations (animator duration scale 0) | Compose animations jump to end automatically; `Settings.Global.ANIMATOR_DURATION_SCALE` for custom handling |
| Windows | Settings → Accessibility → Visual effects → Animation effects | `UISettings.AnimationsEnabled`; web: `prefers-reduced-motion` |
| React Native | the platform settings above | `AccessibilityInfo.isReduceMotionEnabled()`; Reanimated `useReducedMotion()` / `ReduceMotion.System` |

In `motion-runtime.js`, `Motion.reduced` is true when `?reduced=1` or the media query matches.
Every `seek(t)` branches on it. The player's "Reduced motion" toggle and `render.py --reduced`
review it.

## What reduced motion means

Reduced is **not** "no feedback". It means no vestibular triggers:

| Replace | With |
|---|---|
| Travel (slides, pushes, large translate) | crossfade in place, 150–200ms |
| Zoom / scale transitions (especially full-screen) | crossfade; small scale (≤ 2%) is OK for press feedback |
| Parallax, scroll-linked depth | layers move together (no differential), or static |
| Spinning, rotating backgrounds; looping ambient motion | static frame, or a slow opacity pulse (≥ 2s period) |
| Bouncy springs | critically damped, short |
| Auto-playing video and animated illustrations | poster frame plus a play control |

Keep: progress indicators (linear fill), focus rings, colour and opacity state changes, the press tint,
and the final states of everything. Information carried by motion (where a thing went) must survive:
use the destination's highlight, a badge, or announcement text.

## Vestibular safety beyond the setting

Even without the setting, avoid: large-area motion filling the viewport with no user trigger,
scroll-jacking, parallax at large ratios (> 0.5 difference between layers), rapid zooms, and spinning
of large elements. These are WCAG 2.3.3 (AAA) territory. Treat them as defaults to avoid, not
extras.

## Flashing (WCAG 2.3.1, Level A)

**No more than 3 flashes in any 1-second period**, unless the flashing area is small (< about 25% of
10° of visual field: roughly 341×256 px at typical viewing distance) and isn't saturated red. A flash
is a pair of opposing luminance changes of ≥ 10% where the darker state is below 0.80 relative
luminance. Glitch effects, strobing success states and rapid colour cycling are the usual culprits.
Error shakes and pulsing badges must stay under this.

## Pause, stop, hide (WCAG 2.2.2, Level A)

Any moving, blinking or scrolling content that **starts automatically, lasts more than 5 seconds, and
is presented alongside other content** needs a mechanism to pause, stop or hide it. That means a pause
control, stopping on its own within 5s, or playing only on hover or focus. This applies to looping
illustrations, animated backgrounds, carousels and autoplay video. Loading indicators are exempt while
loading is actually happening.

## Motion never blocks the task

- Inputs are accepted during transitions (interruptible). The user never waits for choreography to
  finish before tapping the next thing.
- Entrance animations never delay content availability for screen readers. The DOM or accessibility
  tree is complete immediately, and only presentation animates.
- Long sequences (onboarding illustrations, explainers) can be skipped.
- Don't hide content behind a scroll-triggered reveal that requires motion to read it. In the
  no-animation case, content must be visible.

## Focus stays visible

- Focus rings appear instantly on keyboard focus (a fade-in ≤ 100ms is the maximum). No delayed or
  animated-in focus that leaves an unfocused gap.
- During and after transitions, focus moves to the new context (dialog → first focusable,
  closed dialog → its trigger). Animating elements must not trap or lose focus.
- Elements mid-animation shouldn't move under the focus ring in a way that detaches the ring.

## Checklist (put it in the test report)

- [ ] Reduced version designed in the spec and implemented (player toggle and `--reduced` render
      reviewed)
- [ ] No travel, zoom or parallax in reduced, and state still readable
- [ ] ≤ 3 flashes per second at every point (check the jank report and contact sheets)
- [ ] Anything that loops longer than 5s can be paused, or stops
- [ ] Inputs work mid-transition; nothing waits on animation
- [ ] Focus visible and correctly placed through every transition
