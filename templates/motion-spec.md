# Motion spec: {{NAME}}

Version: v1 · Stage: {{WIDTH}}×{{HEIGHT}} · Duration: {{DURATION}}s · {{FPS}} fps
Implements: `animation.html` (every file that implements this spec names it in a header comment).

## 1. Profile

| Dimension | Value | Consequence |
|---|---|---|
| Frequency | constantly · often · rarely · once | |
| Trigger | user input · system event · time · scroll | |
| Duration | instant · short · long · looping | |
| Attention | peripheral · supporting · focal | |
| Platform | iOS · Android · web · desktop · cross-platform | |

**Complexity:** simple | complex. One line of reasoning.

**Track:** runtime | rendered | both. **Format:** … because … (one line).

**Job of the motion:** orient | feedback | focus | continuity. **Silent sentence:** "…"

## 2. Timing table

Times in seconds from t=0. Springs list stiffness/damping and the derived damping ratio (ζ) and settle time.
`seek(t)` must reproduce this table exactly; any change to the code changes this table first.

| # | Element | Property | From → To | Duration / spring | Easing | Delay | Trigger |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |

## 3. Choreography

Lead element, followers, stagger step and cap, where things come from and leave to.
Overlaps between phases (the next element enters already moving).

## 4. Interruption rules

What happens on re-trigger, reverse, or interrupt mid-flight. Always from the current value,
carrying current velocity. Not applicable for rendered-only pieces: say so.

## 5. Loop construction

Integer cycles, how the seam is matched in position AND velocity. "No loop" if it doesn't loop.

## 6. Reduced motion

What replaces travel, scale, parallax and loops. Durations. What stays (state must still read).

## 7. Tokens

Colours, type, radii, spacing, curves and springs used, with their source (Figma variable, product token, or new).

## 8. Decisions and assumptions

One line each, with the reason. The user can override any of them.

- **Easing:** … because …
- **Format:** … because …

## 9. Change log

| Version | Change | Why (review note) |
|---|---|---|
| v1 | Initial build | |
