# Android (Jetpack Compose, Views)

## Conventions (Material 3 motion)

- **Easing and duration tokens:** emphasized (`0.2, 0, 0, 1`) for most transitions,
  emphasized decelerate (`0.05, 0.7, 0.1, 1`) for entering, emphasized accelerate
  (`0.3, 0, 0.8, 0.15`) for exiting. Durations: short1–4 = 50–200ms, medium1–4 = 250–400ms,
  long1–4 = 450–600ms. Material 3 Expressive (2025) moves to **spring tokens**: spatial springs
  (`fast` ≈ stiffness 1400 / ζ 0.9, `default` ≈ 700 / 0.9, `slow` ≈ 300 / 0.9) and effects springs
  (ζ 1, for colour and opacity). Prefer springs for new work.
- **Transition patterns:** container transform (shared element), shared axis (x/y/z, for related
  screens), fade through (for unrelated peers), fade (for dialogs and menus in place).
- **Predictive back** (Android 14+, required behaviour on 15+ targets): the back gesture previews the
  destination. The current screen scales down to about 90%, shifts with the gesture and rounds its
  corners. Commit on release past the threshold. Implement with `PredictiveBackHandler` in Compose, or
  use Navigation's built-in support. Custom transitions must follow the gesture progress.
- **Haptics:** `HapticFeedbackType.LongPress` / `TextHandleMove` in Compose, and
  `View.performHapticFeedback(HapticFeedbackConstants.CONFIRM / REJECT / CLOCK_TICK)` (API 30+).
- **"Remove animations"** (Settings → Accessibility) sets the animator duration scale to 0. Compose
  animations then jump to their end values. Infinite animations stop. Make sure end states are
  correct without motion, and test with `adb shell settings put global animator_duration_scale 0`.
  Read it via `Settings.Global.ANIMATOR_DURATION_SCALE` when you need a custom reduced version.
- **Refresh rates:** many devices run at 90/120Hz adaptively. Compose's frame clock follows the
  display. Don't hardcode 16ms anywhere.

## Patterns (Compose)

```kotlin
// Spring matching the spec (mass 1): stiffness = k, dampingRatio = ζ
val y by animateFloatAsState(if (open) 0f else hiddenY, spring(dampingRatio = 0.95f, stiffness = 400f), label = "sheet")

// Gesture with velocity handoff
val offset = remember { Animatable(0f) }
Modifier.pointerInput(Unit) {
  val tracker = VelocityTracker()
  detectVerticalDragGestures(
    onVerticalDrag = { change, dy -> tracker.addPosition(change.uptimeMillis, change.position); launch { offset.snapTo(offset.value + dy) } },
    onDragEnd = { val v = tracker.calculateVelocity().y; launch { offset.animateTo(target(offset.value, v), spring(0.95f, 400f), initialVelocity = v) } })
}

// Content swap with size change
AnimatedContent(state, transitionSpec = {
  (fadeIn(tween(220, 90)) + slideInVertically { it / 4 }) togetherWith fadeOut(tween(90)) using SizeTransform(clip = false)
})

// Read animated values in the draw/layer phase to skip recomposition
Modifier.graphicsLayer { translationY = offset.value; alpha = a.value }
```

Views: `SpringAnimation(view, DynamicAnimation.TRANSLATION_Y).setSpring(SpringForce(target).setStiffness(400f).setDampingRatio(0.95f)).setStartVelocity(v).start()`.

## Exposing seek for review

- **Compose:** `Transition` objects can be seeked. `rememberTransition(SeekableTransitionState(...))`
  with `seekTo(fraction)` (Compose 1.7+). For bespoke pieces, compute values from `t` with a ported
  closed-form `spring()` and drive the composable from a `t` parameter. Preview it with a slider
  (`@Preview` plus interactive mode), and render frames with Paparazzi or Roborazzi screenshot tests
  per t.
- **Compose test clock:** `composeTestRule.mainClock.autoAdvance = false; mainClock.advanceTimeBy(ms)`
  gives frame-accurate captures of real animations in tests.
- **AnimatedVectorDrawable:** `seekTo` is not public. Review the AVD via its Lottie or seek(t) twin, or
  record it on device.

## Performance

Avoid reading animated state in composition (it recomposes every frame), so read it in
`graphicsLayer {}` / `drawBehind {}` lambdas. Use `Modifier.offset { IntOffset(...) }` (lambda form),
not `offset(x.dp)`. Profile with Macrobenchmark `FrameTimingMetric` and Perfetto (see `testing.md`).
