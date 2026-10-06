# ui-motion

A [Claude Code](https://claude.com/claude-code) skill that works as a senior motion designer for
mobile apps, desktop apps and websites. You describe the motion you need; it decides timing,
easing, choreography and format. It builds the animation as a scrubbable page, opens a review
player where you can point at exact frames, tests the result and hands off production-ready code
or assets.

It covers UI transitions, micro-interactions, hover/click/drag responses, animated buttons, icons
and logos, typography motion, looped illustrations, data-viz motion, loading states, splash
screens, onboarding screens and feature explainers.

---

## Install

You need **Claude Code**, **Python 3.9+**, **Node 18+** and **git**, on macOS or Linux.

### 1. Clone into your skills folder

```bash
git clone https://github.com/wojciechtymicki/ui-motion.git ~/.claude/skills/ui-motion
```

The repo is private, so use an account with access. `gh repo clone wojciechtymicki/ui-motion ~/.claude/skills/ui-motion`
works as well. To install for a single project instead, clone into `<project>/.claude/skills/ui-motion`.

### 2. Install the Python tools (rendering, checks, reference analysis)

```bash
cd ~/.claude/skills/ui-motion
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
```

ffmpeg comes bundled with `imageio-ffmpeg`, so there's nothing else to install for video export.

### 3. Install the Node tools (performance and device tests)

```bash
npm install
npx playwright install chromium
```

Optional: `npx playwright install webkit firefox` enables the Safari/Firefox browser matrix.

### 4. Check it works

Restart Claude Code and type `/` in the prompt: **ui-motion** should be listed. To check the tools:

```bash
.venv/bin/python tests/test_analysis.py --quick
```

This should end with `23/23 passed`.

### Updating

```bash
cd ~/.claude/skills/ui-motion && git pull
```

Re-run the `pip install` and `npm install` steps if `requirements.txt` or `package.json` changed.

---

## Use

### Start a piece

In Claude Code, run the skill with a brief:

```
/ui-motion
Animation: onboarding screen 2, illustration entrance
Duration: 2s
Style: gentle parallax, secondary elements appear staggered, notification is the last beat
Speed/easing: soft and calm, no bounce
Where: mobile app onboarding
Interactive: no
Loops: no, holds the final frame
Purpose: explain that orders are confirmed instantly
Figma: https://www.figma.com/design/…?node-id=…
```

Any field can be left out. The skill decides what's missing and logs every assumption so you can
override it. You can also just describe what you want in plain language; the skill triggers on
motion requests without the slash command.

Optional inputs:
- **Figma link:** read via the Figma connector (layers, assets, colour tokens). The final frame is
  checked against Figma's own render.
- **Reference video or GIF:** analysed frame by frame for timing, curves and staggers (the motion's
  grammar, never its content).

Template: [`templates/brief.md`](templates/brief.md). Example briefs: [`evals/briefs/`](evals/briefs).

### What happens next

1. **Spec:** the skill writes `motion-spec.md` with a timing table, choreography, reduced-motion
   version and a list of decisions with reasons.
2. **Checkpoint** (complex pieces only): key-frame stills for one combined approval before the
   full build.
3. **Build:** `animation.html`, a page where every frame is a pure function of time.
4. **Review:** the review player opens (see below).
5. **Test and hand off:** smoothness and loop checks, performance traces, a test report, then the
   deliverable: code (CSS/WAAPI, Motion, SwiftUI, Compose, React Native), Lottie, or video
   (MP4, WebM/HEVC with alpha, GIF, APNG, PNG sequence) with a poster frame.

Projects are created in your working folder, one folder per animation.

### Review in the player

Start it yourself any time:

```bash
~/.claude/skills/ui-motion/.venv/bin/python ~/.claude/skills/ui-motion/scripts/serve.py <folder-with-animations>
```

Open the URL it prints (default `http://127.0.0.1:8765/`). With several animations in the folder,
a dropdown switches between them.

| Action | How |
|---|---|
| Play / pause | Space or the play button; speeds 0.25×–1×; loop toggle |
| Step frames | ← / → one frame, Shift + ← / → one second |
| Scrub | drag on the ruler or the playhead |
| Select a range | drag the handles (the default selection is the whole animation), or press I / O at the playhead. Reset (R) restores the full selection |
| Copy for Claude | click the time readout or playhead (a moment), or the range readout or selection (a range). C copies too |
| Units | Seconds / Frames toggle |
| Reduced motion | the toggle above the stage reloads the reduced-motion version |

Copied text looks like `onboarding-2 v3 @ 1.42s`, `onboarding-2 v3 @ 1.20s–2.10s` or
`onboarding-2 v3 @ frames 72–126 (60fps)`. **Paste it into Claude Code with a note**, e.g.:

```
onboarding-2 v3 @ 1.20s–2.10s: the exit feels late
```

The skill renders that exact moment, updates the spec, fixes the code, compares before and after,
and bumps the version. The player reloads by itself and keeps your playhead, range, speed and
units.

> In the Claude desktop app, the player can run in the Browser pane: add a `.claude/launch.json`
> entry that runs `/usr/bin/python3 <skill>/scripts/serve.py <folder> --port 8765`. Use the system
> Python there, not the skill's `.venv`.

### Tools you can run directly

Run these with `~/.claude/skills/ui-motion/.venv/bin/python` (Python) or `node` (`.js`). `<target>`
is an animation folder, an `animation.html` or a URL.

| Command | What it does |
|---|---|
| `scripts/new_project.py <name> --size 390x844 --duration 2.4` | scaffold a new animation folder |
| `scripts/serve.py <folder>` | review player with auto-reload |
| `scripts/render.py <target> --format mp4` | deterministic render (`mp4`, `webm-alpha`, `hevc-alpha`, `mov-alpha`, `gif`, `apng`, `png`) |
| `scripts/contact_sheet.py <target> --times 0.5,1,1.5` | stills / strips (also `--range a b`, `--prompt "<pasted timestamp>"`) |
| `scripts/jank_check.py <target>` | pops, one-frame glitches, flashes, stalls |
| `scripts/loop_check.py <target>` | loop seam: position and velocity |
| `scripts/extract_frames.py ref.mp4` | reference video/GIF → frames, real timing, cuts |
| `scripts/measure_motion.py ref_mp4_frames` | reference timing, easing curve, springs, staggers |
| `node scripts/perf_test.js <target> --cpu 4` | frame timing and layout/paint cost under CPU throttling |
| `node scripts/device_matrix.js <target> --t 1.2` | viewports × pixel density × modes grid |
| `node scripts/lint_motion.js <files>` | static checks on shipped motion code |
| `node scripts/spring.js --stiffness 400 --damping 38` | spring → damping ratio, settle time, SwiftUI/Compose/Motion equivalents |

Every script has `--help`.

---

## Repository layout

```
SKILL.md        the skill itself (workflow, decision rules, review procedure)
references/     motion knowledge: principles, curves, techniques, domains, formats, platforms, testing
templates/      motion-runtime.js (seek(t) engine), review player, spec/brief templates, SwiftUI spring port
scripts/        player server, scaffolding, rendering, checks, reference analysis, test tools
tests/          self-tests for the player and analysis tools (with deliberately broken fixtures)
evals/          sample briefs for comparing skill versions
```

## License

UNLICENSED, internal.
