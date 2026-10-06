# React Native (Reanimated, Gesture Handler)

## Rules

- **Animate on the UI thread** with Reanimated (`useSharedValue`, `useAnimatedStyle`, `withSpring`,
  `withTiming`). Never animate by `setState` on the JS thread: any JS work (renders, network parsing)
  drops frames.
- **Gestures** via `react-native-gesture-handler` (`Gesture.Pan()` etc.). Their callbacks are
  **worklets** running on the UI thread, so drag stays 1:1 even when JS is busy.
- **Worklet rules:** functions called from worklets must be worklets (`'worklet'` directive, or
  auto-workletized in Reanimated 3+ when defined inline). Call JS from worklets with
  `runOnJS(fn)(args)` (navigation, analytics). Shared values are read via `.value` and must not be
  read in render.
- **Layout animations:** `entering={FadeInDown.springify().stiffness(260).damping(32)}`,
  `exiting={FadeOut.duration(140)}`, `layout={LinearTransition.springify()}` for reorder.
- **Shared element transitions:** Reanimated `sharedTransitionTag` (experimental), or
  react-navigation's native-stack transitions. Verify on both platforms.
- **Platform feel:** respect the platform differences above (iOS push vs Material shared axis), so use
  native-stack for navigation.

## Patterns

```tsx
const y = useSharedValue(hiddenY);
const pan = Gesture.Pan()
  .onChange(e => { y.value = clamp(y.value + e.changeY, topY, hiddenY + rubber(...)); })
  .onEnd(e => {
    const target = pickDetent(y.value + e.velocityY * 0.2);
    y.value = withSpring(target, { stiffness: 400, damping: 38, mass: 1, velocity: e.velocityY });
  });
const style = useAnimatedStyle(() => ({ transform: [{ translateY: y.value }] }));
```

Reanimated's `velocity` is in px/s (not normalized). It handles the units internally.

Reduced motion: `useReducedMotion()` from Reanimated, or `ReduceMotion.System` on animation configs
(`withSpring(v, { reduceMotion: ReduceMotion.System })`), which makes the animation jump to its end
when the OS setting is on. Supply an explicit crossfade alternative where travel carried meaning.

## Exposing seek for review

Make the animated values pure functions of a shared `t` value:
`const t = useSharedValue(0); const style = useAnimatedStyle(() => ({ opacity: interpolate(t.value, [0.1, 0.3], [0, 1], Extrapolation.CLAMP) }))`.
A dev-only slider writes `t.value`. For the seek(t) web twin, port the same functions. Springs used in
reviewed sequences should be computed from the closed-form `spring(t)` (port it as a worklet), so the
RN build and the web review match frame for frame.

## Performance

Check the UI-thread FPS in the Perf Monitor (JS FPS and UI FPS separately). Avoid heavy
`useAnimatedStyle` objects on hundreds of items. Use `FlashList` for long lists. On Android, test with
the new architecture (Fabric) and Hermes, since jank profiles differ.
