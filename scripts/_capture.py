"""Shared deterministic capture for ui-motion scripts.

Every capture script drives the page through window.__motion.seek(t), the same
function the review player uses, so a frame captured here is the frame the user
saw at that timestamp.

    with Capture("work/onboarding-2/animation.html", scale=1) as cap:
        img = cap.frame(1.2)          # PIL.Image (RGB, or RGBA with alpha=True)
        arr = cap.array(1.2)          # numpy uint8 HxWx3/4

Targets can be a local .html file, a project folder (uses its animation.html),
or an http(s) URL. Local files are served from a private localhost server so
fetch()/fonts behave as they do in the player.
"""
from __future__ import annotations

import functools
import io
import re
import shutil
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

try:
    import numpy as np
    from PIL import Image
    from playwright.sync_api import sync_playwright
except ImportError as e:  # pragma: no cover
    sys.exit(f"error: missing dependency ({e.name}). Install with: pip install playwright numpy pillow imageio-ffmpeg && playwright install chromium")

SKILL_ROOT = Path(__file__).resolve().parent.parent
RUNTIME = SKILL_ROOT / "templates" / "motion-runtime.js"

# Deterministic Chromium: no threaded compositor animations, every compositor
# stage runs before a frame is drawn, fixed colour profile and font hinting.
CHROMIUM_ARGS = [
    "--deterministic-mode",
    "--run-all-compositor-stages-before-draw",
    "--disable-threaded-animation",
    "--disable-threaded-scrolling",
    "--disable-checker-imaging",
    "--disable-new-content-rendering-timeout",
    "--disable-image-animation-resync",
    "--font-render-hinting=none",
    "--force-color-profile=srgb",
    "--hide-scrollbars",
]

SEEK_JS = """async (t) => {
  const m = window.__motion;
  m.seek(t);
  // Two rAFs: the first lets style/layout commit, the second guarantees paint.
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  return m.time();
}"""

PREPARE_JS = """async () => {
  const m = window.__motion;
  await m.ready;
  if (document.fonts) await document.fonts.ready;
  // Freeze any CSS/WAAPI animation so only seek(t) decides the frame.
  for (const a of document.getAnimations()) a.pause();
  const imgs = [...document.images].filter(i => !i.complete);
  await Promise.all(imgs.map(i => new Promise(r => { i.onload = i.onerror = r; })));
  return { name: m.name, version: m.version, duration: m.duration, fps: m.fps,
           width: m.width, height: m.height, loops: m.loops, reduced: m.reduced, holds: m.holds || [],
           runtimeVersion: (window.Motion && window.Motion.runtimeVersion) || 1 };
}"""


def template_runtime_version() -> int:
    m = re.search(r"RUNTIME_VERSION\s*=\s*(\d+)", RUNTIME.read_text(encoding="utf-8"))
    return int(m.group(1)) if m else 1


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        p = urlparse(self.path).path
        if p.endswith("/motion-runtime.js") and not Path(self.translate_path(self.path)).is_file():
            body = RUNTIME.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def resolve_target(target: str) -> tuple[str | None, Path | None, str | None]:
    """Return (url, root_dir, rel_path). For URLs root/rel are None."""
    if re.match(r"^https?://", target):
        return target, None, None
    p = Path(target).expanduser().resolve()
    if p.is_dir():
        p = p / "animation.html"
    if not p.is_file():
        raise SystemExit(f"error: {target} is not a URL, an .html file or a folder with animation.html")
    return None, p.parent, p.name


def with_params(url: str, **params) -> str:
    u = urlparse(url)
    q = dict(parse_qsl(u.query))
    for k, v in params.items():
        if v is None:
            q.pop(k, None)
        else:
            q[k] = str(v)
    return urlunparse(u._replace(query=urlencode(q)))


def project_out_dir(target: str) -> Path:
    """Default output folder: <project>/out for local targets, ./out for URLs."""
    url, root, _ = resolve_target(target)
    return (root / "out") if root else Path.cwd() / "out"


