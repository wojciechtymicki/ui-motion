# Brief: onboarding-2

| Field | Value |
|---|---|
| Duration | about 2.5s for the entrance |
| Style of motion | calm, friendly, a little bit of character at the end |
| Speed and easing (in your words) | smooth |
| Where it's used (screen, platform, stack) | second onboarding screen, iOS app (SwiftUI); 390×844 |
| Interactive? (what input, what responds) | swipe to next screen; Continue button |
| Loops? | the illustration idles after the entrance |
| Purpose (what should the viewer understand or feel) | "your spending, sorted automatically": the app categorises transactions for you |

## Content

Top: illustration of three transaction cards (Coffee $4.20, Groceries $62.10, Rent $1,450) that sort
themselves into three category chips (Food, Home, Fun). Below: headline "Spending, sorted.", body text
"We categorise every transaction automatically, so you see where money goes.", page dots (2 of 4),
"Continue" button.

## Expected (for graders)

- Complex call → checkpoint with stills before the full build.
- Clear lead (cards), choreography that tells the sorting story in one sentence, headline masked rise,
  button last with the one expressive spring; seamless idle loop (loop_check on the idle).
- Exit/next-screen behaviour defined (swipe follows finger, velocity handoff) in the spec.
- Reduced motion: no travel, sorting shown as crossfade into final positions.
