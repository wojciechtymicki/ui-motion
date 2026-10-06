# Desktop (macOS, Windows, Electron/Tauri, desktop web)

## Conventions

- **Pointer precision and hover:** desktop has hover, right-click, scroll wheels and trackpads with
  inertia. Hover feedback is expected on every interactive element (120–180ms in, 200ms out).
  Magnetic or tilt effects only on hero CTAs (`techniques.md` §13).
- **Larger distances, same visual angle:** windows are big, but users sit farther away. Keep durations
  about 1.2× mobile for the same *relative* travel, and cap them. Avoid full-window slides. Desktop
  favours fades, scale 0.98 → 1, and short (8–16px) shared-axis movement.
- **Keyboard-first users:** focus changes animate instantly or in ≤ 100ms. Keyboard shortcuts that
  open UI should feel instantaneous (skip entrance choreography when triggered by keyboard, or
  halve it).
- **macOS:** native windows and sheets use springs. `NSAnimationContext` with
  `allowsImplicitAnimation`, or Core Animation. SwiftUI on macOS has the same APIs as iOS. Respect
  System Settings → Accessibility → Display → Reduce motion (`NSWorkspace.shared.accessibilityDisplayShouldReduceMotion`).
  Trackpad gestures (swipe between pages) must track 1:1 with momentum.
- **Windows (WinUI 3):** Fluent motion: `Microsoft.UI.Composition` springs
  (`SpringVector3NaturalMotionAnimation`, `DampingRatio`, `Period`). Connected animations
  (`ConnectedAnimationService`) for shared elements. The entrance curve is a fast-out decelerate
  `cubic-bezier(0, 0, 0, 1)` (about 300ms for page entrance). The respect setting is "Animation effects"
  (`UISettings.AnimationsEnabled`).
- **Electron / Tauri:** web rules apply, plus:
  - Chromium respects the OS reduced-motion setting through `prefers-reduced-motion`.
  - Window-level animations (open/close) belong to the OS, so don't fake them inside the webview.
  - Variable refresh rates (120–240Hz monitors): rAF runs at the display rate, so seek(t)-based code is
    already rate-independent. Never step animations per frame.
- **Multiple monitors at different DPI:** test at 1× and 2× (render scale changes sub-pixel snapping;
  text crispness at the end frame).

## Exposing seek for review

Same as web for Electron/Tauri. For native macOS, use the `layer.speed = 0; layer.timeOffset = t`
method (see `ios.md`). For WinUI, Composition animations can be controlled through `AnimationController`
(`Pause()`, then set `Progress`).
