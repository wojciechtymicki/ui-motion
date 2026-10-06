# Brief: feed-skeleton

| Field | Value |
|---|---|
| Duration | |
| Style of motion | quiet |
| Speed and easing (in your words) | |
| Where it's used (screen, platform, stack) | social feed, Android (Compose) and web |
| Interactive? (what input, what responds) | no; data arrives from the network |
| Loops? | shimmer while loading |
| Purpose (what should the viewer understand or feel) | content is coming; no jumps when it arrives |

## Content

Feed of 3 visible posts: avatar 40px, name line, 2–3 text lines, image 16:9.

## Expected (for graders)

- Skeleton geometry matches final layout; calm linear shimmer (≥1.2s period, low contrast).
- Delay before showing (~200ms) and minimum display time; per-block crossfade in reading order, no travel.
- Demo timeline covering a fast load (no skeleton) and a slow load; reduced = static skeleton.
