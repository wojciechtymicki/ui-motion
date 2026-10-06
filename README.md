# ui-motion

A Claude Code skill that works as a senior motion designer for mobile, desktop and web, plus a
browser review player with frame-accurate, copy-to-prompt timestamps.

Everything is plain files: no bundler, no build step. Python runs the server, capture and analysis
scripts. Node is used only for the Playwright-based test scripts.

## Install

```bash
# 1. Put the skill where Claude Code finds it (or symlink it)
ln -s /path/to/ui-motion ~/.claude/skills/ui-motion

# 2. Python dependencies, in a venv inside the skill (SKILL.md looks for .venv first)
cd ~/.claude/skills/ui-motion
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # playwright, numpy, pillow, imageio-ffmpeg
.venv/bin/python -m playwright install chromium

# 3. Node dependencies (only for perf_test.js, device_matrix.js; lint_motion.js and spring.js need nothing)
npm install
npx playwright install chromium                  # optional: webkit firefox for the browser matrix
```

Requirements: Python ≥ 3.9 and Node ≥ 18. macOS or Linux. ffmpeg comes bundled with `imageio-ffmpeg`.
HEVC-alpha export needs macOS (VideoToolbox).

## Verify

```bash
.venv/bin/python scripts/new_project.py demo --size 800x600 --duration 2 --dir /tmp/motion
.venv/bin/python scripts/serve.py /tmp/motion &          # open the printed URL
.venv/bin/python tests/test_player.py --anim-file /tmp/motion/demo/animation.html
.venv/bin/python tests/test_analysis.py                  # determinism, jank/loop fixtures, measure accuracy
```

## Layout

```
SKILL.md                 the skill: identity, profile, decisions, workflow, router
references/              the knowledge: principles, curves, techniques, domains, formats, platforms, …
templates/
  motion-runtime.js      seek(t) contract + easing, closed-form springs, tween, stagger, PRNG, demo timeline
  animation.html         starter page for a new animation
  brief.md, motion-spec.md
  player/                the review player (index.html, player.css, player.js)
scripts/                 serve, scaffold, capture/render, reference analysis, checks, tests
tests/                   player acceptance test, analysis self-test, fixtures with known defects
evals/                   7 briefs + how to compare skill versions
```

## The review loop

1. The skill builds `animation.html` against `motion-runtime.js` and starts `scripts/serve.py <dir>`.
2. In the player: scrub, step frames (← →), select a range (drag in the lane, or I / O), and click
   the time, playhead, range readout or range body to copy, e.g.
   `onboarding-2 v3 @ 1.42s`, `onboarding-2 v3 @ 1.20s–2.10s`, `onboarding-2 v3 @ frame 85 (60fps)`,
   `onboarding-2 v3 @ frames 72–126 (60fps)`.
3. Paste into Claude Code with a note. The skill renders that exact moment, fixes it, re-renders, and
   bumps the version. The player auto-reloads and keeps your playhead, range, speed and units.

Player keys: Space play/pause · ←/→ one frame · Shift+←/→ one second · Home/End range start/end ·
L loop · R reset range · C copy · I/O set range in/out.

## License

UNLICENSED, internal.
