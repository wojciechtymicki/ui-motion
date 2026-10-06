# Brief: pay-button

| Field | Value |
|---|---|
| Duration | |
| Style of motion | confident, premium, not playful |
| Speed and easing (in your words) | snappy |
| Where it's used (screen, platform, stack) | checkout screen, mobile web (React) |
| Interactive? (what input, what responds) | yes: tap to pay; button shows loading, then success or error |
| Loops? | no (the loading state loops while waiting) |
| Purpose (what should the viewer understand or feel) | the payment was heard instantly and the result is unambiguous |

## Content

A full-width primary button, 56px tall, radius 14, label "Pay $48.00". States: idle, hover (desktop),
pressed, loading, success ("Paid" + check), error ("Try again" + shake), disabled.

## Expected (for graders)

- Full state set with designed transitions; press feedback on touch-down; loading keeps width.
- Label morph without layout jump; check draws on; error shake + colour, ≤ 3 flashes/s.
- Demo timeline in the seek(t) page covering idle → press → loading → success, and a second pass → error.
- Reduced-motion version; React implementation with tokens; jank_check passes.
