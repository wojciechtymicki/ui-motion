# iOS (SwiftUI, UIKit, Core Animation)

## Conventions

- **Springs are the default.** Since iOS 17, SwiftUI's default animation is a spring
  (`.smooth`: duration 0.5, bounce 0). System sheets, navigation and the keyboard all use
  critically damped or near-critically damped springs. Match that: ζ 0.9–1.0 for structural motion,
  `bounce` ≤ 0.15 for controls.
- **Everything is interruptible and additive.** SwiftUI animations retarget from the current
  presentation value and velocity automatically when state changes mid-flight. In UIKit, use
  `UIViewPropertyAnimator` (interruptible, scrubbable, reversible), not `UIView.animate` for gestures.
- **Navigation:** the push is a full-width slide from the right with parallax (−30%) on the outgoing
  view, plus the interactive edge-swipe back. Don't replace it without reason. iOS 18 adds
  `.navigationTransition(.zoom(sourceID:in:))` for card → detail.
- **Sheets:** `presentationDetents([.medium, .large])` with system springs and velocity. Custom sheets
  must carry release velocity (`DragGesture.Value.velocity` on iOS 17+).
- **Haptics:** pair commits with `UIImpactFeedbackGenerator(style: .light)` or `.sensoryFeedback(.impact, trigger:)`
  (iOS 17). Selection changes use `.selection`. Success and error use `.notification`. Fire them on the
  state change, not at the end of the animation. `prepare()` generators before use.
- **ProMotion (120Hz):** Core Animation runs at up to 120Hz for animations it drives. Custom
  `CADisplayLink` code must set `preferredFrameRateRange = CAFrameRateRange(minimum: 80, maximum: 120, preferred: 120)`
  and add `CADisableMinimumFrameDurationOnPhone = YES` to Info.plist, or it's capped at 60.
- **Reduce Motion:** `@Environment(\.accessibilityReduceMotion)` /
  `UIAccessibility.isReduceMotionEnabled`. Replace travel, zoom and parallax with crossfades, and keep
  feedback. Also respect `accessibilityPrefersCrossFadeTransitions`.

## Patterns

```swift
// Spring with explicit physics (mass 1): matches motion-spec values.
withAnimation(.interpolatingSpring(mass: 1, stiffness: 400, damping: 38, initialVelocity: v)) { y = target }

// Perceptual API (iOS 17): response = 2π/√k, bounce = 1 − ζ
withAnimation(.spring(duration: 0.31, bounce: 0.05)) { open.toggle() }

// Staggered appearance
ForEach(Array(items.enumerated()), id: \.element.id) { i, item in
  Row(item).opacity(shown ? 1 : 0).offset(y: shown ? 0 : 14)
    .animation(.spring(response: 0.39, dampingFraction: 1).delay(min(Double(i) * 0.05, 0.25)), value: shown)
}

// Phase and keyframe animators (iOS 17) for multi-step sequences
.keyframeAnimator(initialValue: Values(), trigger: tap) { view, v in view.scaleEffect(v.scale).offset(y: v.y) } keyframes: { _ in
  KeyframeTrack(\.scale) { SpringKeyframe(0.96, duration: 0.08); SpringKeyframe(1.0, spring: .init(response: 0.21, dampingRatio: 0.83)) }
}
```

UIKit gesture-driven:
```swift
let animator = UIViewPropertyAnimator(duration: 0, timingParameters:
  UISpringTimingParameters(mass: 1, stiffness: 400, damping: 38, initialVelocity: CGVector(dx: 0, dy: v / remaining)))
animator.addAnimations { sheet.frame.origin.y = target }
animator.startAnimation()
```

## Exposing seek for review

- **UIViewPropertyAnimator:** `animator.pauseAnimation(); animator.fractionComplete = t / duration`.
  Springs are scrubbable this way (fraction of the spring's settling time).
- **Core Animation:** set `layer.speed = 0` and `layer.timeOffset = t` on the container layer. Every
  sublayer animation is then frozen at t. This is the most reliable frame-accurate capture method.
- **SwiftUI:** make the view a pure function of a `t: Double` parameter, computing values with the same
  closed-form spring as `motion-runtime.js` (port `spring()`: it's 20 lines). Drive it from a slider in
  a `#Preview` for review, and from `TimelineView(.animation)` in production when it's a rendered-style
  piece. For state-driven UI, review the seek(t) web twin and trust SwiftUI's spring with identical
  constants.
- Capture frames with `ImageRenderer` (SwiftUI) per t, or a UI test that sets `timeOffset` and
  screenshots.

### Verifying a port against the review source

Keep the SwiftUI view a pure function of `t` and port the springs with
`templates/native/MotionSpring.swift` (the closed-form spring from `motion-runtime.js`, so the values
are identical). Then render native frames on macOS with `templates/native/render_frames.swift`
(ImageRenderer), and put them next to `contact_sheet.py --times` frames of the seek(t) page at the same
timestamps. Typecheck for iOS with
`xcrun -sdk iphonesimulator swiftc -typecheck -target arm64-apple-ios18.0-simulator -swift-version 5 *.swift`.
In practice this catches porting slips the eye misses, e.g. a `NumberFormatter` using the device
locale ("$1.450" instead of "$1,450"). Pin formatters to the spec's locale.

## Performance

Watch for offscreen passes (shadows without `shadowPath`, masks, `cornerRadius` with
`masksToBounds` on many layers), and for `drawingGroup()` being needed for complex vector
composition. Profile with Instruments → Animation Hitches and Core Animation (see `testing.md`).
