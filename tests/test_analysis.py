#!/usr/bin/env python3
"""Self-test for the capture and analysis scripts (build-order steps 2 and 3).

    python tests/test_analysis.py [--quick]

1. Determinism: two renders of the same second are byte-identical.
2. jank_check: a clean fixture passes; pop / snap / flash / dead fixtures each fail
   with the right issue type.
3. loop_check: a seamless loop passes; a position jump and a velocity reversal fail.
4. measure_motion: a fixture with known timings (ease-out, ease-in-out, spring,
   linear fade) is rendered to MP4 (60 fps) and GIF (25 fps); measured start and
   duration must be within ±1 frame, the curve and spring constants must match.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
FIX = HERE / "fixtures"
PY = sys.executable
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)


def run(script, *args):
    return subprocess.run([PY, str(SCRIPTS / script), *map(str, args)], capture_output=True, text=True)


def main():
    quick = "--quick" in sys.argv
    tmp = Path(tempfile.mkdtemp(prefix="uimotion_test_"))

    # 1. determinism
    digests = []
    for k in range(2):
        out = tmp / f"det{k}"
        r = run("render.py", FIX / "measure.html", "-f", "png", "--start", "0.4", "--end", "0.6", "--out", out)
        digests.append(hashlib.sha1(b"".join(p.read_bytes() for p in sorted(out.glob("*.png")))).hexdigest())
    check("two renders of the same range are identical", digests[0] == digests[1] and r.returncode == 0, digests[0][:12])

    # 2. jank_check
    expect = {"clean": None, "pop": "off-path", "snap": "pop", "flash": "flash", "dead": "dead"}
    for name, typ in expect.items():
        js = tmp / f"jank-{name}.json"
        r = run("jank_check.py", FIX / f"{name}.html", "--json", js)
        issues = json.loads(js.read_text())["issues"]
        if typ is None:
            check(f"jank_check passes {name}", r.returncode == 0 and not issues)
        else:
            check(f"jank_check finds {typ} in {name}", r.returncode == 1 and any(i["type"] == typ for i in issues),
                  ", ".join(i["type"] for i in issues))

    # 3. loop_check
    for name, ok in {"loop-good": True, "loop-jump": False, "loop-kink": False}.items():
        r = run("loop_check.py", FIX / f"{name}.html")
        check(f"loop_check {'passes' if ok else 'fails'} {name}", (r.returncode == 0) == ok, r.stdout.strip().splitlines()[-1])

    # 4. measure_motion against ground truth
    truth = {"A": (0.20, 0.60, "out"), "B": (0.35, 0.70, "inOut"), "D": (0.30, 0.40, "linear")}
    spring_truth = {"start": 0.50, "stiffness": 380, "damping": 20}
    boxes = ["--box", "A=0,16,400,64", "--box", "B=0,104,400,64", "--box", "C=0,192,420,64", "--box", "D=510,280,70,70"]
    cases = [("mp4", 60, ["-f", "mp4"])] + ([] if quick else [("gif", 25, ["-f", "gif", "--fps", "25", "--gif-fps", "25"])])
    for kind, fps, fargs in cases:
        vid = tmp / f"measure.{kind}"
        run("render.py", FIX / "measure.html", *fargs, "--out", vid)
        run("extract_frames.py", vid, "--out", tmp / f"{kind}_frames", "--no-sheets")
        js = tmp / f"measure-{kind}.json"
        r = run("measure_motion.py", tmp / f"{kind}_frames", *boxes, "--json", js)
        if r.returncode != 0:
            check(f"measure_motion runs on {kind}", False, r.stderr[-400:])
            continue
        rep = {x["name"]: x for x in json.loads(js.read_text())["regions"]}
        f = 1 / fps
        for name, (s, d, curve) in truth.items():
            m = rep[name]
            check(f"{kind} {name} start within ±1 frame", abs(m["start"] - s) <= f + 1e-6, f"{m['start']} vs {s}")
            check(f"{kind} {name} duration within ±1 frame", abs(m["duration"] - d) <= f + 1e-6, f"{m['duration']} vs {d}")
            check(f"{kind} {name} curve is {curve}", m["curve"] == curve, m["curve"])
        c = rep["C"]
        sp = c.get("spring") or {}
        check(f"{kind} C classified as spring", c.get("curve") == "spring", c.get("curve"))
        check(f"{kind} C start within ±1 frame", abs(c["start"] - spring_truth["start"]) <= f + 1e-6, c["start"])
        check(f"{kind} C stiffness within 5%", abs(sp.get("stiffness", 0) - 380) / 380 < 0.05, sp.get("stiffness"))
        check(f"{kind} C damping within 10%", abs(sp.get("damping", 0) - 20) / 20 < 0.10, sp.get("damping"))
        st = json.loads(js.read_text()).get("stagger", [])
        check(f"{kind} stagger A→D→B→C order", [x["to"] for x in st] == ["D", "B", "C"], [x["to"] for x in st])

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed  (scratch: {tmp})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
