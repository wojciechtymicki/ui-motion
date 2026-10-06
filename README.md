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

To install for a single project instead, clone into `<project>/.claude/skills/ui-motion`.

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
> entry that runs `/usr/bin/python3 <skill>/scripts/serve.py <folder>` with `"autoPort": true`
> (the server then uses the port the app assigns). Use the system Python there, not the skill's `.venv`.

### Export your animation

The easiest way is to ask Claude in plain words, for example:

```
Export mg-onboarding-bag as an MP4 for our website
Export mg-onboarding-bag with a transparent background
Give me a GIF of mg-onboarding-bag for Slack
```

Claude picks the right settings and tells you where the files are. Exports are saved in the
animation's own `out/` folder, together with a **poster** image (a still of the final frame).

**Which format do I need?**

| You want to… | Ask for | Format |
|---|---|---|
| put it on a website, in a presentation or on social media | MP4 | `mp4` |
| place it over other content (no background) on a website | transparent video | `webm-alpha` (Chrome, Firefox) **and** `hevc-alpha` (Safari, macOS only) |
| edit it further in After Effects, Premiere or Final Cut | ProRes with transparency | `mov-alpha` |
| share it in Slack, email or a doc | GIF | `gif` |
| a looping image with transparency that works anywhere an image does | animated PNG | `apng` |
| individual frames for a designer or developer | PNG sequence | `png` |
| ship it inside an app (iOS, Android, Flutter, web) | ask Claude for the app version | Lottie or code, built from the same animation |

Useful extras to mention when you ask: **"at 2× size"** for sharp retina output, and **"the
reduced-motion version"** for the calmer variant shown to people who turn animations off.

**Exporting yourself in Terminal (optional).** Use the same command and change the last part:

```bash
~/.claude/skills/ui-motion/.venv/bin/python ~/.claude/skills/ui-motion/scripts/render.py \
  path/to/your-animation-folder --format mp4
```

Replace `mp4` with any format from the table. Add `--scale 2` for 2× size and `--reduced` for the
reduced-motion version.

> The skill comes with more helper scripts (quality checks, reference-video analysis, performance
> tests). Claude runs them for you while it works, so you don't need them. Each one explains
> itself with `--help` if you're curious.

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

No license has been chosen yet, so all rights are reserved by the author.
