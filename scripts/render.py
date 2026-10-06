#!/usr/bin/env python3
"""Deterministic render of a seek(t) animation.

    python render.py <animation.html|project_dir|url> --format mp4 [options]

Formats
  mp4         H.264, yuv420p, BT.709 TV range, +faststart (universal playback)
  webm-alpha  VP9 with alpha (Chrome, Firefox, Edge)
  hevc-alpha  HEVC with alpha in .mov (Safari / Apple platforms; macOS VideoToolbox only)
  mov-alpha   ProRes 4444 with alpha (hand-off to editors / After Effects)
  png         PNG sequence (RGBA with --alpha)
  gif         palette-optimised GIF (default 25 fps: GIF delays are in 10 ms steps)
  apng        animated PNG (alpha kept)

Quality
  --supersample 2   render at 2x and downsample (sharp text; default 2 for video/gif)
  --motion-blur 8   adaptive subframe blur: up to N subframes on fast frames only,
                    180° shutter, never across a hard cut
Outputs land in <project>/out/<name>-v<version>.<ext> plus a poster PNG.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _capture import Capture, ffmpeg_exe, project_out_dir, run  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

ALPHA_FORMATS = {"webm-alpha", "hevc-alpha", "mov-alpha"}


def even(n: int) -> int:
    return n + (n % 2)


def downsample(img: Image.Image, ss: int) -> Image.Image:
    if ss <= 1:
        return img
    w, h = img.size
    return img.resize((w // ss, h // ss), Image.LANCZOS)


def diff_level(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """(mean abs diff 0..255, fraction of pixels that changed by > 24)."""
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2)
    return float(d.mean()), float((d > 24).mean())


def capture_frame(cap: Capture, t: float, ss: int, blur: int, shutter: float, stats: dict) -> Image.Image:
    base = cap.frame(t)
    if blur <= 1:
        return downsample(base, ss)
    dt = shutter / cap.fps
    t_end = min(cap.duration, t + dt)
    if t_end <= t:
        return downsample(base, ss)
    a = np.asarray(base)
    b = np.asarray(cap.frame(t_end))
    mean, changed = diff_level(a, b)
    if changed > 0.35:
        stats["cuts"] += 1           # hard cut inside the shutter: never blend across it
        return downsample(base, ss)
    # Adaptive: subframes proportional to how much moved, capped at `blur`.
    n = int(min(blur, max(1, round(mean * 4))))
    if n <= 1:
        return downsample(base, ss)
    stats["blurred"] += 1
    acc = a.astype(np.float32)
    for i in range(1, n):
        acc += np.asarray(cap.frame(t + dt * i / n)).astype(np.float32)
    acc /= n
    return downsample(Image.fromarray(acc.round().astype(np.uint8)), ss)


def encode_cmd(fmt: str, w: int, h: int, fps: int, out: Path, ff: str, crf: int | None, gif_fps: int) -> list[str]:
    pix_in = "rgba" if fmt in ALPHA_FORMATS or fmt == "apng" else "rgb24"
    src = [ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", pix_in,
           "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
    pad = f"pad={even(w)}:{even(h)}:0:0:color=black@0"
    if fmt == "mp4":
        return src + ["-vf", f"{pad},scale=out_color_matrix=bt709:out_range=tv,format=yuv420p,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv",
                      "-c:v", "libx264", "-preset", "slow", "-crf", str(crf if crf is not None else 16),
                      "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
                      "-color_trc", "bt709", "-color_range", "tv", "-movflags", "+faststart", str(out)]
    if fmt == "webm-alpha":
        return src + ["-vf", pad, "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0",
                      "-crf", str(crf if crf is not None else 24), "-row-mt", "1", "-auto-alt-ref", "0", str(out)]
    if fmt == "hevc-alpha":
        return src + ["-vf", pad, "-c:v", "hevc_videotoolbox", "-alpha_quality", "0.75", "-q:v", "65",
                      "-tag:v", "hvc1", "-pix_fmt", "bgra", "-movflags", "+faststart", str(out)]
    if fmt == "mov-alpha":
        return src + ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", str(out)]
    if fmt == "apng":
        return src + ["-c:v", "apng", "-plays", "0", "-f", "apng", str(out)]
    if fmt == "gif":
        return src + ["-vf", f"fps={gif_fps},split[a][b];[a]palettegen=stats_mode=diff:max_colors=256[p];[b][p]paletteuse=dither=sierra2_4a:diff_mode=rectangle",
                      "-loop", "0", str(out)]
    raise ValueError(fmt)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="animation .html, project folder, or URL")
    ap.add_argument("--format", "-f", default="mp4", choices=["mp4", "webm-alpha", "hevc-alpha", "mov-alpha", "png", "gif", "apng"])
    ap.add_argument("--out", help="output file (or folder for png)")
    ap.add_argument("--scale", type=float, default=1, help="output pixel density (2 = retina-sized output)")
    ap.add_argument("--supersample", type=int, default=None, help="render at Nx then downsample (default 2 for video/gif, 1 for png)")
    ap.add_argument("--motion-blur", type=int, default=0, metavar="N", help="max subframes for adaptive motion blur (0 = off)")
    ap.add_argument("--shutter", type=float, default=0.5, help="shutter as a fraction of the frame (0.5 = 180°)")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--fps", type=int, default=None, help="override fps (default: the animation's fps)")
    ap.add_argument("--gif-fps", type=int, default=25)
    ap.add_argument("--crf", type=int, default=None)
    ap.add_argument("--alpha", action="store_true", help="transparent background (implied by alpha formats and apng)")
    ap.add_argument("--reduced", action="store_true", help="render the reduced-motion version")
    ap.add_argument("--poster", type=float, default=None, help="poster time in s (default: last frame, or 0 for loops)")
    ap.add_argument("--no-deterministic", action="store_true", help="launch Chromium without the deterministic flags")
    args = ap.parse_args(argv)

    fmt = args.format
    alpha = args.alpha or fmt in ALPHA_FORMATS or fmt == "apng"
    if fmt == "hevc-alpha" and sys.platform != "darwin":
        raise SystemExit("error: hevc-alpha needs macOS VideoToolbox. Use webm-alpha + a mov-alpha master instead.")
    ss = args.supersample if args.supersample is not None else (1 if fmt == "png" else 2)
    t0 = time.time()

    with Capture(args.target, scale=args.scale * ss, reduced=args.reduced, alpha=alpha,
                 deterministic=not args.no_deterministic) as cap:
        m = cap.meta
        fps = args.fps or cap.fps
        if args.fps:
            cap.meta["fps"] = fps
        times = cap.frame_times(args.start, args.end)
        base = f"{m['name']}-v{m['version']}" + ("-reduced" if args.reduced else "")
        out_dir = project_out_dir(args.target)
        ext = {"mp4": ".mp4", "webm-alpha": ".webm", "hevc-alpha": ".mov", "mov-alpha": ".prores.mov", "gif": ".gif", "apng": ".png", "png": ""}[fmt]
        out = Path(args.out) if args.out else out_dir / (base + ext if fmt != "png" else base)
        out.parent.mkdir(parents=True, exist_ok=True)
        stats = {"blurred": 0, "cuts": 0}

        w = int(round(m["width"] * args.scale))
        h = int(round(m["height"] * args.scale))

        if fmt == "png":
            out.mkdir(parents=True, exist_ok=True)
            for i, t in enumerate(times):
                capture_frame(cap, t, ss, args.motion_blur, args.shutter, stats).save(out / f"frame_{i:05d}.png")
        else:
            cmd = encode_cmd(fmt, w, h, fps, out, ffmpeg_exe(), args.crf, min(args.gif_fps, fps))
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                for t in times:
                    img = capture_frame(cap, t, ss, args.motion_blur, args.shutter, stats)
                    if img.size != (w, h):
                        img = img.resize((w, h), Image.LANCZOS)
                    img = img.convert("RGBA" if (alpha or fmt == "apng") else "RGB")
                    proc.stdin.write(img.tobytes())
                proc.stdin.close()
                err = proc.stderr.read().decode(errors="ignore")
                if proc.wait() != 0:
                    raise SystemExit(f"error: ffmpeg failed:\n{err[-2000:]}")
            except BrokenPipeError:
                raise SystemExit("error: ffmpeg exited early:\n" + proc.stderr.read().decode(errors="ignore")[-2000:])

        poster_t = args.poster if args.poster is not None else (0.0 if m.get("loops") else cap.duration)
        poster_dir = (out if fmt == "png" else out.parent) if args.out else out_dir   # next to an explicit --out
        poster = poster_dir / f"{base}-poster.png"
        poster_dir.mkdir(parents=True, exist_ok=True)
        downsample(cap.frame(poster_t), ss).save(poster)

        report = {
            "output": str(out), "poster": str(poster), "format": fmt, "frames": len(times), "fps": fps,
            "size": [w, h], "supersample": ss, "motion_blur": args.motion_blur,
            "blurred_frames": stats["blurred"], "cuts_skipped": stats["cuts"],
            "seconds": round(time.time() - t0, 1), "page_errors": cap.errors,
        }
    print(json.dumps(report, indent=2))
    return 1 if report["page_errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
