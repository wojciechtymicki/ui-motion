# Domain notes

These notes cover only what the motion profile and `principles.md` can't derive on their own. Read the
section for the piece's domain before writing the spec.

## UI motion (screen transitions, sheets, navigation, overlays)

- Follow the platform's navigation grammar unless the brief overrides it. iOS push: the new screen
  slides from the right edge (100% → 0) while the old one moves −30% and dims, with an interactive
  edge-swipe back. Android: Material shared axis (x: 30px slide plus fade) or fade-through for
  peers, and predictive back (Android 14+) shrinks and moves the current screen with the gesture. Web:
  View Transitions, a crossfade with a 16–24px shared-axis slide.
- Overlays emerge from their trigger. A menu scales from 0.95 at the trigger-side corner. A popover's
  arrow stays attached. A sheet comes from its resting edge. A modal without a trigger (system alert)
  fades plus scales from 0.96 at the centre.
- The scrim fades with the overlay (opacity 0 → 0.4–0.5 for modal, 0.2–0.3 for sheets), on the same
  curve, and slightly shorter.
- Navigation is interruptible: a second tap mid-transition retargets from the current state. Never
  queue transitions.

## Micro-interactions

- Feedback starts on **touch-down** (pointerdown or `isPressed`), within 1 frame. The result of the
  action can come later; the acknowledgement can't.
- The **final frame must read as the state**. If a toggle's motion is skipped (reduced motion, a
  background tab), the end state alone must be unambiguous.
- Keep them under 300ms of visible motion, with no overshoot over 2%, except rare success moments.

## Interaction response (click, hover, drag)

- Hover effects only on devices that hover: `@media (hover: hover) and (pointer: fine)`. On touch,
  hover styles stick after a tap. iPadOS pointer: use native hover effects (`.hoverEffect`).
- Hover in about 120–180ms, hover out about 200–250ms (leaving slower prevents flicker when the cursor
  grazes an edge).
- Drag is 1:1 with the finger: no easing, no lag, no spring *while* dragging (a spring follow is for
  cursor parallax, not direct manipulation). Momentum is preserved on release (`techniques.md` §10).
- Drag thresholds: start after 6–10px (touch) or 3–4px (mouse), so taps aren't stolen.

## Animated buttons

- Design the **full state set**: idle, hover, focus-visible, pressed, loading, success, error,
  disabled. Every pair that can follow each other has a defined transition. Missing transitions
  snap.
- Labels morph without layout jumps (`techniques.md` §4). The loading state **keeps the button's width
  and height**: the spinner replaces the label in place.
- Success: a check draws on (§5) over 300ms, holds ≥ 900ms, then returns to idle or advances the flow.
  Error: a horizontal shake ±6px, 3 cycles over 300ms (a decaying sine), plus a colour change. Never
  shake alone (inaccessible), and pair it with a message.
- Disabled → enabled: a 150ms opacity and colour change, no motion.
- Focus ring: appears instantly (no fade) for keyboard users. It may scale from 1.04 → 1 over 120ms.

## Animated icons