class Capture:
    def __init__(self, target: str, scale: float = 1.0, reduced: bool = False, alpha: bool = False,
                 deterministic: bool = True, headless: bool = True):
        self.target = target
        self.scale = scale
        self.reduced = reduced
        self.alpha = alpha
        self.deterministic = deterministic
        self.headless = headless
        self.meta: dict = {}
        self._server = None

    # ------------------------------------------------------------ lifecycle
    def __enter__(self):
        url, root, rel = resolve_target(self.target)
        if url is None:
            handler = functools.partial(_QuietHandler, directory=str(root))
            self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            threading.Thread(target=self._server.serve_forever, daemon=True).start()
            url = f"http://127.0.0.1:{self._server.server_address[1]}/{rel}"
        self.url = with_params(url, render=1, embed=1, reduced=1 if self.reduced else None)

        self._pw = sync_playwright().start()
        args = CHROMIUM_ARGS if self.deterministic else []
        self._browser = self._pw.chromium.launch(headless=self.headless, args=args)
        self.errors: list[str] = []

        # Probe at 1x to read the stage size, then open the real page at that size.
        probe = self._browser.new_page()
        self._open(probe)
        self.meta = probe.evaluate(PREPARE_JS)
        probe.close()
        tv = template_runtime_version()
        if self.meta.get("runtimeVersion", 1) < tv:
            print(f"warning: this page uses motion-runtime v{self.meta.get('runtimeVersion', 1)}, the skill template is v{tv}. "
                  f"Refresh it: python scripts/new_project.py --refresh <project>", file=sys.stderr)

        self._ctx = self._browser.new_context(
            viewport={"width": int(self.meta["width"]), "height": int(self.meta["height"])},
            device_scale_factor=self.scale,
            reduced_motion="reduce" if self.reduced else "no-preference",
        )
        self.page = self._ctx.new_page()
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.on("console", lambda m: self.errors.append(m.text) if m.type == "error" else None)
        self._open(self.page)
        self.page.evaluate(PREPARE_JS)
        self._stage = self.page.locator("#stage")
        if self._stage.count() == 0:
            self._stage = None
        return self

    def _open(self, page):
        page.goto(self.url, wait_until="load")
        try:
            page.wait_for_function("window.__motion !== undefined", timeout=10000)
        except Exception:
            raise SystemExit(f"error: {self.url} never called Motion.register(...). Does it include motion-runtime.js?")

    def __exit__(self, *exc):
        try:
            self._browser.close()
            self._pw.stop()
        finally:
            if self._server:
                self._server.shutdown()

    # ------------------------------------------------------------ frames
    @property
    def fps(self) -> int:
        return int(self.meta["fps"])

    @property
    def duration(self) -> float:
        return float(self.meta["duration"])

    def seek(self, t: float) -> float:
        return self.page.evaluate(SEEK_JS, float(t))

    def png(self, t: float) -> bytes:
        self.seek(t)
        opts = {"type": "png", "omit_background": self.alpha, "animations": "disabled", "caret": "hide"}
        if self._stage is not None:
            return self._stage.screenshot(**opts)
        return self.page.screenshot(**opts)

    def frame(self, t: float) -> Image.Image:
        img = Image.open(io.BytesIO(self.png(t)))
        return img.convert("RGBA" if self.alpha else "RGB")

    def array(self, t: float) -> np.ndarray:
        return np.asarray(self.frame(t))

    def frame_times(self, start: float = 0.0, end: float | None = None, include_end: bool | None = None) -> list[float]:
        """Frame times i/fps in [start, end). The final frame t=end is included for
        non-looping pieces (it is the resting state) and excluded for loops (it equals frame 0)."""
        end = self.duration if end is None else end
        if include_end is None:
            include_end = not self.meta.get("loops")
        f0 = int(start * self.fps + 1e-6)
        f1 = int(end * self.fps + 1e-6)
        last = f1 if include_end else f1 - 1
        return [i / self.fps for i in range(f0, max(f0, last) + 1)]


def frame_of(t: float, fps: int) -> int:
    return int(t * fps + 1e-6)


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        exe = shutil.which("ffmpeg")
        if not exe:
            raise SystemExit("error: ffmpeg not found. pip install imageio-ffmpeg (or install ffmpeg)")
        return exe


def run(cmd: list[str], **kw):
    res = subprocess.run(cmd, capture_output=True, **kw)
    if res.returncode != 0:
        raise SystemExit("error: command failed:\n  " + " ".join(cmd) + "\n" + res.stderr.decode(errors="ignore")[-2000:])
    return res


PROMPT_RE = re.compile(
    r"(?P<name>[\w.-]+)\s+v(?P<ver>\d+)\s*@\s*(?:"
    r"frames?\s+(?P<f0>\d+)(?:\s*[–-]\s*(?P<f1>\d+))?\s*\((?P<fps>\d+)\s*fps\)"
    r"|(?P<s0>\d+(?:\.\d+)?)s(?:\s*[–-]\s*(?P<s1>\d+(?:\.\d+)?)s)?)"
)


def parse_prompt(text: str) -> dict:
    """Parse a timestamp copied from the player.
    'onboarding-2 v3 @ 1.42s', '… @ 1.20s–2.10s', '… @ frame 85 (60fps)', '… @ frames 72–126 (60fps)'.
    Returns {name, version, start, end|None, frames: bool, fps|None} with times in seconds."""
    m = PROMPT_RE.search(text)
    if not m:
        raise ValueError(f"not a player timestamp: {text!r}")
    d = m.groupdict()
    out = {"name": d["name"], "version": int(d["ver"]), "note": text[m.end():].lstrip(" :—-").strip()}
    if d["f0"] is not None:
        fps = int(d["fps"])
        out.update(frames=True, fps=fps, start=int(d["f0"]) / fps, end=(int(d["f1"]) / fps) if d["f1"] else None,
                   frame_start=int(d["f0"]), frame_end=int(d["f1"]) if d["f1"] else None)
    else:
        out.update(frames=False, fps=None, start=float(d["s0"]), end=float(d["s1"]) if d["s1"] else None)
    return out
