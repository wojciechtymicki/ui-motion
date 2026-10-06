#!/usr/bin/env python3
"""Explode a reference video or GIF into every frame, with real timing.

    python extract_frames.py <video.mp4|.mov|.webm|anim.gif> [--out DIR] [--sheet-cols 8]

Writes to DIR (default <name>_<ext>_frames/, e.g. hero_mp4_frames/):
  frame_00000.png …     every decoded frame (no resampling, no dropped frames)
  frames.json           [{index, file, t, delay}] with t in seconds from the first frame
  sheet_seg01.png …     a contact sheet per segment (up to --sheet-max tiles each)

Timing
  GIF   each frame's own delay from the file. Browsers clamp delays <= 10 ms to
        100 ms; both the file delay and the browser delay are recorded, and t
        follows the browser (what people actually saw). Use --gif-timing file to
        follow the file instead.
  video presentation timestamps (pts) from ffmpeg, so variable frame rate is kept.

Hard cuts are detected (large, near-global change between consecutive frames)
and split the frames into segments: analyse motion inside a segment, never across a cut.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _capture import ffmpeg_exe, run  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageSequence  # noqa: E402


def extract_gif(src: Path, out: Path, timing: str) -> list[dict]:
    im = Image.open(src)
    frames, t = [], 0.0
    for i, fr in enumerate(ImageSequence.Iterator(im)):
        delay = fr.info.get("duration", im.info.get("duration", 100)) or 0
        browser = 100 if delay <= 10 else delay
        name = f"frame_{i:05d}.png"
        fr.convert("RGBA").save(out / name)
        frames.append({"index": i, "file": name, "t": round(t, 6), "delay_ms": delay, "browser_delay_ms": browser})
        t += (browser if timing == "browser" else delay) / 1000
    return frames


def extract_video(src: Path, out: Path) -> list[dict]:
    ff = ffmpeg_exe()
    res = run([ff, "-hide_banner", "-i", str(src), "-map", "0:v:0", "-vf", "showinfo",
               "-fps_mode", "passthrough", "-start_number", "0", str(out / "frame_%05d.png")])
    pts = [float(m.group(1)) for m in re.finditer(r"pts_time:\s*([-\d.]+)", res.stderr.decode(errors="ignore"))]
    files = sorted(out.glob("frame_*.png"))
    if not files:
        raise SystemExit("error: ffmpeg produced no frames")
    if len(pts) != len(files):
        print(f"warning: {len(files)} frames but {len(pts)} timestamps; assuming constant rate", file=sys.stderr)
        rate = re.search(r"(\d+(?:\.\d+)?) fps", res.stderr.decode(errors="ignore"))
        fps = float(rate.group(1)) if rate else 30.0
        pts = [i / fps for i in range(len(files))]
    t0 = pts[0]
    frames = []
    for i, (f, p) in enumerate(zip(files, pts)):
        nxt = pts[i + 1] if i + 1 < len(pts) else None
        frames.append({"index": i, "file": f.name, "t": round(p - t0, 6),
                       "delay_ms": round((nxt - p) * 1000, 3) if nxt is not None else None})
    if frames[-1]["delay_ms"] is None and len(frames) > 1:
        frames[-1]["delay_ms"] = frames[-2]["delay_ms"]
    return frames


def small(path: Path) -> np.ndarray:
    im = Image.open(path).convert("RGB")
    k = 160 / max(im.size)
    return np.asarray(im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.BILINEAR), dtype=np.float32)


def detect_cuts(out: Path, frames: list[dict], thr: float) -> list[int]:
    """Indices i where a cut happens between frame i-1 and i."""
    cuts, prev = [], None
    for fr in frames:
        cur = small(out / fr["file"])
        if prev is not None:
            d = np.abs(cur - prev).max(axis=2)
            changed = float((d > 40).mean())
            hist = np.abs(np.histogram(cur, 32, (0, 255))[0] - np.histogram(prev, 32, (0, 255))[0]).sum() / cur.size
            if changed > thr and hist > 0.25:
                cuts.append(fr["index"])
        prev = cur
    return cuts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="video (mp4, mov, webm, …) or GIF")
    ap.add_argument("--out", help="output folder (default <input>_frames)")
    ap.add_argument("--gif-timing", choices=["browser", "file"], default="browser")
    ap.add_argument("--cut-threshold", type=float, default=0.55, help="fraction of pixels changing for a cut")
    ap.add_argument("--sheet-max", type=int, default=48, help="max tiles per contact sheet (sampled evenly)")
    ap.add_argument("--sheet-cols", type=int, default=8)
    ap.add_argument("--no-sheets", action="store_true")
    args = ap.parse_args(argv)

    src = Path(args.input).expanduser().resolve()
    if not src.is_file():
        raise SystemExit(f"error: {src} not found")
    out = Path(args.out) if args.out else src.with_name(f"{src.stem}_{src.suffix.lstrip('.').lower()}_frames")
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("frame_*.png"):
        old.unlink()

    is_gif = src.suffix.lower() == ".gif"
    frames = extract_gif(src, out, args.gif_timing) if is_gif else extract_video(src, out)
    cuts = detect_cuts(out, frames, args.cut_threshold)
    bounds = [0] + cuts + [len(frames)]
    segments = [{"start": bounds[i], "end": bounds[i + 1] - 1,
                 "t0": frames[bounds[i]]["t"], "t1": frames[bounds[i + 1] - 1]["t"]} for i in range(len(bounds) - 1)]

    delays = [f["browser_delay_ms" if is_gif and args.gif_timing == "browser" else "delay_ms"] for f in frames if f.get("delay_ms") is not None]
    med = float(np.median(delays)) if delays else 0
    info = {
        "source": str(src), "kind": "gif" if is_gif else "video", "frame_count": len(frames),
        "duration": round(frames[-1]["t"] + (delays[-1] if delays else 0) / 1000, 6),
        "fps_estimate": round(1000 / med, 3) if med else None,
        "variable_timing": bool(delays) and (max(delays) - min(delays)) > 1.5,
        "size": list(Image.open(out / frames[0]["file"]).size),
        "cuts": cuts, "segments": segments, "frames": frames,
    }

    if not args.no_sheets:
        from contact_sheet import compose
        for si, seg in enumerate(segments, 1):
            idx = list(range(seg["start"], seg["end"] + 1))
            if len(idx) > args.sheet_max:
                idx = sorted({idx[round(k * (len(idx) - 1) / (args.sheet_max - 1))] for k in range(args.sheet_max)})
            tiles = [(Image.open(out / frames[i]["file"]), f"{frames[i]['t']:.3f}s · #{i}") for i in idx]
            title = f"{src.name} · segment {si}/{len(segments)} · frames {seg['start']}–{seg['end']}"
            sheet = out / f"sheet_seg{si:02d}.png"
            compose(tiles, min(args.sheet_cols, len(tiles)), title, 220).save(sheet)
            seg["sheet"] = sheet.name

    (out / "frames.json").write_text(json.dumps(info, indent=2))
    print(json.dumps({k: v for k, v in info.items() if k != "frames"}, indent=2))
    print(f"frames: {out}")


if __name__ == "__main__":
    sys.exit(main())
