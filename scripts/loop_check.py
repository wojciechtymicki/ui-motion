#!/usr/bin/env python3
"""Check that a loop is seamless in position AND velocity.

    python loop_check.py <target> [--scale 1] [--json out.json]

Frames F(i) = seek(i/fps), i = 0..N where N = duration*fps, so F(N) should equal F(0).
  position   mean |F(N) - F(0)|                       must be ~0
  velocity   the seam step |F(0) - F(N-1)| compared with the steps either side
             |F(N-1) - F(N-2)| and |F(1) - F(0)|: a matched-position loop whose
             speed changes at the seam shows a ratio far from 1
  velocity   motion vectors (block-matching flow) across the seam N-1 → 0 compared
             with the vectors just before and after: the change in velocity at the
             seam must not exceed the largest frame-to-frame change elsewhere in the
             loop by more than --accel-ratio (catches reversals and speed jumps that
             a position match hides)
Also warns when duration*fps is not an integer (the loop cannot land on a frame).
Exit code 1 on failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402


def mad(a, b):
    return float(np.abs(a.astype(np.float32) - b.astype(np.float32)).mean())


def flows(frames: list[np.ndarray], px_scale: float):
    """Per-pair tile flow for the cyclic sequence F(0)..F(N-1) (pair i: i -> i+1 mod N)."""
    from _flow import block_flow, gray
    G = [gray(f, 320) for f in frames]
    k = px_scale * frames[0].shape[1] / G[0].shape[1]  # flow px -> stage px
    out = []
    n = len(G)
    for i in range(n):
        dx, dy, v = block_flow(G[i], G[(i + 1) % n])
        out.append((dx * k, dy * k, v))
    return out


def max_accel(f1, f2, reach=3):
    """Largest velocity change (stage px/frame) between consecutive flow fields.
    A moving object covers different tiles each frame, so each moving tile in f2 is
    matched to the most similar moving tile within `reach` tiles in f1 (same object);
    the result is the largest of those best-match differences."""
    dx1, dy1, v1 = f1
    dx2, dy2, v2 = f2
    m1 = v1 & ((np.abs(dx1) > 0.05) | (np.abs(dy1) > 0.05))
    m2 = v2 & ((np.abs(dx2) > 0.05) | (np.abs(dy2) > 0.05))
    p1 = np.argwhere(m1)
    if len(p1) == 0 or m2.sum() == 0:
        return 0.0
    worst = 0.0
    for y, x in np.argwhere(m2):
        near = p1[(np.abs(p1[:, 0] - y) <= reach) & (np.abs(p1[:, 1] - x) <= reach)]
        if len(near) == 0:
            continue
        diffs = np.hypot(dx1[near[:, 0], near[:, 1]] - dx2[y, x], dy1[near[:, 0], near[:, 1]] - dy2[y, x])
        worst = max(worst, float(diffs.min()))
    return worst


def analyse(frames: list[np.ndarray], pos_tol=0.05, vel_tol=0.35, accel_ratio=3.0, floor=0.05,
            px_scale: float = 1.0) -> dict:
    """frames: F(0)..F(N) inclusive. px_scale converts capture px to stage px."""
    F = frames
    N = len(F) - 1
    pos = mad(F[N], F[0])
    seam = mad(F[0], F[N - 1])
    before = mad(F[N - 1], F[N - 2])
    after = mad(F[1], F[0])
    ref = (before + after) / 2
    vel_ratio = seam / ref if ref > floor else (1.0 if seam <= floor else float("inf"))

    fl = flows(F[:N], px_scale)          # pair i = F(i) -> F(i+1 mod N); pair N-1 is the seam
    acc = [max_accel(fl[i - 1], fl[i]) for i in range(N)]   # acc[i]: change entering pair i
    seam_acc = max(acc[N - 1], acc[0])   # entering the seam pair, and leaving it
    inner = [a for i, a in enumerate(acc) if i not in (0, N - 1)]
    base = float(np.percentile(inner, 95)) if inner else 0.0   # robust to a few tile mismatches
    acc_ratio = seam_acc / max(base, 0.25)

    fails = []
    if pos > pos_tol:
        fails.append(f"position: last frame differs from first by {pos:.3f} (tol {pos_tol})")
    if ref > floor and abs(vel_ratio - 1) > vel_tol:
        fails.append(f"speed: seam step is {vel_ratio:.2f}× its neighbours (tol ±{vel_tol:.0%})")
    if seam_acc > 1.0 and acc_ratio > accel_ratio:
        fails.append(f"velocity: changes by {seam_acc:.1f}px/frame at the seam, {acc_ratio:.1f}× the typical largest change elsewhere (p95 {base:.1f})")
    return {"frames": N, "position_error": round(pos, 4), "seam_step": round(seam, 4),
            "step_before": round(before, 4), "step_after": round(after, 4), "velocity_ratio": round(vel_ratio, 3),
            "seam_accel_px": round(seam_acc, 3), "max_inner_accel_px": round(base, 3),
            "accel_ratio": round(acc_ratio, 2), "failures": fails}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="animation .html, project folder or URL")
    ap.add_argument("--scale", type=float, default=1.0, help="capture density (keep 1: lower densities alias and fake velocity noise)")
    ap.add_argument("--reduced", action="store_true")
    ap.add_argument("--pos-tol", type=float, default=0.05)
    ap.add_argument("--vel-tol", type=float, default=0.35)
    ap.add_argument("--accel-ratio", type=float, default=3.0)
    ap.add_argument("--json")
    args = ap.parse_args(argv)

    from _capture import Capture
    with Capture(args.target, scale=args.scale, reduced=args.reduced) as cap:
        fps, dur = cap.fps, cap.duration
        exact = dur * fps
        N = round(exact)
        frames = [cap.array(i / fps) for i in range(N)] + [cap.array(dur)]
        label = f"{cap.meta['name']} v{cap.meta['version']}"
        loops = cap.meta.get("loops")

    rep = analyse(frames, args.pos_tol, args.vel_tol, args.accel_ratio, px_scale=1 / args.scale)
    rep["target"] = label
    if abs(exact - N) > 1e-6:
        rep["failures"].insert(0, f"duration×fps = {exact:.3f} is not an integer: the loop cannot land on a frame")
    if not loops:
        rep["warning"] = "page does not declare loops: true in Motion.register"
    if args.json:
        Path(args.json).write_text(json.dumps(rep, indent=2))
    print(f"loop_check {label}: {N} frames  pos_err={rep['position_error']}  vel_ratio={rep['velocity_ratio']}  accel_ratio={rep['accel_ratio']}")
    if rep.get("warning"):
        print("WARN", rep["warning"])
    if rep["failures"]:
        for f in rep["failures"]:
            print("FAIL", f)
        return 1
    print("PASS seamless in position and velocity")
    return 0


if __name__ == "__main__":
    sys.exit(main())
