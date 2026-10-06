# Principles

Read this before deciding any timing. Part A is the rule set. Part B lists the habits that make
motion look generated, and what to do instead. When a rule and the brief conflict, the brief wins,
but log the conflict in the spec's **Decisions and assumptions** list.

---

## Part A: rules

### 1. Every motion has a job

There are four jobs: **orient** (where am I, where did that come from), **feedback** (the system heard
you), **focus** (look here now), **continuity** (this is the same thing, changed). If you can't name
the job in three words, cut the motion.

*Example:* a settings row that slides in on every screen visit has no job, so render it in place.
A row that slides in after "Add account" has a job (*orient: new item, here*): 16px rise, spring, once.

Write the job in the spec. During critique, every element in the timing table must point to one.

### 2. Spatial logic: nothing appears from nowhere

Elements arrive from their trigger or their logical origin, and leave toward their destination. A
menu grows from the button that opened it. A toast enters from the edge it docks to. A deleted item
collapses into its row's space. A sheet comes from the edge it rests on and returns there.

*Example:* a popover opened from a top-right avatar gets `transform-origin: top right` and scales
from 0.96 at that corner. Centre-origin scale on a corner-anchored popover makes it look detached
from its anchor.

The test is simple: freeze the first frame of an entrance. You should be able to point at where the
element is coming from.

### 3. Frequency rule: the more often it's seen, the faster and quieter it is

| Seen | Duration (tween) | Amplitude | Expression allowed |
|---|---|---|---|
| Constantly (hover, press, toggle, tab) | 80–180ms | 1–4px, scale 0.96–1.0 | none: pure feedback |
| Often (sheet, menu, list insert, nav push) | 200–350ms | full travel, no overshoot or ≤2% | minimal |
| Rarely (onboarding, empty → first item, success moment) | 350–700ms | bigger travel, choreography | some character, restrained overshoot |
| Once (splash, first-run hero, logo sting) | 600–2000ms | as the brief wants | the most, still with a job |

*Example:* a "copied" check that appears 40 times a day: 120ms opacity plus 2px rise, no bounce. The
same check as the final beat of an onboarding flow: 450ms stroke draw-on plus a lively spring scale
from 0.9.

### 4. Springs for anything the user touches

A direct-manipulation surface (drag, swipe, pinch, press-and-release, toggle, sheet, card) settles
with a spring. A spring can start from any position and any velocity, which is what makes interruption
and velocity handoff possible. A bezier always restarts at zero velocity.

Use restrained overshoot: ζ ≥ 0.8 by default (≤ 1.2% overshoot). Go to ζ 0.6–0.7 (about 5–9%)
only when the brief says playful, or for a success moment seen rarely. ζ < 0.5 is a toy, never
product UI.

*Example:* a toggle thumb uses `{stiffness: 700, damping: 48}` (ζ 0.91, settles in about 300ms). A
gamified streak badge, seen once a day, can use `{stiffness: 380, damping: 26}` (ζ 0.67, 6% overshoot).

### 5. Never linear, except for rotation, progress and marquees

Linear motion in UI looks like a machine with no mass. It is correct only where the motion represents a
constant-rate quantity: a spinner's rotation, determinate progress, a ticker or marquee, a time-based
scrubber, a parallax layer locked to scroll.

*Example:* a loading spinner arc rotates linearly at 1 turn per 1.1–1.4s, and its arc **length** eases
(in-out, about 1.4s period). That combination is what makes Material's spinner feel alive.

### 6. Exits are faster than entrances, and they accelerate out

An exit runs at about 60–75% of its entrance duration and uses an ease-in or accelerate curve. The
user already decided to dismiss it, so don't make them watch it leave. Entrances decelerate (ease-out)
because the eye needs to land on the content.

*Example:* a sheet enters in 340ms with `cubic-bezier(0.16, 1, 0.3, 1)` (or the `sheet` spring) and
exits in 220ms with `cubic-bezier(0.55, 0, 1, 0.45)`. A modal fades in over 200ms and out over 140ms.

### 7. The next element enters already moving

In a sequence, don't wait for the previous exit to finish. Start the next entrance while the exit is
at roughly 60–80% of its progress, travelling in the same direction, so the eye follows one continuous
motion. Two separate events with a gap read as a stutter.

