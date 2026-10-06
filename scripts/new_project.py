#!/usr/bin/env python3
"""Scaffold a motion project folder from the ui-motion templates.

    python new_project.py <name> [--size 390x844] [--duration 2.4] [--fps 60] [--dir .]
    python new_project.py --refresh <project_dir>     # update the project's motion-runtime.js copy

Creates <dir>/<name>/ with:
  animation.html     starter page wired to motion-runtime.js (seek(t) contract)
  motion-runtime.js  copy of the runtime (projects stay self-contained for rendering)
  motion-spec.md     spec template, pre-filled with stage, duration and fps
  brief.md           brief template
  out/               renders, contact sheets and reports go here
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def fill(text: str, values: dict) -> str:
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scaffold a ui-motion project folder.")
    ap.add_argument("name", nargs="?", help="slug used in copied timestamps, e.g. onboarding-2")
    ap.add_argument("--refresh", metavar="PROJECT", help="copy the current template runtime into an existing project and exit")
    ap.add_argument("--size", default="390x844", help="stage WIDTHxHEIGHT in CSS px (default 390x844)")
    ap.add_argument("--duration", type=float, default=2.4, help="seconds (default 2.4)")
    ap.add_argument("--fps", type=int, default=60, help="frames per second (default 60)")
    ap.add_argument("--dir", default=".", help="parent folder (default: current directory)")
    ap.add_argument("--force", action="store_true", help="overwrite template files in an existing folder")
    args = ap.parse_args(argv)

    if args.refresh:
        proj = Path(args.refresh).expanduser().resolve()
        if not (proj / "animation.html").is_file() and not list(proj.glob("*.html")):
            raise SystemExit(f"error: {proj} has no animation .html")
        shutil.copy2(TEMPLATES / "motion-runtime.js", proj / "motion-runtime.js")
        print(f"refreshed {proj / 'motion-runtime.js'}")
        return
    if not args.name:
        ap.error("name is required (or use --refresh PROJECT)")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.name):
        raise SystemExit("error: name must be a lowercase slug (letters, digits, dashes), e.g. onboarding-2")
    m = re.fullmatch(r"(\d+)x(\d+)", args.size)
    if not m:
        raise SystemExit("error: --size must look like 390x844")
    if args.duration <= 0 or args.fps <= 0:
        raise SystemExit("error: --duration and --fps must be positive")

    dest = Path(args.dir).expanduser().resolve() / args.name
    if dest.exists() and any(dest.iterdir()) and not args.force:
        raise SystemExit(f"error: {dest} exists and is not empty (use --force to overwrite template files)")
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "out").mkdir(exist_ok=True)

    values = {
        "NAME": args.name,
        "WIDTH": m.group(1),
        "HEIGHT": m.group(2),
        "DURATION": f"{args.duration:g}",
        "FPS": args.fps,
    }
    for src, dst in [("animation.html", "animation.html"), ("motion-spec.md", "motion-spec.md"), ("brief.md", "brief.md")]:
        (dest / dst).write_text(fill((TEMPLATES / src).read_text(encoding="utf-8"), values), encoding="utf-8")
    shutil.copy2(TEMPLATES / "motion-runtime.js", dest / "motion-runtime.js")

    print(f"created {dest}")
    print(f"  next: edit {dest / 'motion-spec.md'}, then {dest / 'animation.html'}")
    print(f"  review: python {Path(__file__).parent / 'serve.py'} {dest}")


if __name__ == "__main__":
    sys.exit(main())
