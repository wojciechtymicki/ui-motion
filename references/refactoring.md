# Refactoring

After the motion is approved and tested, refactor the shipping code to this standard. Then re-run the
tests: refactoring must not change a single frame (`render.py` PNG hashes before and after, for
rendered pieces; `jank_check` and spec-match frames for runtime pieces).

## 1. All values from tokens: no magic numbers

Durations, curves, springs, distances and staggers live in one motion token module, named by role:

```ts
// motion.tokens.ts. Implements motion-spec.md §7 (Tokens)
export const spring = {
  press:  { stiffness: 900, damping: 50, mass: 1 },
  sheet:  { stiffness: 400, damping: 38, mass: 1 },
  smooth: { stiffness: 260, damping: 32, mass: 1 },
} as const;
export const ease = {
  enter: [0.16, 1, 0.3, 1], exit: [0.55, 0, 1, 0.45], move: [0.65, 0, 0.35, 1],
} as const;
export const duration = { exitShort: 0.14, fade: 0.2, enter: 0.34 } as const;
export const stagger = { list: 0.05, listCap: 0.25 } as const;
export const distance = { rise: 16, push: 24 } as const;
```

Native equivalents: a `Motion` enum with static `Animation` values (SwiftUI), and a `MotionTokens`
object of `AnimationSpec`s (Compose). If the product has design tokens (Figma variables, Style
Dictionary), add motion there and generate per platform.

`lint_motion.js` flags numeric literals in `transition`/`animate` calls outside the token module.

## 2. Clean up on unmount

- Cancel running animations (`animation.cancel()`, `controls.stop()`, `animator.stopAnimation(true)`,
  coroutine scope cancellation).
- Remove listeners (`pointermove`, `scroll`, `resize`, `matchMedia` change, IntersectionObserver).
- Cancel rAF loops, and pause Lottie/Rive/video when hidden or unmounted (`destroy()`).
- Reset `will-change` after animations finish.

## 3. Centralised reduced-motion logic

One source of truth (`useReducedMotion()` hook / `MotionPreferences` object / environment value).
Components ask *which variant to play*, never re-implement the media query:

```ts
const variant = useMotionVariant();   // "full" | "reduced"
const t = transitions.sheet[variant]; // both defined in tokens
```

## 4. Motion separated from layout

Layout (positions, sizes, flex/grid) is static CSS or layout code. Motion is applied as transforms on
top. Components don't compute layout inside animation callbacks. FLIP measures layout, and motion
only interpolates the delta.

## 5. No iteration leftovers

Remove: debug overlays, `console.log` in animation loops, unused keyframes, commented-out old curves,
`?t=`/`?reduced=` dev params in production paths, the seek(t) demo-timeline code (it belongs to the
review page only), and slow-motion multipliers.

## 6. Typed where possible

Token objects are `as const`. Spring configs have a type. Animation state is a union type
(`"idle" | "hover" | "pressed" | "loading" | "success" | "error"`), so missing transitions surface at
compile time.

## 7. Library bundle cost reported

In the handoff notes, list each motion library added and its cost, e.g. "Motion `animate` 5.1 KB gz",
"motion/react with layout 34 KB gz", "lottie-web light 52 KB gz", "Rive web runtime 160 KB (WASM)".
Prefer the smallest entry point (Motion's `animate` / `mini`, `lottie_light`).

## 8. Names match Figma layers

Component, element and token names follow the Figma layer and variable names
(`OnboardingCard/Title` → `onboardingCardTitle`), so designers and engineers can trace a moving
element from the spec to the file to the code.

## 9. Header comment naming the spec

Every file that implements motion starts with:

```ts
/**
 * Implements motion-spec.md: onboarding-2 v4 (§2 rows 1–9, §4 interruption, §6 reduced).
 * Review: python scripts/serve.py work/onboarding-2  (player)
 */
```

## Refactor checklist

- [ ] Tokens only; lint passes
- [ ] Unmount cleanup verified (mount/unmount 20× in a test: no leaks, no warnings)
- [ ] Reduced motion via the central hook
- [ ] Layout and motion separated
- [ ] No leftovers
- [ ] Types for tokens and states
- [ ] Bundle cost reported
- [ ] Names match Figma
- [ ] Header comments present
- [ ] Tests re-run and identical (frame hashes / spec-match frames)
