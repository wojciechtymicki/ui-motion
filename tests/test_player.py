#!/usr/bin/env python3
"""Acceptance test for the review player (build-order step 1).

    python tests/test_player.py [--url http://127.0.0.1:8765/] [--anim path/animation.html]

Needs serve.py running on a project that contains at least one animation.
The auto-reload test touches the animation file (bumps its mtime, content unchanged
except a version comment it adds and then removes).
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

RESULTS: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:8765/")
    ap.add_argument("--anim-file", help="filesystem path of the animation (for the auto-reload test)")
    args = ap.parse_args(argv)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=args.url.rstrip("/"))
        page = ctx.new_page()
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(args.url)
        page.wait_for_function("window.__player && __player.meta.name && document.getElementById('frame').contentWindow.__motion")
        meta = page.evaluate("__player.meta")
        fps, dur, name, ver = meta["fps"], meta["duration"], meta["name"], meta["version"]
        st = lambda: page.evaluate("__player.state")
        clip = lambda: page.evaluate("navigator.clipboard.readText()")
        frame_t = lambda: page.evaluate("document.getElementById('frame').contentWindow.__motion.time()")

        # reset to a known state
        page.evaluate("__player.resetRange(); __player.pause(); __player.seek(0)")
        page.click('#unitsGroup [data-units="s"]')

        # ---------------------------------------------------------- play / pause / stop at every speed
        for sp in ["0.25", "0.5", "0.75", "1"]:
            page.click(f'#speedGroup [data-speed="{sp}"]')
            page.evaluate("__player.seek(0)")
            page.click("#playBtn")
            t0 = time.perf_counter(); page.wait_for_timeout(500); s = st(); el = time.perf_counter() - t0
            expect = float(sp) * el
            check(f"play advances at {sp}x", s["playing"] and abs(s["t"] - expect) < 0.12 + 0.1 * expect, f"t={s['t']:.3f} expected~{expect:.3f}")
            check(f"frame follows player at {sp}x", abs(frame_t() - st()["t"]) < 0.1)
            page.click("#playBtn")
            a = st()["t"]; page.wait_for_timeout(200); b = st()["t"]
            check(f"pause holds at {sp}x", not st()["playing"] and a == b)
        page.click("#playBtn"); page.wait_for_timeout(200)
        page.click("#stopBtn")
        s = st()
        check("stop pauses and returns to start", not s["playing"] and s["t"] == 0)
        page.click('#speedGroup [data-speed="1"]')

        # ---------------------------------------------------------- scrubbing lands on frames
        ruler = page.locator("#ruler").bounding_box()
        y = ruler["y"] + ruler["height"] / 2
        page.mouse.move(ruler["x"] + ruler["width"] * 0.137, y)
        page.mouse.down(); page.mouse.move(ruler["x"] + ruler["width"] * 0.4123, y, steps=6); page.mouse.up()
        t = st()["t"]; f = t * fps
        check("scrub lands on an exact frame", abs(f - round(f)) < 1e-6 and 0.35 * dur < t < 0.45 * dur, f"t={t} frame={f}")
        check("iframe shows the scrubbed time", abs(frame_t() - t) < 1e-9)
        base = round(t * fps)
        page.keyboard.press("ArrowRight"); f1 = st()["t"] * fps
        page.keyboard.press("ArrowRight"); f2 = st()["t"] * fps
        page.keyboard.press("ArrowLeft"); f3 = st()["t"] * fps
        check("→ steps one frame", abs(f1 - (base + 1)) < 1e-6 and abs(f2 - (base + 2)) < 1e-6)
        check("← steps one frame back", abs(f3 - (base + 1)) < 1e-6)
        page.evaluate("__player.seek(0.5)"); page.keyboard.press("Shift+ArrowRight")
        check("Shift+→ jumps 1s", abs(st()["t"] - 1.5) < 1 / fps + 1e-9, str(st()["t"]))
        page.keyboard.press("Shift+ArrowLeft")
        check("Shift+← jumps back 1s", abs(st()["t"] - 0.5) < 1 / fps + 1e-9, str(st()["t"]))

        # knob drag scrubs, knob click copies
        page.evaluate("__player.seek(0.5)")
        kb = page.locator("#knob").bounding_box()
        kx, ky = kb["x"] + kb["width"] / 2, kb["y"] + kb["height"] / 2
        page.mouse.move(kx, ky); page.mouse.down(); page.mouse.move(kx + 120, ky, steps=5); page.mouse.up()
        check("knob drag scrubs", st()["t"] > 0.6, str(st()["t"]))
        page.evaluate("__player.seek(%r)" % (85 / fps))
        kb = page.locator("#knob").bounding_box()
        page.mouse.click(kb["x"] + kb["width"] / 2, kb["y"] + kb["height"] / 2)
        page.wait_for_timeout(100)
        exp = f"{name} v{ver} @ {85 / fps + 1e-9:.2f}s"
        check("knob click copies the time", clip() == exp and st()["t"] == 85 / fps, f"{clip()!r} vs {exp!r}")

        # ---------------------------------------------------------- range lane
        lane = page.locator("#rangeLane").bounding_box()
        ly = lane["y"] + lane["height"] / 2
        X = lambda sec: lane["x"] + lane["width"] * sec / dur
        full = page.evaluate("[document.getElementById('rangeBody').hidden, document.getElementById('rangeBody').style.left, document.getElementById('rangeBody').style.width]")
        check("default selection spans the whole animation", st()["range"] is None and full == [False, "0%", "100%"], str(full))
        check("Reset is disabled for the full-length selection", page.is_disabled("#resetBtn"))
        exp_full = f"{name} v{ver} @ 0.00s–{dur + 1e-9:.2f}s"
        page.click("#rangeBtn"); page.wait_for_timeout(100)
        check("full range copies 0–duration", clip() == exp_full, clip())
        # narrow the default selection with the handles
        ib = page.locator("#inHandle").bounding_box()
        page.mouse.move(ib["x"] + 2, ly); page.mouse.down(); page.mouse.move(X(0.5) + 2, ly, steps=8); page.mouse.up()
        ob = page.locator("#outHandle").bounding_box()
        page.mouse.move(ob["x"] + ob["width"] - 2, ly); page.mouse.down(); page.mouse.move(X(1.2) - 2, ly, steps=8); page.mouse.up()
        r = st()["range"]
        check("dragging the handles narrows the selection", r and abs(r["inT"] - 0.5) < 0.04 and abs(r["outT"] - 1.2) < 0.04, str(r))
        check("Reset becomes active when narrower", page.is_enabled("#resetBtn"))
        check("range edges are on frames", r and all(abs(v * fps - round(v * fps)) < 1e-6 for v in (r["inT"], r["outT"])))
        dim = page.evaluate("document.getElementById('dimBefore').style.width")
        check("outside of range dimmed on ruler", dim != "0" and dim != "0%", dim)
        ib = page.locator("#inHandle").bounding_box()
        page.mouse.move(ib["x"] + 6, ly); page.mouse.down(); page.mouse.move(X(0.3) + 6, ly, steps=6); page.mouse.up()
        r2 = st()["range"]
        check("in handle resizes", abs(r2["inT"] - 0.3) < 0.03 and r2["outT"] == r["outT"], str(r2))
        ob = page.locator("#outHandle").bounding_box()
        page.mouse.move(ob["x"] + 6, ly); page.mouse.down(); page.mouse.move(X(1.0) - 6, ly, steps=6); page.mouse.up()
        r3 = st()["range"]
        check("out handle resizes", abs(r3["outT"] - 1.0) < 0.03 and r3["inT"] == r2["inT"], str(r3))
        bb = page.locator("#rangeBody").bounding_box()
        cx = bb["x"] + bb["width"] / 2
        page.mouse.move(cx, ly); page.mouse.down(); page.mouse.move(cx + (X(0.4) - X(0)), ly, steps=8); page.mouse.up()
        r4 = st()["range"]
        check("body drag moves the range, length kept", abs((r4["outT"] - r4["inT"]) - (r3["outT"] - r3["inT"])) < 1e-6 and abs(r4["inT"] - (r3["inT"] + 0.4)) < 0.03, str(r4))
        bb = page.locator("#rangeBody").bounding_box()
        page.mouse.click(bb["x"] + bb["width"] / 2, ly); page.wait_for_timeout(100)
        exp = f"{name} v{ver} @ {r4['inT'] + 1e-9:.2f}s–{r4['outT'] + 1e-9:.2f}s"
        check("body click copies the range", clip() == exp and st()["range"] == r4, f"{clip()!r} vs {exp!r}")
        page.click("#rangeBtn"); page.wait_for_timeout(100)
        check("range readout copies the range", clip() == exp)

        # playback loops inside range
        page.evaluate("__player.seek(%r)" % r4["inT"])
        if not st()["loop"]: page.click("#loopBtn")
        page.click("#playBtn")
        samples = []
        for _ in range(30):
            page.wait_for_timeout(50); samples.append(st()["t"])
        page.click("#playBtn")
        inside = all(r4["inT"] - 1e-9 <= v <= r4["outT"] + 1e-9 for v in samples)
        wrapped = any(samples[i + 1] < samples[i] for i in range(len(samples) - 1))
        check("playback loops inside the range", inside and wrapped, f"min={min(samples):.3f} max={max(samples):.3f}")
        page.click("#startBtn")
        check("jump-to-start goes to range start", st()["t"] == r4["inT"])
        # loop off: stops at range end
        page.click("#loopBtn"); page.click("#playBtn"); page.wait_for_timeout(int((r4["outT"] - r4["inT"]) * 1000) + 300)
        s = st()
        check("loop off stops at range end", not s["playing"] and abs(s["t"] - r4["outT"]) < 1e-9, str(s["t"]))
        page.click("#loopBtn")

        # ---------------------------------------------------------- copy formats in frames mode
        page.click('#unitsGroup [data-units="f"]')
        page.click("#timeBtn"); page.wait_for_timeout(100)
        fr = int(st()["t"] * fps + 1e-6)
        check("frames mode time copy", clip() == f"{name} v{ver} @ frame {fr} ({fps}fps)", clip())
        page.click("#rangeBtn"); page.wait_for_timeout(100)
        rf = st()["range"]
        exp = f"{name} v{ver} @ frames {int(rf['inT'] * fps + 1e-6)}–{int(rf['outT'] * fps + 1e-6)} ({fps}fps)"
        check("frames mode range copy", clip() == exp, f"{clip()!r} vs {exp!r}")
        txt = page.inner_text("#timeBtn")
        check("frames readout shows fps", f"{fps} fps" in txt, txt)
        check("toast confirms copy", page.locator("#toast").is_visible() and "copied" in page.inner_text("#toast").lower())
        page.click('#unitsGroup [data-units="s"]')
        page.evaluate("__player.seek(%r)" % (85 / fps))
        page.click("#timeBtn"); page.wait_for_timeout(100)
        check("seconds mode time copy", re.fullmatch(re.escape(f"{name} v{ver} @ ") + r"\d+\.\d\ds", clip() or "") is not None, clip())

        # ---------------------------------------------------------- keyboard shortcuts
        page.evaluate("document.activeElement && document.activeElement.blur()")
        page.keyboard.press("r"); check("R resets to the full-length selection", st()["range"] is None and page.is_disabled("#resetBtn"))
        page.evaluate("__player.seek(0.5)"); page.keyboard.press("i")
        page.evaluate("__player.seek(1.5)"); page.keyboard.press("o")
        r = st()["range"]
        check("I / O set the range at the playhead", r and abs(r["inT"] - 0.5) < 1e-9 and abs(r["outT"] - 1.5) < 1e-9, str(r))
        page.keyboard.press("Home"); check("Home goes to range start", st()["t"] == r["inT"])
        page.keyboard.press("End"); check("End goes to range end", st()["t"] == r["outT"])
        lp = st()["loop"]; page.keyboard.press("l"); check("L toggles loop", st()["loop"] != lp); page.keyboard.press("l")
        page.keyboard.press("c"); page.wait_for_timeout(100)
        check("C copies the range when one exists", "–" in (clip() or ""), clip())
        page.keyboard.press("r"); page.keyboard.press("c"); page.wait_for_timeout(100)
        check("C copies the time when no range", "–" not in (clip() or "") and "@" in (clip() or ""), clip())
        page.keyboard.press("Space"); p1 = st()["playing"]; page.keyboard.press("Space"); p2 = st()["playing"]
        check("Space toggles play", p1 and not p2)
        # Space with a focused button must not double-toggle
        page.focus("#loopBtn"); lp = st()["loop"]; page.keyboard.press("Space"); page.wait_for_timeout(50)
        check("Space on a focused button toggles play only", st()["playing"] and st()["loop"] == lp)
        page.keyboard.press("Space")

        # ---------------------------------------------------------- accessibility basics
        missing = page.evaluate("""[...document.querySelectorAll('button')].filter(b => !b.getAttribute('aria-label') && !b.textContent.trim()).length""")
        check("every icon button has a label", missing == 0, str(missing))
        check("toggles expose aria-pressed", page.get_attribute("#loopBtn", "aria-pressed") in ("true", "false") and page.get_attribute("#reducedBtn", "aria-pressed") in ("true", "false"))

        # ---------------------------------------------------------- reduced motion toggle
        page.click("#reducedBtn")
        page.wait_for_function("document.getElementById('frame').src.includes('reduced=1') && document.getElementById('frame').contentWindow.__motion && document.getElementById('frame').contentWindow.__motion.reduced === true")
        check("reduced toggle reloads iframe with ?reduced=1", True)
        page.click("#reducedBtn")
        page.wait_for_function("!document.getElementById('frame').src.includes('reduced=1') && document.getElementById('frame').contentWindow.__motion && document.getElementById('frame').contentWindow.__motion.reduced === false")

        # ---------------------------------------------------------- auto-reload keeps playhead + range
        if args.anim_file:
            path = Path(args.anim_file)
            original = path.read_text(encoding="utf-8")
            page.evaluate("__player.pause(); __player.setRange(0.4, 1.3); __player.seek(0.95)")
            page.click('#speedGroup [data-speed="0.5"]'); page.click('#unitsGroup [data-units="f"]')
            before = st()
            try:
                bumped = re.sub(r"version:\s*(\d+)", lambda m: f"version: {int(m.group(1)) + 1}", original, count=1)
                path.write_text(bumped, encoding="utf-8")
                page.wait_for_function(f"__player.meta.version === {ver + 1}", timeout=5000)
                page.wait_for_timeout(200)
                after = st()
                check("auto-reload picks up the new version", True)
                check("auto-reload keeps playhead, range, speed, units",
                      after["t"] == before["t"] and after["range"] == before["range"] and after["speed"] == 0.5 and after["units"] == "f",
                      f"{before} -> {after}")
                check("iframe re-seeked after reload", abs(frame_t() - before["t"]) < 1e-9)
            finally:
                path.write_text(original, encoding="utf-8")
                page.wait_for_function(f"__player.meta.version === {ver}", timeout=5000)
            page.click('#speedGroup [data-speed="1"]'); page.click('#unitsGroup [data-units="s"]')

        check("no console errors", not errors, "; ".join(errors[:3]))
        page.screenshot(path=str(Path(__file__).parent / "player-screenshot.png"))
        browser.close()

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
