#!/usr/bin/env python3
"""Contact sheets and frame strips from a seek(t) page.

    python contact_sheet.py <target> --times 0,0.4,1.2
    python contact_sheet.py <target> --range 1.2 2.1 --count 8
    python contact_sheet.py <target> --frames 72,85,126
    python contact_sheet.py <target> --prompt "onboarding-2 v3 @ 1.20s–2.10s: exit feels late"
    python contact_sheet.py <target> --keyframes            # evenly spaced, whole duration

<target> is an animation .html, a project folder or a URL. A --prompt with a
single moment writes that exact frame at full size plus a strip of its
neighbours (±--neighbours frames). Every tile is labelled with time and 0-based
frame number (floor(t*fps), the same rule the player uses).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _capture import Capture, frame_of, parse_prompt, project_out_dir  # noqa: E402

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

BG = (220, 220, 224)
INK = (39, 39, 42)
MUTED = (113, 113, 122)


def font(size: int):
    for name in ["/System/Library/Fonts/SFNSMono.ttf", "/System/Library/Fonts/Menlo.ttc",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "DejaVuSansMono.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def compose(tiles: list[tuple[Image.Image, str]], cols: int, title: str, thumb_w: int) -> Image.Image:
    w0, h0 = tiles[0][0].size
    tw = min(thumb_w, w0)
    th = round(h0 * tw / w0)
    pad, label_h, head = 16, 22, 34
    rows = (len(tiles) + cols - 1) // cols
    W = pad + cols * (tw + pad)
    H = head + rows * (th + label_h + pad) + pad // 2
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    d.text((pad, 10), title, fill=INK, font=font(14))
    f = font(12)
    for i, (img, label) in enumerate(tiles):
        r, c = divmod(i, cols)
        x = pad + c * (tw + pad)
        y = head + r * (th + label_h + pad)
        thumb = img.convert("RGBA").resize((tw, th), Image.LANCZOS)
        checker = Image.new("RGBA", (tw, th), (255, 255, 255, 255))
        checker.alpha_composite(thumb)
        sheet.paste(checker.convert("RGB"), (x, y))
        d.rectangle([x - 1, y - 1, x + tw, y + th], outline=(196, 196, 202))
        d.text((x, y + th + 5), label, fill=MUTED, font=f)
    return sheet


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--times", help="comma-separated seconds")
    g.add_argument("--frames", help="comma-separated 0-based frame numbers")
    g.add_argument("--range", nargs=2, type=float, metavar=("A", "B"), help="seconds; use with --count")
    g.add_argument("--prompt", help="a timestamp/range pasted from the player")
    g.add_argument("--keyframes", action="store_true", help="evenly spaced across the whole duration")
    ap.add_argument("--count", type=int, default=8, help="tiles for --range / --keyframes (default 8)")
    ap.add_argument("--neighbours", type=int, default=2, help="frames either side for a single-moment --prompt")
    ap.add_argument("--cols", type=int, default=None, help="columns (default: one row up to 8 tiles, else 6)")
    ap.add_argument("--thumb", type=int, default=360, help="max tile width in px")
    ap.add_argument("--scale", type=float, default=1, help="capture pixel density")
    ap.add_argument("--reduced", action="store_true")
    ap.add_argument("--out", help="output PNG (default <project>/out/sheet-…png)")
    ap.add_argument("--tag", default="", help="suffix for the default filename, e.g. before / after")
    args = ap.parse_args(argv)

    with Capture(args.target, scale=args.scale, reduced=args.reduced, alpha=False) as cap:
        fps, dur, m = cap.fps, cap.duration, cap.meta
        single = None
        if args.times:
            times = [float(x) for x in args.times.split(",") if x.strip()]
        elif args.frames:
            times = [int(x) / fps for x in args.frames.split(",") if x.strip()]
        elif args.range:
            a, b = args.range
            n = max(2, args.count)
            times = [a + (b - a) * i / (n - 1) for i in range(n)]
        elif args.keyframes:
            n = max(2, args.count)
            times = [dur * i / (n - 1) for i in range(n)]
        else:
            p = parse_prompt(args.prompt)
            if p["name"] != m["name"]:
                print(f"warning: prompt names '{p['name']}' but the page is '{m['name']}'", file=sys.stderr)
            if p["version"] != m["version"]:
                print(f"note: prompt is v{p['version']}, page is v{m['version']} (rendering the current page)", file=sys.stderr)
            if p["fps"] and p["fps"] != fps:
                print(f"warning: prompt fps {p['fps']} differs from page fps {fps}", file=sys.stderr)
            if p["end"] is None:
                single = p["start"]
                f0 = frame_of(single, fps)
                times = [(f0 + k) / fps for k in range(-args.neighbours, args.neighbours + 1) if 0 <= f0 + k <= round(dur * fps)]
            else:
                a, b = p["start"], p["end"]
                n = max(2, args.count)
                # Frame-aligned samples across the range, ends included.
                fa, fb = frame_of(a, fps), frame_of(b, fps)
                idx = sorted({round(fa + (fb - fa) * i / (n - 1)) for i in range(n)})
                times = [i / fps for i in idx]

        times = [min(max(0.0, t), dur) for t in times]
        tiles = []
        for t in times:
            mark = " ◆" if single is not None and frame_of(t, fps) == frame_of(single, fps) else ""
            tiles.append((cap.frame(t), f"{t:.3f}s · f{frame_of(t, fps)}{mark}"))

        out_dir = project_out_dir(args.target)
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = f"sheet-{m['name']}-v{m['version']}-f{frame_of(times[0], fps)}-{frame_of(times[-1], fps)}"
        if args.reduced:
            stem += "-reduced"
        if args.tag:
            stem += "-" + args.tag
        out = Path(args.out) if args.out else out_dir / f"{stem}.png"
        cols = args.cols or (len(tiles) if len(tiles) <= 8 else 6)
        title = f"{m['name']} v{m['version']}  ·  {m['width']}×{m['height']}  ·  {fps} fps" + ("  ·  reduced" if args.reduced else "")
        compose(tiles, cols, title, args.thumb).save(out)
        result = {"sheet": str(out), "times": [round(t, 4) for t in times], "frames": [frame_of(t, fps) for t in times]}

        if single is not None:
            exact = out_dir / f"frame-{m['name']}-v{m['version']}-f{frame_of(single, fps)}{('-' + args.tag) if args.tag else ''}.png"
            cap.frame(frame_of(single, fps) / fps if args.prompt and parse_prompt(args.prompt)["frames"] else single).save(exact)
            result["frame"] = str(exact)
        result["page_errors"] = cap.errors
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    sys.exit(main())
