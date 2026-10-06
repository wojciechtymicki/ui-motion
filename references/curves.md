# Curves and springs: a taste library

**This is a library to choose from with reasoning. It is not a word-to-value lookup table.** "Smooth"
in a brief doesn't mean the `smooth` spring. It means: work out what the motion is for (profile,
platform, distance, frequency, what the reference shows), pick the curve whose *character* fits, and
write the exact value plus one line of why into the spec. Values here are tuned starting points.
Adjust them to distance and size, and record the adjustment.

All named curves exist in `motion-runtime.js` as `Motion.ease.<name>` and all springs as
`Motion.springs.<name>`, so a spec value is directly runnable.

---

## How to choose

1. **Is the user touching it, or could it be interrupted mid-flight?** → spring (section 2).
2. **Entering or settling into place?** → decelerate (ease-out family).
3. **Leaving or committing (dismiss, send, delete)?** → accelerate (ease-in family), shorter.
4. **Moving between two on-screen positions?** → ease-in-out (symmetric or emphasized).
5. **Representing a constant-rate quantity (progress, rotation, time)?** → linear.
6. **Rendered piece with a hero moment?** → stronger curves (expo-out, emphasized) and longer tails are
   fine. There's no interaction to block.

Duration and curve trade off against each other. A strong ease-out (`out`) looks "done" at about 60% of
its duration, so it can carry a longer nominal duration than a gentle one (`outCubic`) for the same
perceived speed.

---

## 1. Cubic-bezier curves

| Name (runtime) | cubic-bezier | Character | Use it for | Typical duration |
|---|---|---|---|---|
| `standard` | `0.2, 0, 0, 1` | Decisive start, long soft landing. Material 3 "standard". The safest default for UI state changes. | Container transforms, tab indicator, small size changes | 200–300ms |
| `out` | `0.16, 1, 0.3, 1` | Expo-like: fast immediately, then glides. Feels instant and premium. Most of the travel happens in the first 30%. | Entrances, sheets, toasts, hero reveals, masked text rise | 300–600ms |
| `outQuart` | `0.25, 1, 0.5, 1` | Strong deceleration without the expo "snap". Calmer than `out`. | List items, cards entering, popovers | 250–450ms |
| `outCubic` | `0.33, 1, 0.68, 1` | Gentle decel. Visible motion through the end. Friendly, unhurried. | Large, slow elements (backgrounds, illustration layers), onboarding | 400–700ms |
| `emphasizedDecel` | `0.05, 0.7, 0.1, 1` | Material 3 emphasized decelerate: very fast start, very long tail. Dramatic. | Full-screen entrances, FAB → screen, expressive moments | 400–500ms |
| `emphasized` | `0.3, 0, 0, 1` | Short wind-up then strong decel. Has intent: it gathers, then goes. | Shared-element morphs, navigation between peers | 400–500ms |
| `in` | `0.55, 0, 1, 0.45` | Accelerates away and leaves at speed. Never "lands". | Exits, dismissals, deletes | 150–250ms |
| `inCubic` | `0.32, 0, 0.67, 0` | Softer accelerate. | Exits of large content, fade-outs that must not feel abrupt | 200–300ms |
| `emphasizedAccel` | `0.3, 0, 0.8, 0.15` | Material 3 emphasized accelerate. | Full-screen exits paired with `emphasizedDecel` | 200ms |
| `inOut` | `0.65, 0, 0.35, 1` | Strong symmetric S: settled at both ends, fast through the middle. | On-screen → on-screen travel, reorder, selection pill, carousel snap without gesture | 300–500ms |
| `sine` | `cos`-based | Gentlest symmetric curve. Zero velocity at both ends. | Loops, breathing, floating, pendulum halves | per cycle |
| `backOut` | `0.34, 1.36, 0.64, 1` | About 6% overshoot then settle, in one tween. A spring look-alike when you can't use springs (CSS, Lottie). | Rare, playful entrances, badges, success ticks | 350–500ms |
| `anticipate` | `0.36, 0, 0.66, -0.56` | Pulls back about 10% before going. Cartoon wind-up. Use sparingly. | Logo stings, explainer cursors "aiming", playful briefs only | 300–500ms |
| `linear` | `0, 0, 1, 1` | Constant rate. No mass. | Rotation, determinate progress, marquees, scroll-locked parallax | n/a |

