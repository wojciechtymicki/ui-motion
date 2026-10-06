# Critique

How to judge your own motion before the user sees it. Simple pieces run the automated checks plus a
spec match. Complex pieces add the rubric below and fix everything scoring under 8.

## Review method (complex pieces)

1. **Contact sheet** of the whole piece (`contact_sheet.py --keyframes --count 12`). Does each tile
   read? Is the composition good at every frame, not only at the end?
2. **Frame strips around fast moves** (`--range a b --count 10`). Look for pops, smears, overlaps,
   text clipping, and elements passing through each other.
3. **¼-speed review** in the player (0.25×). Timing problems invisible at 1× (late followers, dead
   frames, an overshoot that's too big) become obvious.
4. **1× review, twice, muted**, the way a user sees it. Write the one-sentence description
   (`principles.md` rule 16). Does it match the spec's sentence?
5. **Reduced-motion review** (player toggle).
6. Score the rubric. Write the scores and fixes into the spec's change log.

## Rubric (score 1–10 each; ship at ≥ 8 on all)

| Criterion | 10 looks like | ≤ 6 looks like |
|---|---|---|
| **Matches the spec** | Every row of the timing table is observable at its time; values verified by frame | Timings drifted from the spec; the spec wasn't updated |
| **Smoothness** | No pops, flashes, stalls; constant-velocity moves are perfectly even; jank_check passes | Hitches, one-frame glitches, steppy springs, dropped frames in perf trace |
| **Choreography** | Clear lead; followers subordinate; group lands inside ~400ms; reading order respected | Everything at once, or a long uniform cascade; no hierarchy |
| **Continuity** | Every element comes from somewhere and goes somewhere; shared elements persist; one shape language | Things appear from nowhere; crossfades between unrelated layouts |
| **Timing fits the profile** | Frequency, trigger and attention justify every duration and amplitude | A frequent micro-interaction at 400ms; a once-only moment that's timid |
| **Craft** | Text sharp every frame; exact end states; curves chosen with intent; restrained colour and effects | Blurry scaled text; end frame 1px off; default easing everywhere; gratuitous effects |
| **Reduced-motion quality** | Designed alternative; state still clear; no travel or zoom | Motion simply removed so state changes are invisible, or reduced = same as full |
| **Performance** | Compositor-only properties; frame budget met at 4× CPU throttle / target device | Layout or paint every frame; long tasks during motion |

## Diagnostic table: symptom → cause → fix

| Symptom | Likely cause | Fix |
|---|---|---|
| "Feels cheap" | Bounce on product UI; everything moving at once; scale-from-zero pops; glow/particles | ζ ≥ 0.8; one lead with capped stagger; scale from 0.9+; remove effects |
| "Feels sluggish" | Equal in/out durations; feedback on release instead of press; ease-in-out on entrances; long durations on frequent interactions | Exits at 60–75%; press on touch-down; ease-out/spring entrances; frequency rule |
| "Feels robotic" | Linear movement; uniform stagger; identical durations for different distances | Curves or springs; capped/eased stagger; duration from distance |
| "Feels floaty / drunk" | Low stiffness springs on small elements; long ease-out tails on frequent UI; parallax too strong | Stiffer spring (keep ζ); shorter duration; reduce parallax ratio |
| "Stutters" | Timers (`setTimeout`/`setInterval`) driving motion; animating layout properties; per-frame increments instead of time-based; main-thread work during motion | Time-based seek(t)/rAF; transform/opacity only; move work off the animation window |
| "Pops at the end" | Easing without exact 1 at p = 1; rounding the final value differently; switching elements at the last frame; spring cut before settle | `exact()` easings; set the final state explicitly at t ≥ end; settle-length springs |
| "Loop jumps" | Position matched but velocity not; non-integer cycles; seam frame rendered twice | Periodic functions with integer cycles; zero-velocity seams; `loop_check.py`; render 0…N−1 |
| "Text shimmers / is blurry" | Scaling text; sub-pixel translate at rest; blur filter on text | Mask or fill crossfade; integer translate at rest; remove blur |
| "Too busy" | Animating everything; too many simultaneous leads; decorative loops near content | Animate only what changed; one lead; remove or slow ambient loops |
| "Disconnected from the finger" | Easing ignores release velocity; target chosen by position only; lag while dragging | Velocity handoff; momentum projection; 1:1 drag |
| "Snaps when interrupted" | New animation starts from the target or start, not the current value; queued animations | Interrupt from the presented value with current velocity; no queueing |
| "Overshoot looks wrong" | Overshoot on bars, progress or sheets near the edge; overshoot on both position and scale | ζ ≥ 0.95 there; overshoot on one property only |
| "Can't tell what happened" | Opacity-only where travel would explain; no origin; too fast for a rare event | Add directional travel; emerge from the trigger; lengthen rare moments |
| "Flash / flicker" | Element visible for one frame (mount order, a z-index swap); a 3+ Hz luminance change | Fix mount timing; check jank_check flash report; slow pulses below 3 Hz |

## Self-critique output (in the spec's change log)

```
v2 critique (complex): matches 9 · smooth 8 · choreography 7 → 9 (capped row stagger 0.24→0.18s)
  · continuity 9 · profile 8 · craft 8 · reduced 8 · perf 9
jank_check PASS · loop_check n/a · sheets: out/sheet-…-f0-144.png
```
