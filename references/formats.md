# Formats

Format is decided, not asked. Decide from these criteria in order, and write the result plus a
one-line reason into the spec.

## Decision criteria

1. **Interactive or state-driven?** If it reacts to input or app state → runtime code (CSS/WAAPI,
   Motion, SwiftUI, Compose, Reanimated) or Rive. Never a video.
2. **Who implements it?** If engineers will rebuild it, deliver code in their stack plus the spec. If it
   is dropped in as an asset, use Lottie, Rive or video.
3. **Needs alpha** (composited over varying backgrounds)? → vector (Lottie or Rive) or an alpha video
   (WebM VP9 + HEVC alpha pair).
4. **Recolouring or theming at runtime** (dark mode, brand variants)? → code, Lottie (with colour
   slots or dynamic properties) or Rive. Never video.
5. **Visual complexity:** photographic or 3D content, heavy blur or particles → video. Flat vector →
   code, Lottie or Rive.
6. **File size and performance budget** (see the table).
7. **Target stack constraints:** email (GIF or static only), App Store and Play previews (MP4/MOV
   only), social (MP4), web hero (code, or WebM + MP4 with a poster).

## Options and trade-offs

| Format | Strengths | Weaknesses | Typical size | Use for |
|---|---|---|---|---|
| **CSS transitions / keyframes** | Zero dependency, compositor-run (transform/opacity), declarative | No springs (use `linear()` easing to approximate), weak sequencing, no velocity | 0 KB | Hover, press, simple state changes on the web |
| **WAAPI** | Native, scrubbable (`currentTime`), sequenceable, compositor-run | Verbose; no springs natively | 0 KB | Web micro-interactions needing control |
| **CSS `linear()` easing** | Spring curves sampled into CSS (all modern browsers 2024+) | Fixed duration, no velocity handoff | 0 KB | Spring *look* for non-interactive web motion |
| **Motion (motion.dev)** | Real springs with velocity, layout/shared animations, gestures, small `animate()` core | Bundle cost (≈ 5 KB `animate`, ≈ 30+ KB React `motion` with layout features) | 5–35 KB | React/web product UI with gestures and layout changes |
| **GSAP** | Best timeline and sequencing, ScrollTrigger, SVG morph plugins, robust | Imperative, 25+ KB, springs need plugins/custom eases | 25–60 KB | Marketing sites, complex scroll stories, explainers on the web |
| **View Transitions API** | Shared-element and page transitions with near-zero code | Same-document: Chromium + Safari 18; cross-document is newer; limited per-element control | 0 KB | Web navigation and state-swap transitions |
| **SwiftUI** | Native springs, `matchedGeometryEffect`, interruptible by default | iOS-version-gated APIs | n/a | iOS/macOS product UI |
| **UIKit / Core Animation** | Full control, `UIViewPropertyAnimator` (scrubbable, interruptible) | More code | n/a | Complex iOS gestures and custom transitions |
| **Jetpack Compose** | `Animatable`, springs, `SharedTransitionLayout`, `AnimatedContent` | Recomposition cost if misused | n/a | Android product UI |
| **React Native Reanimated** | UI-thread worklets, gesture-handler integration, springs with velocity | Setup and worklet rules | ~ | RN apps (never animate via JS-thread `setState`) |
| **Lottie** | Vector, small, designers author it in After Effects, recolourable via dynamic properties | No interactivity beyond segment playback; expression and effect support varies by platform; complex masks are slow | 10–150 KB JSON (dotLottie compresses about 70%) | Icons, illustrations, loaders, empty states, success moments |
| **Rive** | Vector, state machines with inputs, runtime-interactive, tiny files, mesh deformation | Its own editor; runtime ≈ 150 KB+ (WASM on web) | 5–80 KB | Interactive illustrations, character/mascot, animated buttons with many states |
| **MP4 / H.264** | Universal playback, hardware decode everywhere | No alpha; banding on gradients (use CRF ≤ 18, add grain/dither); not recolourable | 0.3–2 MB per 10s @1080p for UI content | Explainers, social, App Store previews, marketing |
| **WebM / VP9 with alpha** | Alpha in Chrome, Firefox and Edge | No Safari alpha | ≈ H.264 size | Alpha video on the web (pair with HEVC alpha) |
| **HEVC with alpha (.mov)** | Alpha in Safari and Apple platforms, hardware decode | Encoding on macOS (VideoToolbox) only | ≈ 1.3× VP9 | The Safari half of alpha video |
| **ProRes 4444** | Lossless-ish master with alpha for editors | Huge | 50–200 MB per 10s | Hand-off to video editors / After Effects |
| **APNG** | Alpha, lossless, plays as `<img>` in all modern browsers | Large for long or large animations | 0.2–3 MB | Short alpha loops where video isn't possible (email clients excluded) |
| **GIF** | Plays everywhere, including email | 256 colours, 1-bit alpha, delays in 10ms steps (≤ 50fps; browsers clamp ≤ 10ms to 100ms), big | 0.5–5 MB | Email, docs, tickets. Never in product |
| **PNG sequence** | Lossless frames with alpha | Not a delivery format | n/a | Intermediate for editors, sprite sheets, game engines |

## Defaults by deliverable

| Deliverable | Default | Why |
|---|---|---|
| Web micro-interaction | CSS/WAAPI (+ `linear()` spring) | No dependency; compositor-run |
| Web product UI with gestures or layout animation | Motion | Springs with velocity plus layout animations |
| iOS / Android UI | SwiftUI / Compose | Native interruptibility and accessibility settings |
| Animated icon in-app | Lottie (or code for 2–3 path icons) | Small, recolourable, designer-editable |
| Multi-state interactive illustration or button | Rive | State machine runs at runtime |
| Logo sting for app/web | Lottie + MP4/WebM pair | In-app vector plus marketing video |
| Explainer / store preview | MP4 H.264 (+ HEVC) at the platform spec | Universal; required by stores |
| Alpha overlay on the web | WebM VP9 alpha + HEVC alpha `<source>` pair | Covers Chrome/Firefox + Safari |
| Email | GIF ≤ 1 MB, or a static poster | Only thing that plays |

Alpha video markup (order matters):

```html
<video autoplay muted loop playsinline poster="poster.png">
  <source src="anim.mov" type='video/quicktime; codecs="hvc1"'>   <!-- Safari: HEVC alpha -->
  <source src="anim.webm" type="video/webm">                       <!-- Chrome/Firefox: VP9 alpha -->
</video>
```

## Size and performance budgets

- Lottie: ≤ 150 KB JSON, ≤ 30 layers, no "merge paths" on mobile, avoid mattes over large areas and
  Gaussian blur effects (not supported or very slow on mobile renderers). Prefer dotLottie.
- Rive: ≤ 100 KB per file. Keep bones/meshes modest on low-end Android.
- Video for UI: CRF 16–20 (H.264), 30 or 60fps matching the motion (60 for fast UI motion; 30 halves
  size and is fine for slow explainers), `+faststart`, poster always.
- GIF: keep it under 1 MB. Reduce size, frame rate (25 → 15fps), or colours before reducing duration.

`render.py` produces all video and image formats here. Lottie and Rive are authored separately (see
`platforms/lottie-rive.md`). The seek(t) page remains the source of truth for timing.
