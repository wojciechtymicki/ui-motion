#!/usr/bin/env python3
"""Measure the grammar of a reference motion: timing, curves, staggers.

    python measure_motion.py <frames_dir|video|gif> [--box x,y,w,h ...] [--auto 4] [--segment N]

Input is a folder made by extract_frames.py (uses its frames.json timing) or a
video/GIF (extracted on the fly). Regions are given with --box (source pixels,
repeatable, optional name: --box card=40,120,300,200) or found automatically
(--auto K: the K largest areas of change).

Per region it reports
  start / end / duration   fitted (sub-frame) and visible (first/last frame that moved)
  travel                   px, main axis, or "opacity/colour" when nothing translates
  velocity profile         px/s per frame pair (block-matching flow)
  overshoot                % past the final value
  curve                    best fit among named curves, a refined cubic-bezier, and a
                           closed-form spring (stiffness/damping, ζ, settle time),
                           plus the class: linear | ease-out | ease-in | ease-in-out | spring
and, with several regions, the stagger between their fitted starts.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from _flow import gray, region_velocity  # noqa: E402

ANALYSIS_SIDE = 480
SEARCH_RADIUS = 16   # coarse radius at 1/8 scale: ±128 analysis px per frame (fast ease-out starts)

# Same named curves as templates/motion-runtime.js (cubic-bezier control points).
NAMED = {
    "linear": (0, 0, 1, 1),
    "standard": (0.2, 0, 0, 1),
    "out": (0.16, 1, 0.3, 1),
    "outQuart": (0.25, 1, 0.5, 1),
    "outCubic": (0.33, 1, 0.68, 1),
    "in": (0.55, 0, 1, 0.45),
    "inCubic": (0.32, 0, 0.67, 0),
    "inOut": (0.65, 0, 0.35, 1),
    "emphasizedDecel": (0.05, 0.7, 0.1, 1),
    "css-ease": (0.25, 0.1, 0.25, 1),
    "css-ease-in-out": (0.42, 0, 0.58, 1),
    "css-ease-out": (0, 0, 0.58, 1),
    "backOut": (0.34, 1.36, 0.64, 1),
}


# ------------------------------------------------------------------ curve models

def bezier_table(x1, y1, x2, y2, n=1024):
    s = np.linspace(0, 1, 4096)
    bx = 3 * x1 * s * (1 - s) ** 2 + 3 * x2 * s ** 2 * (1 - s) + s ** 3
    by = 3 * y1 * s * (1 - s) ** 2 + 3 * y2 * s ** 2 * (1 - s) + s ** 3
    order = np.argsort(bx)
    xs = np.linspace(0, 1, n)
    return np.interp(xs, bx[order], by[order])


def eval_table(table, p):
    p = np.clip(p, 0, 1)
    return np.interp(p, np.linspace(0, 1, len(table)), table)


def spring_curve(t, zeta, w0, v0=0.0):
    t = np.maximum(t, 0)
    if zeta < 1 - 1e-6:
        wd = w0 * math.sqrt(1 - zeta * zeta)
        A, B = -1.0, (v0 - zeta * w0) / wd
        return 1 + np.exp(-zeta * w0 * t) * (A * np.cos(wd * t) + B * np.sin(wd * t))
    if zeta <= 1 + 1e-6:
        return 1 + (-1 + (v0 - w0) * t) * np.exp(-w0 * t)
    sq = math.sqrt(zeta * zeta - 1)
    r1, r2 = -w0 * (zeta - sq), -w0 * (zeta + sq)
    C2 = (v0 + r1) / (r2 - r1)
    return 1 + (-1 - C2) * np.exp(r1 * t) + C2 * np.exp(r2 * t)


def spring_settle(zeta, w0, eps=0.001):
    """Same rule as motion-runtime.js: position within 0.1% AND |v|/ω0 within 0.1%."""
    t = np.arange(0, 10, 0.001)
    x = spring_curve(t, zeta, w0)
    v = np.gradient(x, t)
    out = np.nonzero((np.abs(x - 1) > eps) | (np.abs(v) / max(w0, 1) > eps))[0]
    return float(t[out[-1]] + 0.001) if len(out) else 0.0


def _grid(times, prog, table, S, D):
    tt = times[None, None, :]
    P = (tt - S[:, None, None]) / D[None, :, None]
    err = np.sqrt(((eval_table(table, P) - prog[None, None, :]) ** 2).mean(axis=2))
    i, j = np.unravel_index(np.argmin(err), err.shape)
    return float(err[i, j]), float(S[i]), float(D[j])


def fit_timing(times, prog, table, s_range, d_range, step):
    """Start s and duration d for a fixed curve, coarse-to-fine grid. Returns (rmse, s, d)."""
    coarse = step * 4
    S = np.arange(s_range[0], s_range[1] + 1e-9, coarse)
    D = np.arange(max(coarse, d_range[0]), d_range[1] + 1e-9, coarse)
    if len(S) == 0 or len(D) == 0:
        return float("inf"), s_range[0], d_range[0]
    e, s, d = _grid(times, prog, table, S, D)
    S = np.arange(s - coarse, s + coarse + 1e-9, step / 2)
    D = np.arange(max(step, d - coarse), d + coarse + 1e-9, step / 2)
    return _grid(times, prog, table, S, D)


def fit_spring(times, prog, s_range, step):
    best = (float("inf"), None)
    S = np.arange(s_range[0], s_range[1] + 1e-9, step)
    for zeta in np.arange(0.15, 1.31, 0.025):
        for w0 in np.arange(4, 80, 0.5):
            tt = times[None, :] - S[:, None]
            m = np.where(tt <= 0, 0.0, spring_curve(tt, zeta, w0))
            err = np.sqrt(((m - prog[None, :]) ** 2).mean(axis=1))
            k = int(np.argmin(err))
            if err[k] < best[0]:
                best = (float(err[k]), (float(S[k]), float(zeta), float(w0)))
    return best


def classify_bezier(c):
    tab = bezier_table(*c, n=512)
    v = np.diff(tab)
    if v.max() - v.min() < 0.15 * v.mean() + 1e-9:
        return "linear"
    peak = int(np.argmax(v)) / len(v)
    if tab.max() > 1.005:
        return "ease-out with overshoot"
    if peak < 0.3:
        return "ease-out"
    if peak > 0.7:
        return "ease-in"
    return "ease-in-out"


# ------------------------------------------------------------------ frames + regions

def load_frames(src: Path, segment: int | None):
    if src.is_dir():
        info = json.loads((src / "frames.json").read_text())
        folder = src
    else:
        import extract_frames
        folder = Path(tempfile.mkdtemp(prefix="measure_"))
        extract_frames.main([str(src), "--out", str(folder), "--no-sheets"])
        info = json.loads((folder / "frames.json").read_text())
    frames = info["frames"]
    if segment is not None:
        seg = info["segments"][segment - 1]
        frames = frames[seg["start"]: seg["end"] + 1]
    elif len(info["segments"]) > 1:
        print(f"note: {len(info['segments'])} segments (hard cuts at {info['cuts']}); measuring segment 1. Use --segment N.", file=sys.stderr)
        seg = info["segments"][0]
        frames = frames[seg["start"]: seg["end"] + 1]
    rgb = [np.asarray(Image.open(folder / f["file"]).convert("RGB")) for f in frames]
    times = np.array([f["t"] for f in frames], dtype=np.float64)
    return rgb, times, info


def auto_regions(G, k, min_cells=4):
    act = np.zeros_like(G[0])
    for a, b in zip(G, G[1:]):
        act = np.maximum(act, np.abs(a - b))
    cell = 8
    h, w = act.shape[0] // cell, act.shape[1] // cell
    grid = act[: h * cell, : w * cell].reshape(h, cell, w, cell).max(axis=(1, 3)) > 12
    seen = np.zeros_like(grid)
    comps = []
    for y in range(h):
        for x in range(w):
            if grid[y, x] and not seen[y, x]:
                stack, cells = [(y, x)], []
                seen[y, x] = True
                while stack:
                    cy, cx = stack.pop()
                    cells.append((cy, cx))
                    for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                        if 0 <= ny < h and 0 <= nx < w and grid[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
                if len(cells) >= min_cells:
                    ys, xs = zip(*cells)
                    comps.append((len(cells), (min(xs) * cell, min(ys) * cell, (max(xs) + 1 - min(xs)) * cell, (max(ys) + 1 - min(ys)) * cell)))
    comps.sort(key=lambda c: -c[0])
    return [c[1] for c in comps[:k]]


# ------------------------------------------------------------------ per-region analysis

def track_foreground(G, box, thr=24.0):
    """Absolute tracking for flat backgrounds (most UI): the background is the dominant
    grey level of the box in the first and last frame; the element is everything that
    differs from it. Returns per-frame centroids (analysis px) or None when the
    background is textured or the element leaves the box."""
    x, y, w, h = box
    def bg_level(a):
        crop = a[y:y + h, x:x + w]
        hist, edges = np.histogram(crop, 64, (0, 256))
        k = int(np.argmax(hist))
        level = (edges[k] + edges[k + 1]) / 2
        return level, float((np.abs(crop - level) <= 8).mean())
    l0, f0 = bg_level(G[0])
    l1, f1 = bg_level(G[-1])
    if f0 < 0.6 or f1 < 0.6 or abs(l0 - l1) > 8:
        return None
    level = (l0 + l1) / 2
    pts, areas = [], []
    yy, xx = np.mgrid[y:y + h, x:x + w]
    for a in G:
        m = np.abs(a[y:y + h, x:x + w] - level) > thr
        n = int(m.sum())
        if n < 6:
            return None
        pts.append((float(xx[m].mean()), float(yy[m].mean())))
        areas.append(n)
    areas = np.array(areas, float)
    if areas.min() < 0.7 * areas.max():   # element clipped by the box or changing size: not a clean translate
        return None
    return np.array(pts)


def analyse_region(G, times, box, k_src, frame_dt):
    x, y, w, h = box
    n = len(G)
    vel = [(0.0, 0.0)]
    energy = [0.0]
    lum = [float(G[0][y:y + h, x:x + w].mean())]
    for i in range(1, n):
        vx, vy, _ = region_velocity(G[i - 1], G[i], box, radius=SEARCH_RADIUS)
        vel.append((vx, vy))
        energy.append(float(np.abs(G[i][y:y + h, x:x + w] - G[i - 1][y:y + h, x:x + w]).mean()))
        lum.append(float(G[i][y:y + h, x:x + w].mean()))
    vel = np.array(vel) * k_src
    pos = np.cumsum(vel, axis=0)
    fg = track_foreground(G, box)
    if fg is not None:                     # exact absolute positions beat integrated flow
        pos = (fg - fg[0]) * k_src
        vel = np.vstack([[0.0, 0.0], np.diff(pos, axis=0)])
    final = pos[-1]
    far = pos[np.argmax(np.hypot(pos[:, 0], pos[:, 1]))]
    travel = float(np.hypot(*final))
    energy = np.array(energy)
    res = {}
    if travel >= 3 or float(np.hypot(*far)) >= 3:
        axis = final / travel if travel >= 3 else far / max(1e-9, float(np.hypot(*far)))
        proj = pos @ axis
        prog = proj / (proj[-1] if abs(proj[-1]) >= 3 else proj[np.argmax(np.abs(proj))])
        res.update(kind="translate", tracking="foreground" if fg is not None else "flow",
                   travel_px=round(float(proj[-1]), 1),
                   axis=[round(float(axis[0]), 3), round(float(axis[1]), 3)],
                   returns=bool(travel < 0.5 * float(np.hypot(*far))))
    else:
        lum = np.array(lum)
        dl = lum[-1] - lum[0]
        if abs(dl) < 1.0:
            res.update(kind="none")
            return res, None
        prog = (lum - lum[0]) / dl
        res.update(kind="opacity/colour", luminance_change=round(float(dl), 1))

    speed = np.hypot(vel[:, 0], vel[:, 1]) / np.maximum(np.diff(np.concatenate([[times[0] - frame_dt], times])), 1e-6)
    res["velocity_profile"] = [[round(float(t), 4), round(float(s), 1)] for t, s in zip(times, speed)]
    res["peak_speed_px_s"] = round(float(speed.max()), 1)
    return res, prog


def fit_region(times, prog, frame_dt):
    moving = np.nonzero(np.abs(prog) > 0.01)[0]
    if len(moving) == 0:
        return {}
    i0 = int(moving[0])
    settled = np.nonzero(np.abs(prog - 1) > 0.01)[0]
    i1 = int(settled[-1]) + 1 if len(settled) else len(prog) - 1
    i1 = min(i1, len(prog) - 1)
    vis_start = float(times[max(0, i0 - 1)])
    vis_end = float(times[i1])
    overshoot = max(0.0, float(prog.max()) - 1.0)

    lo = max(0, i0 - 4 - int(0.5 * (i1 - i0)))
    hi = min(len(prog), i1 + max(6, (i1 - i0) // 2))
    tt, pp = times[lo:hi], prog[lo:hi]
    step = frame_dt / 8
    span = max(frame_dt, vis_end - vis_start)
    # Ease-in curves cross the 1% threshold late, so the true start can be well before
    # the first visibly moved frame: search back by up to half the visible span.
    s_rng = (float(times[max(0, i0 - 1)]) - max(frame_dt, 0.5 * span), float(times[i0]) + frame_dt * 0.5)
    d_rng = (span * 0.5, span * 2.6)

    fits = []
    for name, c in NAMED.items():
        e, s, d = fit_timing(tt, pp, bezier_table(*c), s_rng, d_rng, step)
        fits.append({"model": name, "bezier": c, "rmse": e, "start": s, "duration": d})
    fits.sort(key=lambda f: f["rmse"])
    best = fits[0]

    # Refine a free cubic-bezier around the best named curve.
    rng = np.random.default_rng(7)
    c, s, d, e = list(best["bezier"]), best["start"], best["duration"], best["rmse"]
    for it in range(400):
        sc = 0.2 * (1 - it / 400) + 0.01
        cand = [min(1, max(0, c[0] + rng.normal(0, sc))), c[1] + rng.normal(0, sc),
                min(1, max(0, c[2] + rng.normal(0, sc))), c[3] + rng.normal(0, sc)]
        P = (tt - s) / d
        err = float(np.sqrt(((eval_table(bezier_table(*cand, n=512), P) - pp) ** 2).mean()))
        if err < e:
            c, e = cand, err
    e2, s2, d2 = fit_timing(tt, pp, bezier_table(*c), s_rng, d_rng, step)
    refined = {"model": "cubic-bezier", "bezier": tuple(round(v, 3) for v in c), "rmse": e2, "start": s2, "duration": d2}

    out = {"visible_start": round(vis_start, 4), "visible_end": round(vis_end, 4),
           "overshoot_pct": round(overshoot * 100, 2)}
    candidates = [best, refined]
    if overshoot > 0.01 or best["rmse"] > 0.02:
        se, sp = fit_spring(tt, pp, s_rng, step)
        if sp:
            s0, zeta, w0 = sp
            candidates.append({"model": "spring", "rmse": se, "start": s0, "zeta": zeta, "omega": w0,
                               "duration": spring_settle(zeta, w0)})
    # Prefer a named curve unless the alternative is clearly better (keeps reports readable).
    win = best
    for cnd in candidates[1:]:
        if cnd["rmse"] < win["rmse"] * 0.8 - 1e-4:
            win = cnd
    if win["model"] == "spring":
        z, w0 = win["zeta"], win["omega"]
        out.update(curve="spring", klass="spring" + (" with overshoot" if z < 0.99 else " (no overshoot)"),
                   spring={"stiffness": round(w0 * w0, 1), "damping": round(2 * z * w0, 2), "mass": 1,
                           "damping_ratio": round(z, 3), "settle_s": round(win["duration"], 3),
                           "swiftui": {"response": round(2 * math.pi / w0, 3), "dampingFraction": round(z, 3)},
                           "compose": {"dampingRatio": round(z, 3), "stiffness": round(w0 * w0, 1)}})
    else:
        out.update(curve=win["model"] if win["model"] != "cubic-bezier" else "fitted",
                   klass=classify_bezier(win["bezier"]),
                   cubic_bezier="cubic-bezier(%s)" % ", ".join(f"{v:g}" for v in win["bezier"]))
    out.update(start=round(win["start"], 4), duration=round(win["duration"], 4),
               end=round(win["start"] + win["duration"], 4), fit_rmse=round(win["rmse"], 4),
               alternatives=[{"model": f["model"], "rmse": round(f["rmse"], 4)} for f in fits[:4]])
    return out


def parse_box(spec: str, idx: int):
    name, _, rest = spec.rpartition("=")
    vals = [float(v) for v in rest.split(",")]
    if len(vals) != 4:
        raise SystemExit(f"error: --box needs x,y,w,h (got {spec})")
    return (name or f"region{idx + 1}"), vals


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="frames folder from extract_frames.py, or a video / GIF")
    ap.add_argument("--box", action="append", default=[], help="[name=]x,y,w,h in source pixels (repeatable)")
    ap.add_argument("--auto", type=int, default=4, help="find up to K moving regions when no --box is given")
    ap.add_argument("--segment", type=int, default=None, help="1-based segment (between hard cuts)")
    ap.add_argument("--json", help="write the full report (with velocity profiles) here")
    args = ap.parse_args(argv)

    rgb, times, info = load_frames(Path(args.input).expanduser().resolve(), args.segment)
    if len(rgb) < 4:
        raise SystemExit("error: need at least 4 frames")
    G = [gray(a, ANALYSIS_SIDE) for a in rgb]
    k_src = rgb[0].shape[1] / G[0].shape[1]           # analysis px -> source px
    frame_dt = float(np.median(np.diff(times)))

    if args.box:
        regions = []
        for i, b in enumerate(args.box):
            name, (x, y, w, h) = parse_box(b, i)
            regions.append((name, tuple(int(round(v / k_src)) for v in (x, y, w, h))))
    else:
        regions = [(f"auto{i + 1}", b) for i, b in enumerate(auto_regions(G, args.auto))]
        if not regions:
            raise SystemExit("nothing moves in this segment")

    report = {"source": info["source"], "frames": len(rgb), "fps_estimate": round(1 / frame_dt, 3),
              "size": [rgb[0].shape[1], rgb[0].shape[0]], "regions": []}
    for name, box in regions:
        res, prog = analyse_region(G, times, box, k_src, frame_dt)
        entry = {"name": name, "box_px": [round(v * k_src) for v in box], **res}
        if prog is not None:
            entry.update(fit_region(times, prog, frame_dt))
        report["regions"].append(entry)

    timed = [r for r in report["regions"] if "start" in r]
    if len(timed) > 1:
        timed.sort(key=lambda r: r["start"])
        report["stagger"] = [{"from": a["name"], "to": b["name"], "delay_s": round(b["start"] - a["start"], 4)}
                             for a, b in zip(timed, timed[1:])]

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2))
    # Console: the readable part.
    print(f"{Path(info['source']).name}: {report['frames']} frames @ ~{report['fps_estimate']} fps, {report['size'][0]}×{report['size'][1]}")
    for r in report["regions"]:
        if "start" not in r:
            print(f"  {r['name']:<10} {r['kind']}")
            continue
        what = f"{r['travel_px']}px" if r["kind"] == "translate" else r["kind"]
        curve = r.get("cubic_bezier") or ("spring k=%s c=%s ζ=%s" % (r["spring"]["stiffness"], r["spring"]["damping"], r["spring"]["damping_ratio"]))
        print(f"  {r['name']:<10} {what:<16} start {r['start']:.3f}s  dur {r['duration']:.3f}s  "
              f"{r['klass']:<24} {r['curve']:<16} overshoot {r['overshoot_pct']}%  {curve}  rmse {r['fit_rmse']}")
    for s in report.get("stagger", []):
        print(f"  stagger {s['from']} → {s['to']}: {s['delay_s'] * 1000:.0f} ms")


if __name__ == "__main__":
    sys.exit(main())
