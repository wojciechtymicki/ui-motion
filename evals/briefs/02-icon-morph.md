# Brief: menu-close-icon

| Field | Value |
|---|---|
| Duration | |
| Style of motion | crisp |
| Speed and easing (in your words) | |
| Where it's used (screen, platform, stack) | app header, iOS (SwiftUI) and web |
| Interactive? (what input, what responds) | tap toggles menu ↔ close |
| Loops? | no |
| Purpose (what should the viewer understand or feel) | the menu is open / closed |

## Content

24×24 icon, 2px stroke, round caps. Menu: three horizontal lines at y = 7, 12, 17 from x = 4 to 20.
Close: two diagonals from (6,6)–(18,18) and (6,18)–(18,6).

## Expected (for graders)

- Path morph with correct point correspondence; middle line resolves (collapse/fade); optional 90° turn.
- Reads at 24px on every frame (contact sheet at 1×); end frames match static icons exactly.
- Reversible; snappy spring; SwiftUI Shape with animatableData + web implementation.
