# Interaction

Read this for anything that responds to input: buttons, toggles, drags, sheets, carousels, hover
effects, gestures.

## 1. State model first

Write the states and every transition between them before writing motion. A button:

```
idle ⇄ hover ⇄ pressed → loading → success → idle
                        ↘ error → idle
any → disabled → idle        any → focus-visible (overlay, independent)
```

Each arrow gets a row in the timing table, with duration or spring and easing. A state with no
designed incoming transition will snap. Independent layers (focus ring, hover tint, press scale)
compose: they are separate properties, never one "state" animation that overwrites the others.

## 2. Interrupt from the current value, carry the current velocity

Any transition can be interrupted by the next input. The rule:

- The new animation starts from the **current presented value** (not the previous target, not the
  start).
- It starts with the **current velocity** (springs accept it; beziers can't, which is why interactive
  things use springs).
- **No queueing.** Re-triggering mid-flight retargets. It does not wait for the first animation to
  finish.

In seek(t) review pages, interruption is shown with a demo timeline that re-triggers mid-flight. The
seek function evaluates the second animation using the first animation's value and velocity at the
interrupt time (`spring.velocity(t)` gives it in closed form):

```js
const a = spring(cfg); const tI = T.retrigger - T.open;           // interrupt time inside the first
const xI = mix(0, 1, a(tI)), vI = a.velocity(tI);                  // value and velocity in travel units
const b = spring({ ...cfg, velocity: -vI / xI });                  // reverse to 0 from xI: remaining travel xI
x = t < T.retrigger ? a(t - T.open) : xI * (1 - b(t - T.retrigger));
```

## 3. Velocity tracking and handoff

- Track pointer samples (time, position) over the last **80–100ms**. Velocity = least-squares slope, or
  (newest − oldest) / Δt over that window. A single-event delta is noise.
- Platform trackers do this: `VelocityTracker` (Compose/Android), `DragGesture.Value.velocity`
  (SwiftUI iOS 17+), `UIPanGestureRecognizer.velocity(in:)`, Gesture Handler `velocityX/Y`, Motion's
  `info.velocity`.
- Hand off: `v_normalized = v_px_per_s / (target − current)`, in spring units of travel per second.
  Watch the sign when the target is behind the release point.
- **Project before choosing the target:** `projected = position + v × 0.2s` (UIScrollView-like
  deceleration). Or physically: `projected = position + v² / (2a) × sign(v)`, with a ≈ 2500–4000 px/s².
  Snap to the detent nearest the projected point. This is what makes a short, fast flick open a sheet.

## 4. Gesture thresholds

| Gesture | Threshold | Notes |
|---|---|---|
| Drag start (touch) | 8–10px | below this it's a tap |
| Drag start (mouse/trackpad) | 3–4px | |
| Direction lock | first 10px decide axis; lock if |dx| > 1.5·|dy| | prevents diagonal jitter in carousels inside scroll views |
| Swipe commit (page, dismiss) | 50% of distance **or** velocity > 500–800 px/s in the direction | either one commits |
| Fling (velocity only) | > 1000 px/s | |
| Long press | 400–500ms | show progress feedback from about 150ms |
| Double tap | ≤ 300ms between taps | delays single-tap actions, so avoid it on controls |

## 5. 1:1 drag with rubber-banding

While the finger is down, the object follows exactly: no easing, no smoothing, no spring. Past
boundaries, apply resistance (`techniques.md` §11):
`b(x) = (1 − 1/(x·0.55/d + 1)) · d`. On release, the spring back takes the release velocity.

Drag the object with `transform` only. Read pointer positions in `pointermove`. Write the transform in
the same frame (rAF batching is OK. Don't throttle beyond the display rate).

## 6. Input modalities

| Modality | Feedback | Notes |
|---|---|---|
| Touch | press on touch-down (scale 0.97, tint); no hover | targets ≥ 44pt (iOS) / 48dp (Android) |
| Mouse | hover + press; cursor change | hover only with `(hover: hover) and (pointer: fine)` |
| Trackpad | like mouse; gestures have native momentum | two-finger swipe navigation must track 1:1 |
| Keyboard | focus-visible ring instantly; Enter/Space trigger press animation (no hover) | shortcuts skip or shorten entrance choreography |
| Stylus (Pencil, S Pen) | hover (Pencil hover on M2 iPad) as preview; pressure may drive scale | treat as precise pointer |
| Screen reader | no reliance on motion; state changes announced | motion must never be the only signal |

## 7. Haptics pairing

Haptics confirm **commits**, not motion: fire at the moment the state changes (a toggle flips, a
detent is reached, a drag crosses the delete threshold), not when the animation ends.

| Event | iOS | Android |
|---|---|---|
| Toggle / selection change | `.selection` / `UISelectionFeedbackGenerator` | `HapticFeedbackConstants.CLOCK_TICK` / `SEGMENT_TICK` (API 34) |
| Detent reached, snap | `.impact(.light)` | `CONFIRM` (light) |
| Threshold crossed (delete, refresh) | `.impact(.medium)` once, on crossing | `GESTURE_THRESHOLD_ACTIVATE` (API 34) |
| Success / error | `.notification(.success/.error)` | `CONFIRM` / `REJECT` |

Rules: one haptic per commit; never continuous haptics during a drag; respect the system haptics
setting (it's automatic on iOS; check `View.isHapticFeedbackEnabled` on Android).