*Example:* onboarding step 1 → 2. Step 1's content exits left over 220ms (accelerate). Step 2 starts at
t = 140ms, entering from +40px on the right with a decelerating spring. Their travel overlaps by 80ms
in the same direction.

### 8. One lead, followers, and a stagger cap

Every choreographed group has **one lead element** that starts first and travels farthest or
changes most. Followers move less and later. Cap the total stagger so the whole group lands within
roughly 400ms of the lead's start. Past that, the user waits for the list.

- Step: 30–60ms for small items, 60–90ms for large blocks.
- More than 6 items: cap the stagger (`stagger(i, step, cap)`) or stagger only the first 5–6 and bring
  the rest in together with the last one.
- Followers travel 50–75% of the lead's distance.

*Example:* a card (lead, 24px rise, `smooth` spring). Then the title words at 45ms steps, then 3 rows at
60ms steps capped at 200ms, then the CTA. Everything lands by about 620ms. See `work/demo-welcome`.

### 9. Shared elements, not crossfades between unrelated things

When something persists across a state change (thumbnail → detail image, chip → filter sheet, FAB →
compose screen), animate that object's frame (position, size, corner radius) from its old state to its
new one. Crossfading two unrelated layouts loses the thread. Keep one shape language: if the thumbnail
has 12px radii and the detail hero has 0, interpolate the radius. Don't swap it.

*Example:* a search field expanding into a full-screen search. The field's rounded rect morphs into
the top bar, the placeholder text crossfades its fill in place (no scaling), and results stagger in
below.

### 10. No dead frames mid-sequence

Inside a sequence, something should always be moving, even if it's only the tail of a spring settle. A
mid-sequence stall of 3+ identical frames reads as a hitch. Only the **final hold** is completely still.
For long holds in a rendered piece (explainers, splash), keep a micro-settle alive: 1–2px drift, a
0.5% scale breath, or a cursor idle wobble.

`jank_check.py` flags stalls ≥ 3 frames between the first and last moving frame.

### 11. Text is sharp at every frame

Never scale text that is blurred, and never animate `filter: blur` on text you expect people to read.
Text enters by **masking** (rise inside an overflow-clipped line), by **fill crossfade** in place, or by
**translation**. All of these keep glyphs on the pixel grid. If text must scale (a shared-element title
morph), keep the range within 0.9–1.1 and finish exactly at scale 1 with integer-pixel translation.

*Example:* a headline rises per word inside a mask: 110% → 0% translateY, 45ms stagger, ζ ≈ 0.92 spring.
Don't do opacity 0 → 1 plus scale 0.8 → 1 plus blur(8px) → 0. Every frame of that is unreadable.

### 12. Compositor-friendly properties only

Animate `transform` and `opacity`. Use `filter` only where it's cheap (small layers, no large blur
radii). Use `clip-path` only on simple shapes and small areas. Never animate `width`, `height`, `top`,
`left`, `margin`, `padding`, `font-size` or `box-shadow` blur on large elements: they trigger layout
or paint every frame. For size changes, use the FLIP technique: measure, invert with transform,
animate to identity. For shadows, crossfade a pre-rendered shadow layer's opacity.

### 13. Loops are seamless in position AND velocity

A loop of duration T must satisfy f(0) = f(T) and f'(0) = f'(T). Build loops from integer cycles of
periodic functions (`sin(2πnt/T)`), or from segments whose ends meet at zero velocity. A loop whose
position matches but whose velocity reverses has a visible kink once per cycle. `loop_check.py`
measures both. duration × fps must be an integer.

*Example:* a breathing dot. Use `scale = 1 + 0.04 * (1 - cos(2πt/T)) / 2` with T = 2.4s. Don't use a
tween 1 → 1.04 → 1 with ease-out on both halves: velocity is not zero at the turnarounds, so it
"bounces" off the ends.

### 14. Deterministic output

Animation code never calls `Math.random`, `Date.now`, `performance.now` or `setTimeout` to decide what
a frame looks like. Use `Motion.mulberry32(seed)` for organic variation, seeded once at load. Frames
must be identical across renders, devices and review sessions, or the player's timestamps mean nothing.

### 15. Restraint

Use one accent colour in motion, the product's. No gratuitous 3D flips, particles, glows, lens flares,
rainbow gradients, confetti or shimmer unless the brief explicitly asks. Quality comes from timing and
spacing, not from adding effects. When in doubt, remove the most decorative layer and see if anything
is lost.