Platform defaults, for matching native feel (not for copying):

| Platform | Curve | Notes |
|---|---|---|
| CSS `ease` | `0.25, 0.1, 0.25, 1` | Browser default. Slightly sluggish start. Replace it. |
| CSS `ease-out` | `0, 0, 0.58, 1` | Weak decel. `outQuart` is almost always better. |
| iOS UIView `.curveEaseInOut` | `0.42, 0, 0.58, 1` | Legacy. Modern iOS uses springs. |
| Material 3 standard decelerate | `0, 0, 0, 1` | Entering, small elements |
| Material 3 standard accelerate | `0.3, 0, 1, 1` | Exiting, small elements |

---

## 2. Springs

Mass is 1 throughout. ζ (damping ratio) = c / (2√(k·m)). ω₀ = √(k/m). Settle = time until within 0.1% of
the target with negligible velocity (the runtime's rule). A spring looks finished at the **t90**
column (90% of travel), so judge perceived speed by t90, not settle.

| Name | stiffness k | damping c | ζ | t90 | Settle | Overshoot | Character | Use it for |
|---|---|---|---|---|---|---|---|---|
| `press` | 900 | 50 | 0.83 | 104ms | 299ms | 0.9% | Instant, firm, a hint of give | Touch-down squash and release, small toggles |
| `tooltip` | 700 | 48 | 0.91 | 130ms | 306ms | 0.1% | Quick, no wobble | Tooltips, menus, small popovers |
| `drag` | 600 | 40 | 0.82 | 125ms | 367ms | 1.2% | Tight follow with a whisper of overshoot | Dragged objects catching up, snap-back after drag |
| `snappy` | 520 | 42 | 0.92 | 154ms | 319ms | 0.06% | Responsive, critically damped feel | Toggles, segmented controls, chips, list reorder |
| `sheet` | 400 | 38 | 0.95 | 183ms | 399ms | ~0% | Weighty but quick | Bottom sheets, side panels, drawers (with velocity) |
| `lively` | 380 | 26 | 0.67 | 130ms | 553ms | 6.0% | Visible, friendly overshoot | Rare celebratory moments, onboarding hero, success badge |
| `smooth` | 260 | 32 | 0.99 | 239ms | 559ms | 0% | Calm, no overshoot, "expensive" | Cards and content entering, page-level transitions |
| `page` | 220 | 30 | 1.01 | 267ms | 644ms | 0% | Unhurried, overdamped | Full-screen navigation, large surfaces |
| `gentle` | 170 | 24 | 0.92 | 269ms | 556ms | 0.06% | Soft, floaty | Illustration layers, background shifts, parallax catch-up |
| `settle` | 120 | 22 | 1.00 | 357ms | 854ms | 0% | Slow, heavy | Large hero elements in rendered pieces, ambient re-layouts |
| `bouncy` | 300 | 16 | 0.46 | 119ms | 872ms | 19.5% | Toy-like | **Only** when the brief explicitly says playful or bouncy, and never on frequent UI |

### Translating across platforms

| Framework | API | Mapping from (k, c, m = 1) |
|---|---|---|
| `motion-runtime.js` | `spring({stiffness, damping, mass, velocity})` | direct |
| Motion for React / Motion One | `{ type: "spring", stiffness, damping, mass }` | direct. Or `visualDuration` ≈ t90 × 1.1 with `bounce` = 1 − ζ (for ζ ≤ 1) |
| SwiftUI (classic) | `.spring(response:dampingFraction:)` | response = 2π/ω₀ = 2π/√k, dampingFraction = ζ |
| SwiftUI (iOS 17+) | `.spring(duration:bounce:)` | duration = response, bounce = 1 − ζ |
| UIKit | `UISpringTimingParameters(mass:stiffness:damping:initialVelocity:)` | direct. `initialVelocity` is a vector in units of total travel per second |
| Core Animation | `CASpringAnimation` mass/stiffness/damping/initialVelocity | direct. Set `duration = settlingDuration` |
| Jetpack Compose | `spring(dampingRatio = ζ, stiffness = k)` | direct (Compose stiffness assumes mass 1). Built-ins: `StiffnessHigh` 10000, `Medium` 1500, `MediumLow` 400, `Low` 200, `VeryLow` 50 |
| React Native Reanimated | `withSpring(to, { stiffness, damping, mass, velocity })` | direct. Reanimated 3 also accepts `duration` + `dampingRatio` |
| Rive | Not native: drive inputs from code, or bake the curve as keyframes | sample `spring()` into a keyframe table |
| Lottie | No springs: bake it | sample at the export fps and write per-frame keyframes, or approximate with `backOut` |

Precomputed equivalents:

| Name | SwiftUI response / dampingFraction | iOS 17 duration / bounce | Compose dampingRatio / stiffness |
|---|---|---|---|
| press | 0.209 / 0.83 | 0.21 / 0.17 | 0.83 / 900 |
| tooltip | 0.237 / 0.91 | 0.24 / 0.09 | 0.91 / 700 |
| drag | 0.257 / 0.82 | 0.26 / 0.18 | 0.82 / 600 |
| snappy | 0.276 / 0.92 | 0.28 / 0.08 | 0.92 / 520 |
| sheet | 0.314 / 0.95 | 0.31 / 0.05 | 0.95 / 400 |
| lively | 0.322 / 0.67 | 0.32 / 0.33 | 0.67 / 380 |
| smooth | 0.390 / 0.99 | 0.39 / 0.01 | 0.99 / 260 |
| page | 0.424 / 1.0 | 0.42 / 0 | 1.0 / 220 |
| gentle | 0.482 / 0.92 | 0.48 / 0.08 | 0.92 / 170 |
| settle | 0.574 / 1.0 | 0.57 / 0 | 1.0 / 120 |

Native defaults, for reference: SwiftUI `.spring()` = response 0.55, dampingFraction 0.825. SwiftUI
`.snappy` = duration 0.5, bounce 0.15. SwiftUI `.smooth` = bounce 0. SwiftUI `.bouncy` = bounce 0.3.
Compose `spring()` default = `DampingRatioNoBouncy` (1.0) with `StiffnessMedium` (1500). That is
very fast: in Compose, reach for `MediumLow` (400) for anything larger than a chip.

### Velocity

Springs take initial velocity in **units of the full travel per second**. A sheet released at
1200px/s with 400px left to travel gets `velocity: 3`. Over-damped springs (ζ > 1) absorb a fling
without overshoot. Under-damped ones carry it through as overshoot. That is often exactly right for
a flicked card, and wrong for a sheet (it would overshoot the screen edge), so use ζ ≥ 0.95 there.

### Adjusting for size and distance

Large objects should feel heavier. For travel above about 400px, or elements wider than about half the
screen, drop stiffness 30–50% (keeping ζ), or step from `smooth` to `page`. For tiny elements (under
32px), increase stiffness (`snappy` → `press`). Don't change ζ to make things "faster": that changes
the character (overshoot), not the speed.

---

## 3. Choosing durations for tweens

- **Distance:** about 150ms per 100px on mobile (with ease-out), +30% on desktop for the same visual
  angle at larger distances. Cap full-screen moves at 400–450ms (mobile) or 500ms (desktop).
- **Size:** scale and opacity-only changes on small elements take 100–200ms.
- **Frequency** sets the ceiling (see `principles.md` rule 3).
- **Exits** take 60–75% of the matching entrance.
- **Reduced motion:** 100–200ms opacity-only.

## 4. Fingerprints, for identifying a reference's curve

`measure_motion.py` fits these automatically. By eye:

| Look | Probably |
|---|---|
| Jumps most of the way in 2–3 frames, then glides for a long time | `out` / `emphasizedDecel` |
| Clear acceleration, then deceleration, with a visibly fast middle | `inOut` |
| Gentle start and gentle end, nearly constant middle | `sine` / CSS `ease-in-out` |
| Passes the target once, comes back, done | spring ζ ≈ 0.65–0.8 or `backOut` |
| Passes the target and oscillates 2+ times | spring ζ < 0.5 |
| Arrives at speed and stops dead | a cheap ease-out or linear with a hard stop: avoid |
