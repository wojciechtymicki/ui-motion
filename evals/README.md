# Evals

Seven briefs that cover the skill's range. Use them to compare skill versions (a change to
`SKILL.md` or a reference file) on the same inputs.

| # | Brief | Exercises |
|---|---|---|
| 1 | `01-animated-button.md` | interaction state model, label morph, demo timeline, runtime track (React) |
| 2 | `02-icon-morph.md` | path morph correspondence, 24px legibility, SwiftUI + web |
| 3 | `03-onboarding-screen.md` | complex choreography, checkpoint, text rise, idle loop, gesture spec |
| 4 | `04-chart-transition.md` | data-viz honesty, keyed transitions, axis + data together |
| 5 | `05-logo-sting.md` | exact end frame, rendered track, formats, poster |
| 6 | `06-skeleton-handoff.md` | loading timing rules, geometry match, Compose + web |
| 7 | `07-looped-illustration.md` | seamless loop construction, accessibility (pause), seeded variation |

## Running a comparison

1. Snapshot the skill version under test (e.g. `git stash`/branch, or copy the folder to
   `ui-motion@A` and `ui-motion@B`).
2. For each brief, start a fresh Claude Code session with that skill version installed at
   `~/.claude/skills/ui-motion` and prompt: *"Use the ui-motion skill on this brief: <paste brief>.
   Work in `evals/runs/<version>/<brief-slug>/`. Stop after handoff."* For brief 3, approve the
   checkpoint with "approved" so runs are comparable.
3. Collect per run: `motion-spec.md`, `animation.html`, `out/` (sheets, renders, test report), and
   the transcript.

## What to compare

Automatic (run from the skill root on each run folder):

```bash
python scripts/jank_check.py evals/runs/<v>/<slug>            # pass/fail + issues
python scripts/jank_check.py evals/runs/<v>/<slug> --reduced
python scripts/loop_check.py evals/runs/<v>/<slug>            # briefs 3 (idle), 7
node scripts/lint_motion.js evals/runs/<v>/<slug>
node scripts/perf_test.js evals/runs/<v>/<slug> --cpu 4
python scripts/contact_sheet.py evals/runs/<v>/<slug> --keyframes --count 12 --out evals/runs/<v>/<slug>-sheet.png
```

Human / grader (score 1–10 with `references/critique.md` rubric), using the **Expected** list at the
bottom of each brief as the checklist:

- spec quality: profile, decisions logged with reasons, timing table complete and matching the render
- motion quality: the eight rubric criteria, judged from the sheets and the player at 1× and 0.25×
- process: questions asked only when blocked; checkpoint used only for complex; review-prompt
  procedure followed when given a timestamp
- deliverables: reduced version, test report, tokens, handoff notes

Put the contact sheets of version A and B side by side per brief; regressions are usually visible
there first. Record results in `evals/results.md` (one row per brief × version).

## Review-prompt eval

After a run, paste a synthetic note (e.g. `onboarding-2 v1 @ 1.20s–2.10s: exit feels late`) and
check the skill: parses it, renders before/after strips (`--tag before/after`), updates the spec
first, bumps the version, re-runs jank_check.
