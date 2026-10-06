#!/usr/bin/env python3
"""Find pops, one-frame flashes and dead frames in a seek(t) animation.

    python jank_check.py <target> [--scale 1] [--start A --end B] [--json out.json]

Per frame i, d[i] = mean |frame(i+1) - frame(i)| (0..255, max over channels).
  pop         d[i] > --pop-ratio (3) × max(d[i-1], d[i+1]) and d[i] > --floor
              (or a motion-vector speed spike vs. both neighbours)
              (a single step much bigger than its neighbours: a skipped beat,
              a property snapping, a layout jump)
  flash       frame i differs from both neighbours while i-1 ≈ i+1
              (something appears or disappears for exactly one frame)
  off-path    frame i is not between its neighbours: d(i-1,i)+d(i,i+1) > 3 × d(i-1,i+1)
              (a one-frame position/scale glitch inside a move)
  dead        a run of >= --dead-run identical frames *between* moving stretches
              (a mid-sequence stall; the final hold and the lead-in are allowed)
Exit code 1 when anything is found. Also reads frames from a folder of PNGs (--frames-dir).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402


def frame_diff(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2).mean())


def changed_px(a: np.ndarray, b: np.ndarray, thr: int = 2) -> int:
    return int((np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2) > thr).sum())


def flow_speeds(frames: list[np.ndarray], px_scale: float) -> list[float]:
    """Fastest agreed-upon tile motion per step, in stage px/frame (block-matching flow).
    Jumps beyond the search range (~55px at analysis size) are left to the pixel-diff tests."""
    from _flow import block_flow, gray
    G = [gray(f, 320) for f in frames]
    k = px_scale * frames[0].shape[1] / G[0].shape[1]
    out = []
    for i in range(len(G) - 1):
        dx, dy, v = block_flow(G[i], G[i + 1])
        vx, vy = dx[v] * k, dy[v] * k
        moving = np.hypot(vx, vy) > 0.05
        vx, vy = vx[moving], vy[moving]
        # Only trust vectors that at least one other tile agrees with (within 3px):
        # a lone tile is usually a false match (text emerging from a mask, repeats).
        best = 0.0
        for j in range(len(vx)):
            if (np.hypot(vx - vx[j], vy - vy[j]) <= 3.0).sum() >= 2:
                best = max(best, float(np.hypot(vx[j], vy[j])))
        out.append(best)
    return out


def local_step(d, i, k=5):
    """Median step size around i, excluding the two steps touching frame i (the motion envelope)."""
    near = [d[j] for j in range(max(0, i - 1 - k), min(len(d), i + 1 + k)) if j not in (i - 1, i)]
    return float(np.median(near)) if near else 0.0


def analyse(frames: list[np.ndarray], times: list[float], fps: float, pop_ratio=3.0, floor=0.15,
            flash_thr=0.5, dead_run=3, px_scale: float = 1.0, use_flow: bool = True, holds=()) -> dict:
    n = len(frames)
    d = [frame_diff(frames[i], frames[i + 1]) for i in range(n - 1)]
    moving = [changed_px(frames[i], frames[i + 1]) > 0 for i in range(n - 1)]
    issues = []

    still = 0.02
    for i in range(1, len(d) - 1):
        # A motion onset/end is compared with its continuation only (one side is still).
        sides = [x for x in (d[i - 1], d[i + 1]) if x > still]
        if not sides:
            continue
        nb = max(sides)                    # "more than 3x its neighbours": each of them
        if d[i] > floor and d[i] > pop_ratio * max(nb, 1e-3):
            issues.append({"type": "pop", "frame": i + 1, "t": round(times[i + 1], 4),
                           "step": round(d[i], 3), "neighbours": round(nb, 3), "ratio": round(d[i] / max(nb, 1e-3), 1)})

    # Speed spikes measured with motion vectors (pixel diffs saturate once a jump
    # is bigger than the element, so they under-report snaps).
    speeds = flow_speeds(frames, px_scale) if use_flow else []
    flagged = {it["frame"] for it in issues}
    for i in range(1, len(speeds) - 1):
        s0, s1, s2 = speeds[i - 1], speeds[i], speeds[i + 1]
        if (i + 1) in flagged or s0 <= 0 or s2 <= 0:
            continue                     # flow could not measure a neighbour: no basis for a ratio
        nb = (s0 + s2) / 2
        pixel_spike = d[i] > 1.3 * max(d[i - 1], d[i + 1], 1e-3)   # confirm in pixels: flow can alias on repeats
        if s1 > 2.0 and s1 > pop_ratio * max(nb, 0.5) and pixel_spike:
            issues.append({"type": "pop", "frame": i + 1, "t": round(times[i + 1], 4), "speed_px": round(s1, 2),
                           "neighbours_px": round(nb, 2), "ratio": round(s1 / max(nb, 0.5), 1)})

    def fast_vs_envelope(i):
        """Off-path frames come with abnormally fast steps in or out of them. Oscillation
        turnarounds (a designed shake) have near-zero speed at the reversal, so they pass."""
        if speeds:
            near = [speeds[j] for j in range(max(0, i - 7), min(len(speeds), i + 7)) if j not in (i - 1, i) and speeds[j] > 0]
            env = float(np.median(near)) if near else 0.0
            return max(speeds[i - 1], speeds[i]) > max(2.0, 1.8 * env)
        return min(d[i - 1], d[i]) > 1.5 * local_step(d, i)

    # A frame that is not "between" its neighbours: going prev -> i -> next is a much
    # longer path than prev -> next. If prev ≈ next it is a flash; otherwise the frame
    # jumped off the motion path (a one-frame position/scale glitch).
    for i in range(1, n - 1):
        around = frame_diff(frames[i - 1], frames[i + 1])
        via = d[i - 1] + d[i]
        if d[i - 1] <= floor or d[i] <= floor:
            continue
        if d[i - 1] > flash_thr and d[i] > flash_thr and around < 0.25 * min(d[i - 1], d[i]):
            issues.append({"type": "flash", "frame": i, "t": round(times[i], 4),
                           "in": round(d[i - 1], 3), "out": round(d[i], 3), "prev_vs_next": round(around, 3)})
        elif via > pop_ratio * max(around, floor) and fast_vs_envelope(i):
            issues.append({"type": "off-path", "frame": i, "t": round(times[i], 4),
                           "via": round(via, 3), "direct": round(around, 3), "ratio": round(via / max(around, 1e-3), 1)})

    # dead frames: runs of no change strictly between the first and last moving step
    if any(moving):
        first = moving.index(True)
        last = len(moving) - 1 - moving[::-1].index(True)
        run = 0
        for i in range(first, last + 1):
            if not moving[i]:
                run += 1
            else:
                if run >= dead_run:
                    s = i - run
                    t0, t1 = times[s + 1], times[i]
                    tol = 1.5 / fps
                    if any(h0 - tol <= t0 and t1 <= h1 + tol for h0, h1 in holds):
                        run = 0
                        continue
                    issues.append({"type": "dead", "frames": [s + 1, i], "t": [round(times[s + 1], 4), round(times[i], 4)],
                                   "length_ms": round(run / fps * 1000)})
                run = 0

    return {"frames": n, "fps": fps, "steps": [round(x, 4) for x in d],
            "speeds_px": [round(x, 2) for x in speeds], "issues": issues,
            "moving_from": round(times[moving.index(True)], 4) if any(moving) else None,
            "settled_at": round(times[len(moving) - moving[::-1].index(True)], 4) if any(moving) else None}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", nargs="?", help="animation .html, project folder or URL")
    ap.add_argument("--frames-dir", help="analyse a folder of PNG frames instead (sorted by name)")
    ap.add_argument("--fps", type=float, default=None, help="fps for --frames-dir (default 60)")
    ap.add_argument("--scale", type=float, default=1.0, help="capture density (keep 1: lower densities alias scaled text and fake pops)")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--reduced", action="store_true")
    ap.add_argument("--pop-ratio", type=float, default=3.0)
    ap.add_argument("--floor", type=float, default=0.15, help="ignore steps below this mean diff")
    ap.add_argument("--dead-run", type=int, default=3, help="identical frames that count as a stall")
    ap.add_argument("--no-flow", action="store_true", help="skip motion-vector pop detection (faster)")
    ap.add_argument("--strict-holds", action="store_true", help="treat holds in --reduced renders as failures too")
    ap.add_argument("--json", help="write the full report here")
    args = ap.parse_args(argv)

    if args.frames_dir:
        files = sorted(Path(args.frames_dir).glob("*.png"))
        if len(files) < 3:
            raise SystemExit("error: need at least 3 PNG frames")
        fps = args.fps or 60
        frames = [np.asarray(Image.open(f).convert("RGB")) for f in files]
        times = [i / fps for i in range(len(frames))]
        holds = []
        label = args.frames_dir
    else:
        if not args.target:
            ap.error("target or --frames-dir required")
        from _capture import Capture
        with Capture(args.target, scale=args.scale, reduced=args.reduced) as cap:
            times = cap.frame_times(args.start, args.end, include_end=True)
            frames = [cap.array(t) for t in times]
            fps = cap.fps
            holds = cap.meta.get("holds") or []
            label = f"{cap.meta['name']} v{cap.meta['version']}" + (" (reduced)" if args.reduced else "")

    px_scale = 1.0 if args.frames_dir else 1 / args.scale
    rep = analyse(frames, times, fps, args.pop_ratio, args.floor, dead_run=args.dead_run,
                  px_scale=px_scale, use_flow=not args.no_flow, holds=holds)
    rep["declared_holds"] = holds
    rep["target"] = label
    # Reduced-motion versions replace travel with holds and short fades: holds are expected there.
    rep["warnings"] = []
    if args.reduced and not args.strict_holds:
        rep["warnings"] = [i for i in rep["issues"] if i["type"] == "dead"]
        rep["issues"] = [i for i in rep["issues"] if i["type"] != "dead"]
    if args.json:
        Path(args.json).write_text(json.dumps(rep, indent=2))
    print(f"jank_check {label}: {rep['frames']} frames, motion {rep['moving_from']}s → {rep['settled_at']}s")
    for w in rep["warnings"]:
        print("WARN (hold in reduced version)", json.dumps(w))
    if not rep["issues"]:
        print("PASS no pops, flashes or dead frames")
        return 0
    for it in rep["issues"]:
        print("FAIL", json.dumps(it))
    return 1


if __name__ == "__main__":
    sys.exit(main())
