# Brief: revenue-chart-range

| Field | Value |
|---|---|
| Duration | |
| Style of motion | precise, data-first |
| Speed and easing (in your words) | quick but readable |
| Where it's used (screen, platform, stack) | analytics dashboard, desktop web |
| Interactive? (what input, what responds) | segmented control: 7D / 30D / 90D changes the bar chart |
| Loops? | no |
| Purpose (what should the viewer understand or feel) | the data changed range; values stay trustworthy |

## Content

Bar chart, 640×320. 7 bars (7D) → 30 bars (30D). Y axis 0–max with 4 gridlines; max changes with range.

## Expected (for graders)

- Value-space interpolation; axis animates with data; no overshoot; keyed identity (dates).
- Entering bars grow from baseline, exiting collapse; light stagger by x, capped.
- No misrepresentation at any frame (sheet across the transition).
