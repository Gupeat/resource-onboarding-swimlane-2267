# -*- coding: utf-8 -*-
"""FAIL-first acceptance wrapper for the #2267 candidate.

It deletes the previous verdict, writes RUNNING, then re-runs the whole pipeline
from the current tree. A PASS is written only if every stage exits 0 and the
clean-copy check passes.

Stages:
  1 build      python tools/build.py
  2 s1-int     python tools/import_s1_notes.py
  3 render     node tools/render.mjs
  4 check      python scripts/check_delivery.py --full --json artifacts/check-report.json
  5 negative   python scripts/run_negative_tests.py
  6 numbers    python tools/metrics.py
  7 clean      copy repo to a temp dir, run check --full there
  8 mock       start S1-INT mock on 127.0.0.1, GET interviews, stop
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "artifacts")
VERDICT = os.path.join(ART, "acceptance.json")
OUTPUTS = [
    "diagram/resource-onboarding-swimlane.drawio",
    "diagram/resource-onboarding-swimlane.svg",
    "diagram/resource-onboarding-swimlane.png",
    "diagram/resource-onboarding-swimlane.pdf",
    "docs/step-table.md",
    "docs/state-enum.md",
    "docs/catalog-fields.md",
    "docs/s1-intake-report.md",
    "docs/METRICS.json",
    "README.md",
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def tree_hash(root):
    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in {".git", "__pycache__", "node_modules", ".venv", "venv"})
        for fn in sorted(filenames):
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            if rel.startswith("artifacts/"):
                continue
            entries.append(f"{rel}\0{sha256(p)}")
    return hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()


def clean_text(s):
    s = str(s).replace(ROOT, "<repo>")
    s = re.sub(r"[A-Za-z]:\\[^\s]*c2267-clean-[^\s]*", "<clean-copy>", s)
    s = re.sub(r"[A-Za-z]:\\[^\s]*", "<path>", s)
    return s


def display_cmd(cmd):
    out = []
    for i, part in enumerate(cmd):
        if i == 0:
            base = os.path.basename(str(part)).lower()
            if "python" in base:
                out.append("python")
            elif "node" in base:
                out.append("node")
            else:
                out.append(str(part))
        else:
            out.append(clean_text(part))
    return " ".join(out)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def run_stage(name, cmd, timeout=600, env=None):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, env=env)
        rc, out = p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        rc, out = 124, f"timeout after {timeout}s: {e}"
    except FileNotFoundError as e:
        rc, out = 127, f"command not found: {e}"
    dur = round(time.time() - t0, 2)
    raw_tail = out.strip().splitlines()[-8:]
    tail = [clean_text(x) for x in raw_tail]
    print(f"[{name}] exit={rc} {dur}s")
    for line in tail:
        print("   ", line)
    return {"name": name, "command": display_cmd(cmd), "exit_code": rc,
            "duration_s": dur, "output_tail": tail}


def main():
    os.makedirs(ART, exist_ok=True)
    if os.path.exists(VERDICT):
        os.remove(VERDICT)
    running = {
        "task_id": "2267",
        "version": "1.0.0",
        "status": "RUNNING",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "note": "FAIL-first wrapper: no PASS is written until every stage succeeds.",
        "stages": [],
    }
    with open(VERDICT, "w", encoding="utf-8") as f:
        json.dump(running, f, ensure_ascii=False, indent=2)
        f.write("\n")

    node = shutil.which("node")
    stages = [
        run_stage("build", [sys.executable, "tools/build.py"]),
        run_stage("s1-int", [sys.executable, "tools/import_s1_notes.py"]),
        run_stage("render", [node or "node", "tools/render.mjs"]),
        run_stage("check", [sys.executable, "scripts/check_delivery.py", "--root", ".",
                            "--full", "--json", "artifacts/check-report.json"]),
        run_stage("negative", [sys.executable, "scripts/run_negative_tests.py"]),
        run_stage("numbers", [sys.executable, "tools/metrics.py"]),
    ]

    # 7) clean copy: everything except artifacts/ and caches; check --full there
    tmp = tempfile.mkdtemp(prefix="c2267-clean-")
    clean = os.path.join(tmp, "repo")
    try:
        shutil.copytree(ROOT, clean, ignore=shutil.ignore_patterns(
            ".git", "__pycache__", "node_modules", ".venv", "venv", "artifacts"))
        # the clean copy needs the render report + acceptance-independent artifacts
        shutil.copytree(os.path.join(ART), os.path.join(clean, "artifacts"),
                        dirs_exist_ok=True, ignore=shutil.ignore_patterns("acceptance.json", "candidate.zip"))
        st = run_stage("clean-copy", [sys.executable, "scripts/check_delivery.py",
                                      "--root", clean, "--full"])
        stages.append(st)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # 8) S1-INT mock smoke test
    port = free_port()
    env = dict(os.environ, PORT=str(port), S1INT_VERBOSE="")
    proc = subprocess.Popen([sys.executable, "integrations/s1_int_mock/mock_server.py"],
                            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    mock_ok = False
    mock_detail = ""
    try:
        url = f"http://127.0.0.1:{port}/healthz"
        for _ in range(40):
            try:
                with urllib.request.urlopen(url, timeout=0.5) as r:
                    mock_ok = r.status == 200
                    break
            except Exception:
                time.sleep(0.1)
        if mock_ok:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/interviews?project=2267", timeout=2) as r:
                body = json.load(r)
                mock_ok = r.status == 200 and body.get("meta", {}).get("fictional") is True and len(body.get("data", [])) == 3
                mock_detail = f"http=200 fictional={body.get('meta', {}).get('fictional')} interviews={len(body.get('data', []))}"
    except Exception as e:  # noqa: BLE001
        mock_detail = repr(e)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
    print(f"[mock] {'PASS' if mock_ok else 'FAIL'} {mock_detail}")
    stages.append({"name": "mock", "command": "python integrations/s1_int_mock/mock_server.py + GET",
                   "exit_code": 0 if mock_ok else 1, "duration_s": None,
                   "output_tail": [mock_detail]})

    # collapse the verdict
    failed = [s for s in stages if s["exit_code"] != 0]
    status = "PASS" if not failed else "FAIL"

    check = json.load(open(os.path.join(ART, "check-report.json"), encoding="utf-8")) if os.path.exists(os.path.join(ART, "check-report.json")) else {}
    neg = json.load(open(os.path.join(ART, "negative-report.json"), encoding="utf-8")) if os.path.exists(os.path.join(ART, "negative-report.json")) else {}
    num = json.load(open(os.path.join(ART, "metrics-check.json"), encoding="utf-8")) if os.path.exists(os.path.join(ART, "metrics-check.json")) else {}
    ren = json.load(open(os.path.join(ART, "render-report.json"), encoding="utf-8")) if os.path.exists(os.path.join(ART, "render-report.json")) else {}

    verdict = {
        "task_id": "2267",
        "task_code": "S1-BP-025",
        "version": "1.0.0",
        "status": status,
        "started_at": running["started_at"],
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "python": sys.version.split()[0],
        "node": subprocess.run([node or "node", "--version"], capture_output=True, text=True).stdout.strip() if node else None,
        "stages": stages,
        "counts": {
            "checks_total": check.get("total"),
            "checks_failed": check.get("failed"),
            "negative_killed": neg.get("killed"),
            "negative_total": neg.get("total"),
            "numbers_matched": num.get("matched"),
            "numbers_total": num.get("total"),
            "render_texts": ren.get("texts_checked"),
            "render_overflow": len(ren.get("overflow", [])),
            "lanes": num.get("actual", {}).get("lanes"),
            "xor_gateways": num.get("actual", {}).get("xor_gateways"),
            "steps": num.get("actual", {}).get("steps"),
            "states": num.get("actual", {}).get("states"),
            "fields": num.get("actual", {}).get("fields"),
            "resource_types": num.get("actual", {}).get("resource_types"),
            "png": num.get("actual", {}).get("png"),
            "pdf": num.get("actual", {}).get("pdf"),
        },
        "hashes": {rel: sha256(os.path.join(ROOT, rel)) for rel in OUTPUTS if os.path.exists(os.path.join(ROOT, rel))},
        "tree_hash_excluding_artifacts": tree_hash(ROOT),
    }
    with open(VERDICT, "w", encoding="utf-8") as f:
        json.dump(verdict, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # 9) evidence projection: only after a clean run; regenerate hashes afterwards
    if status == "PASS":
        ev = run_stage("evidence", [sys.executable, "tools/write_evidence.py"])
        stages.append(ev)
        if ev["exit_code"] != 0:
            status = "FAIL"
        verdict["status"] = status
        verdict["stages"] = stages
        verdict["hashes"] = {rel: sha256(os.path.join(ROOT, rel)) for rel in OUTPUTS if os.path.exists(os.path.join(ROOT, rel))}
        verdict["tree_hash_excluding_artifacts"] = tree_hash(ROOT)
        with open(VERDICT, "w", encoding="utf-8") as f:
            json.dump(verdict, f, ensure_ascii=False, indent=2)
            f.write("\n")

    print(f"\nACCEPTANCE: {status}  ({len([s for s in stages if s['exit_code'] != 0])} failed stage(s))")
    if failed:
        for s in failed:
            print(f"  FAILED {s['name']}: {s['output_tail'][-1] if s['output_tail'] else ''}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