- They must read at **24px** (and 16px if they're used there). Check every frame of the contact sheet
  at 1× size. Mid-state shapes that only make sense at 96px are wrong.
- The **final frame matches the static icon exactly**. Overlay the static SVG; the diff must be zero.
- Use 150–400ms. Stroke icons keep stroke width constant (`vector-effect` or `scale` compensation).
- State icons (play/pause, menu/close, like/liked) are reversible: the reverse uses the same path,
  with an `in` curve at 75% of the duration.

## Animated logos

- The final frame **matches the static mark exactly**: same geometry, colour and position, at any
  render size. Verify with a pixel diff at the export size.
- No distortion: uniform scale only, no squash on the mark itself. Respect clear space at every frame.
- Ship three cuts: **sting** (0.8–1.6s), **full reveal** (2–3s), **idle** (seamless loop, 4–8s,
  calm), plus a poster frame equal to the final mark.
- Brand colours only. Motion character must fit the brand's voice: a bank mark doesn't bounce.

## Typography motion

- Text is readable at every frame: masks, translation and fill crossfades. No blur or scale on body
  text (`principles.md` rule 11).
- **Line breaks are fixed before animating**: split after fonts load, lock widths, and never let a
  word-wrap change mid-animation.
- Reading time: hold each line ≥ 0.3s + 0.06s per word after it lands, before the next beat.
- Kinetic type for marketing can go bigger (per-letter, axis animation), but the final composition
  must still be good typography (kerning, rag).

## Looped illustrations

- Integer cycles. Seamless in position and velocity (`techniques.md` §18; verify with `loop_check.py`).
- Calm amplitude: ambient loops move ≤ 2–4% of their size and have periods of 2–6s. Several
  elements with different integer cycle counts give an organic feel.
- **Pausable if longer than 5s** (WCAG 2.2.2): a visible pause control, or it stops after 5s, or it
  runs only while hovered or in view.
- Off-screen loops stop (IntersectionObserver, `onDisappear`, lifecycle).

## Data visualization

- **Never misrepresent values mid-motion.** Interpolate in data space and animate axes with the data.
  No overshoot on bars or lines: an overshooting bar shows a false value. Use critically damped
  springs or `standard`.
- Data points keep **identity** across states (keyed joins). Points that appear and disappear do so
  in place (grow from the baseline, collapse to it), not by flying across the chart.
- No scale distortion: log/linear switches are cuts or crossfades, not morphs.
- Sequential reveals (draw-in) follow the data's reading direction (time left → right).

## Loading and progress

- **Skeletons match the final layout** (block sizes, counts, radii). See §15.
- **Minimum display time:** don't show any loading UI for loads under about 200ms. Once shown, keep it
  ≥ 300–500ms, so fast loads don't flash.
- Indeterminate: calm loops (spinner 1.2–1.4s per turn, linear rotation and eased arc).
  Determinate: **honest progress**. Never fake speed-ups that then stall at 99%. If progress is
  unknown, use indeterminate.
- Long waits (> 4s): add a status line that changes meaningfully, not a faster spinner.

## Splash screens

- **Never delay launch.** The splash animation runs while the app loads, never after it's ready.
  iOS: the launch screen is static by OS rule; motion starts in the first app frame that matches it
  exactly. Android 12+: `SplashScreen` API with an animated vector drawable (≤ 1000ms) and
  `setOnExitAnimationListener` for the handoff.
- **Seamless handoff into the first screen:** the last splash frame equals the first app frame (the
  logo moves into the nav bar, or fades as content enters underneath).
- Repeat launches: shorter or skipped (e.g. the full sting only on cold start after install).

## Onboarding

- **Progress follows the swipe**: page content, illustrations and the indicator track the finger 1:1.
  Auto-advancing animations pause during a drag.
- Each screen **reads on its own** (someone might land mid-flow or skip). The illustration finishes
  its entrance within about 800ms, then holds or loops calmly.
- Illustration parallax at 0.3–0.6× the page swipe gives depth (disable under reduced motion).
- The final CTA appears last and gets the one expressive spring of the flow.

## Feature explainers

- **The real UI rebuilt in code** (HTML/CSS or native), not a screen recording: it stays crisp at
  every size, can be retimed, and matches the shipping product. Use real tokens from Figma.
- **Readable muted** (most autoplay is muted): captions or on-UI callouts, every action's result
  visible ≥ 600ms, and cursor choreography per §19.
- Pacing: one idea per 3–5s. Total 15–30s for in-product explainers.
- **App Store previews:** 15–30s, H.264 or HEVC, ≤ 500MB, 30fps, at the exact device resolution
  required (e.g. 886×1920 portrait for 6.9" iPhone previews). Captured in-app footage only, no device
  frames or hands. The poster frame is selectable (default about 5s in), so make frame 0 and 5s strong.
  **Google Play:** a YouTube video link (landscape recommended, 30s–2min, no ads), plus
  feature-graphic rules for the static. Check current specs before rendering: they change.