### 16. The silent one-sentence test

Show the motion muted, once, to someone who hasn't seen the product. They should be able to say what
happened in one sentence ("the card slid up and the button appeared under it"). If they can't, the
choreography is too busy or the lead element isn't clear. Write this sentence in the spec before
building.

---

## Part B: default habits to override

These are the tendencies that make motion look AI-generated or template-made. Check every spec and
build against this list.

### Everything fading in together
**Why it reads cheap:** no hierarchy and no origin. The screen "loads" rather than arrives, and the eye
has nowhere to go first.
**Instead:** pick a lead. Give it travel (12–24px) and a spring. Followers come after it on a capped
stagger, with less travel. Elements that don't need to move render in place.

### 300ms ease-in-out on everything
**Why it reads cheap:** ease-in-out starts slowly, which reads as latency on every interaction, and a
single duration ignores frequency, distance and size.
**Instead:** entrances decelerate (ease-out or a spring). Exits accelerate. Durations scale with
frequency (rule 3) and distance: about 150ms per 100px of travel on mobile, capped at about 450ms for
full-screen moves. Ease-in-out is for things that travel **between two on-screen positions** (a
reordered item, a selection pill sliding between tabs).

### Uniform staggers
**Why it reads cheap:** constant-step cascades across 10+ items look mechanical and take forever.
**Instead:** cap the total at about 400ms. Use shorter steps for small items. Consider an eased
stagger (steps that shrink: `step * i^0.8`) so the tail arrives together. Stagger only what's
visible.

### Centred, symmetric choreography
**Why it reads cheap:** everything scales from the centre or radiates out symmetrically. It looks like
a template transition and ignores the layout's reading order and anchors.
**Instead:** follow reading order (top-left → bottom-right in LTR) and the trigger's position. Scale
from the anchor corner. Let asymmetry carry direction.

### Bounce used as "delight"
**Why it reads cheap:** big overshoot (ζ < 0.6) on product UI feels toy-like, makes the interface
look unstable, and is tiring at frequency.
**Instead:** ζ ≥ 0.8 for anything frequent. Save visible overshoot (5–9%) for rare, celebratory moments,
and apply it to one element, not the whole screen.

### Linear movement
**Why it reads cheap:** objects with no mass and no intention.
**Instead:** a curve or spring for every spatial move. Linear only for rotation, progress and
marquees (rule 5).

### Animating everything on screen
**Why it reads cheap:** noise. The thing that changed is lost among the things that didn't.
**Instead:** animate only what changed, or what needs attention. Static context stays static: that
contrast is what makes the moving element legible.

### Identical entrance and exit timing
**Why it reads cheap:** dismissals feel sluggish, and the exit plays the entrance backwards, which looks
like an undo.
**Instead:** exits at 60–75% of the entrance duration, with an accelerating curve. Exits often travel
less (8px rather than 24px) and fade sooner.

### Scale-from-zero pops
**Why it reads cheap:** a scale of 0 has no size, so it comes from nowhere, and the last 30% of a
0 → 1 scale is a visible "pop".
**Instead:** scale from 0.85–0.96 combined with an opacity ramp over the first 30–40% of the
duration. Icons and badges may go from 0.5 if they have a clear origin.

### Opacity-only transitions where spatial movement would explain more
**Why it reads cheap:** a fade says "this changed" but not where from, where to, or what it is.
**Instead:** add 8–24px of travel in the direction of the relationship (push from the right for
forward navigation, rise for things that come from below). Pure fades are for reduced motion and for
content that replaces content in place.

### Overlong durations on frequent interactions
**Why it reads cheap:** the user waits for the UI. Anything over 200ms on a hover, press or toggle
feels heavy by the third use.
**Instead:** press feedback under 100ms (touch-down, not release), hover 120–180ms, toggles in about
250–300ms of spring settle with 90% complete under 150ms.

### Easing that ignores gesture velocity
**Why it reads cheap:** the user flicks a sheet at 2000px/s, and it stops dead and then eases out on its
own schedule. The object feels disconnected from the hand.
**Instead:** at release, measure velocity (last 50–100ms of pointer samples). Pass it into the spring
as the initial velocity (in units of remaining travel per second). Choose the destination from position
plus projected momentum, not position alone. See `interaction.md`.
