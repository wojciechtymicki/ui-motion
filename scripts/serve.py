#!/usr/bin/env python3
"""Serve a motion project folder together with the review player on one origin.

    python serve.py <project_dir> [--port 8765] [--open]

Routes
  /                 the review player (templates/player/index.html)
  /__player/<file>  player assets
  /__projects       JSON list of animations found in the project
  /__version        JSON hash of project file mtimes (the player polls it to auto-reload)
  /__runtime/motion-runtime.js  the template runtime (fallback if a project has no copy)
  /<anything else>  static files from the project folder, never cached

An "animation" is any .html file under the project that calls Motion.register(.
Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

SKILL_ROOT = Path(__file__).resolve().parent.parent
PLAYER_DIR = SKILL_ROOT / "templates" / "player"
RUNTIME = SKILL_ROOT / "templates" / "motion-runtime.js"
SKIP_DIRS = {"out", "node_modules", ".git", "__pycache__", "frames", ".venv", "renders"}
WATCH_EXT = {".html", ".js", ".css", ".json", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".woff", ".woff2", ".ttf", ".otf", ".lottie", ".riv", ".md"}


def walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(filenames):
            yield Path(dirpath) / name


def find_animations(root: Path) -> list[dict]:
    found = []
    for p in walk(root):
        if p.suffix.lower() != ".html":
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "Motion.register(" not in text:
            continue
        rel = p.relative_to(root).as_posix()
        label = rel[: -len("/animation.html")] if rel.endswith("/animation.html") else rel
        if rel == "animation.html":
            label = root.name
        elif label.endswith(".html"):
            label = label[:-5]
        found.append({"path": rel, "label": label})
    return found


def project_version(root: Path) -> str:
    h = hashlib.sha1()
    for p in walk(root):
        if p.suffix.lower() not in WATCH_EXT:
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        h.update(f"{p.relative_to(root).as_posix()}:{st.st_mtime_ns}:{st.st_size}\n".encode())
    return h.hexdigest()[:16]


def make_handler(root: Path):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(root), **kw)

        def log_message(self, fmt, *args):  # quiet: only errors
            if args and isinstance(args[1], str) and args[1].startswith(("4", "5")):
                sys.stderr.write("[serve] " + (fmt % args) + "\n")

        def end_headers(self):
            self.send_header("Cache-Control", "no-store, max-age=0")
            super().end_headers()

        def _send_json(self, data):
            body = json.dumps(data).encode()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path: Path, ctype: str):
            if not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            body = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = unquote(urlparse(self.path).path)
            if path in ("/", "/index.html", "/__player", "/__player/"):
                return self._send_file(PLAYER_DIR / "index.html", "text/html; charset=utf-8")
            if path.startswith("/__player/"):
                name = path[len("/__player/"):]
                target = (PLAYER_DIR / name).resolve()
                if PLAYER_DIR.resolve() not in target.parents:
                    return self.send_error(HTTPStatus.FORBIDDEN)
                ctype = {".css": "text/css", ".js": "text/javascript", ".html": "text/html"}.get(target.suffix, "application/octet-stream")
                return self._send_file(target, ctype + "; charset=utf-8")
            if path == "/__projects":
                return self._send_json({"root": root.name, "animations": find_animations(root)})
            if path == "/__version":
                return self._send_json({"version": project_version(root)})
            if path == "/__runtime/motion-runtime.js":
                return self._send_file(RUNTIME, "text/javascript; charset=utf-8")
            if path.endswith("/motion-runtime.js") and not (root / path.lstrip("/")).is_file():
                return self._send_file(RUNTIME, "text/javascript; charset=utf-8")
            return super().do_GET()

    return Handler


def free_port(start: int) -> int:
    for port in range(start, start + 30):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # Same option the HTTP server uses, so a port in TIME_WAIT after a restart is reusable.
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SystemExit(f"error: no free port in {start}..{start + 29}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Serve a motion project with the ui-motion review player.")
    ap.add_argument("project_dir", help="folder holding one or more animation .html files")
    ap.add_argument("--port", type=int, default=8765, help="preferred port (next free one is used if taken)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--open", action="store_true", help="open the player in the default browser")
    args = ap.parse_args(argv)

    root = Path(args.project_dir).expanduser().resolve()
    focus = None
    if root.is_file():
        focus, root = root, root.parent
    if not root.is_dir():
        raise SystemExit(f"error: {root} is not a folder")
    if not PLAYER_DIR.is_dir():
        raise SystemExit(f"error: player not found at {PLAYER_DIR}")

    anims = find_animations(root)
    port = free_port(args.port)
    server = ThreadingHTTPServer((args.host, port), make_handler(root))
    url = f"http://{args.host}:{port}/"
    if focus is not None:
        url += "?a=" + focus.relative_to(root).as_posix()
    print(f"ui-motion player: {url}")
    print(f"serving {root} ({len(anims)} animation{'s' if len(anims) != 1 else ''}: {', '.join(a['label'] for a in anims) or 'none yet'})")
    sys.stdout.flush()
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
