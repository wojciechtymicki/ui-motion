# Lottie and Rive

## When to use which

- **Lottie:** linear, timeline-based vector animation (icons, illustrations, loaders, success
  moments, logo stings in-app). Authored in After Effects (Bodymovin) or Figma plugins and editors
  (LottieFiles, Jitter, Haiku). Runtime control is limited to play, segments, speed, direction and
  dynamic colour properties.
- **Rive:** interactive or state-driven vector (buttons with 6 states, mascots reacting to input, toggles,
  progress tied to data). Its state machine, inputs (boolean, number, trigger) and listeners run at
  runtime. The editor is Rive's own.

## Lottie rules

- **Keep it renderer-safe:** avoid expressions (unsupported on mobile renderers), layer effects (Gaussian
  blur, glow, drop shadow: partially or not supported), "merge paths" (slow on iOS and Android, off by
  default), large mattes and masks (memory, offscreen), and 3D layers. Pre-compose sparingly.
- **Text:** convert to shapes unless it's dynamic, and ship the font if it is.
- **Size:** aim ≤ 150 KB JSON. Use **dotLottie** (`.lottie`, zipped, ≈ 70% smaller, can hold themes and
  state machines in newer runtimes). Remove hidden layers and unused assets.
- **Springs:** Lottie has no physics. Bake the closed-form spring: sample `Motion.spring()` at the
  export fps and write keyframes. Or approximate with `backOut` on 2 keyframes plus a small settle
  keyframe.
- **Colours:** name layers and expose them through dynamic properties (`KeyPath`) or slots, so dark
  mode and themes don't need new files.
- **Frame rate:** author at 60fps for UI micro-motion (30fps looks steppy on 120Hz screens for fast
  moves). The JSON size impact is small.
- **Segments:** one file can hold several states (e.g. 0–30 idle, 30–60 press, 60–120 success). Play
  them with `playSegments([30, 60], true)`, so the transitions between them are designed.

Runtime APIs: web `lottie-web` / `@lottiefiles/dotlottie-web`, iOS `lottie-ios` (`LottieView` in
SwiftUI), Android `lottie-android` / `lottie-compose`, React Native `lottie-react-native`.

## Rive rules

- Design the **state machine first**: states, inputs, transitions with their own durations and blend.
  Each transition has an exit time (or none, for interruptible) and an interpolation curve.
- Use **inputs** for everything the app controls (`isLoading` boolean, `progress` number 0–100,
  `success` trigger). Use **listeners** for pointer events inside the artboard (hover and press on
  parts).
- Layouts and data binding (newer runtimes) let text and colours come from the app. Prefer them over
  baked variants.
- Size: ≤ 100 KB file. The runtime is ≈ 150–200 KB (web WASM), so factor it in on the web.
- Rive doesn't do physics springs either. Bake the curve into keyframes, or drive a number input from
  app code that computes the spring.

## Exposing seek for review

- **Lottie:** `anim.goToAndStop(t * 1000, false)` (ms) or `goToAndStop(frame, true)`, with the
  frame = `Math.floor(t * fps + 1e-6)`, using the file's own fps (`anim.frameRate`). In the
  seek(t) page:
  ```js
  const anim = lottie.loadAnimation({ container, renderer: "svg", loop: false, autoplay: false, path: "anim.json" });
  const ready = new Promise(r => anim.addEventListener("DOMLoaded", r));
  Motion.register({ name, version, duration: anim.totalFrames / anim.frameRate, fps: 60, width, height,
    ready, seek: t => anim.goToAndStop(t * 1000, false) });
  ```
  Use the **svg** renderer for review and capture (deterministic). Canvas is faster at runtime.
- **Rive:** the runtime advances by elapsed seconds. For scrubbing a timeline animation, use
  `rive.pause()` and `rive.scrub("AnimationName", t)` (web runtime). For state machines, script inputs
  as a demo timeline (`Motion.demoState`), reset the instance, and advance in fixed steps of 1/fps up
  to t (deterministic, if slower for late timestamps).

## Converting from the seek(t) source

When the reviewed source is a seek(t) page and the deliverable is Lottie or Rive: rebuild the layers
in the tool using the spec's timing table (start, duration, curve as cubic-bezier, springs baked), then
load the export into a seek(t) page (above) and run `contact_sheet.py` on both at the same times.
Compare side by side, and iterate until the frames match.
