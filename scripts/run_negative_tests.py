# -*- coding: utf-8 -*-
"""Real negative tests for the #2267 delivery.

Each case copies the candidate to a throw-away directory, mutates one artifact
(a real deletion/rename, not an empty script), runs the same checker and
asserts that the checker fails with the expected error code.

Exit 0 only if the baseline passes and every mutation is KILLED.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = os.path.join(ROOT, "scripts", "check_delivery.py")
REPORT = os.path.join(ROOT, "artifacts", "negative-report.json")


def run_check(root):
    p = subprocess.run([sys.executable, CHECK, "--root", root],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def fresh_copy(dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(
        "__pycache__", ".git", "negative-*", "acceptance.json", "gate-report.md"))


def mutate_drawio_remove_object(root, obj_id):
    p = os.path.join(root, "diagram", "resource-onboarding-swimlane.drawio")
    tree = ET.parse(p)
    mx = tree.getroot()
    removed = False
    for parent in mx.iter():
        for child in list(parent):
            if child.tag == "object" and child.get("id") == obj_id:
                parent.remove(child)
                removed = True
    if not removed:
        raise RuntimeError(f"object {obj_id} not found")
    tree.write(p, encoding="utf-8", xml_declaration=True)


def mutate_md_row(root, rel, row_prefix, new_line=None):
    p = os.path.join(root, *rel.split("/"))
    lines = open(p, encoding="utf-8").read().splitlines()
    out = []
    hit = 0
    for line in lines:
        if line.startswith("| " + row_prefix) or line.startswith("|" + row_prefix):
            hit += 1
            if new_line is None:
                continue
            line = new_line
        out.append(line)
    if hit != 1:
        raise RuntimeError(f"expected 1 row {row_prefix}, found {hit}")
    open(p, "w", encoding="utf-8").write("\n".join(out) + "\n")


def mutate_drawio_remove_edge(root, edge_id):
    p = os.path.join(root, "diagram", "resource-onboarding-swimlane.drawio")
    tree = ET.parse(p)
    removed = False
    for parent in tree.getroot().iter():
        for child in list(parent):
            if child.tag == "mxCell" and child.get("id") == edge_id:
                parent.remove(child)
                removed = True
    if not removed:
        raise RuntimeError(f"edge {edge_id} not found")
    tree.write(p, encoding="utf-8", xml_declaration=True)


def mutate_svg_text(root, old, new):
    p = os.path.join(root, "diagram", "resource-onboarding-swimlane.svg")
    s = open(p, encoding="utf-8").read()
    if old not in s:
        raise RuntimeError(f"text {old!r} not in svg")
    open(p, "w", encoding="utf-8").write(s.replace(old, new))


CASES = [
    {
        "id": "N1",
        "name": "删除运营泳道",
        "apply": lambda root: mutate_drawio_remove_object(root, "lane-L3"),
        "expect": "E-LANES",
    },
    {
        "id": "N2",
        "name": "把「已暂停」改名为「暂停中」",
        "apply": lambda root: mutate_md_row(root, "docs/state-enum.md", "ST05",
                                            "| ST05 | 暂停中 | `SUSPENDED` | x | x | x | x | x |"),
        "expect": "E-STATES",
    },
    {
        "id": "N3",
        "name": "删除字段 F07（软删除）",
        "apply": lambda root: mutate_md_row(root, "docs/catalog-fields.md", "F07"),
        "expect": "E-FIELDS",
    },
    {
        "id": "N4",
        "name": "删除管理层复核网关",
        "apply": lambda root: mutate_drawio_remove_object(root, "n-g2"),
        "expect": "E-GW-COUNT",
    },
    {
        "id": "N5",
        "name": "删除「有效投诉」触发条件",
        "apply": lambda root: mutate_svg_text(root, "有效投诉", "投诉"),
        "expect": "E-PAUSE-TRIGGER",
    },
    {
        "id": "N6",
        "name": "删除 S15→S14 退出边",
        "apply": lambda root: mutate_drawio_remove_edge(root, "e24"),
        "expect": "E-S15-PATH",
    },
]


def main():
    tmpbase = tempfile.mkdtemp(prefix="c2267-negative-")
    pristine = os.path.join(tmpbase, "pristine")
    fresh_copy(pristine)
    rc, out = run_check(pristine)
    baseline = {
        "command": f"python scripts/check_delivery.py --root <copy>",
        "exit_code": rc,
        "output_tail": out.strip().splitlines()[-3:],
    }
    print(f"[baseline] exit={rc} {'PASS' if rc == 0 else 'FAIL'}")
    if rc != 0:
        print(out)
        print("E-BASELINE: candidate does not pass before mutation; negative tests would be meaningless")
        return 2

    results = []
    for case in CASES:
        work = os.path.join(tmpbase, case["id"])
        fresh_copy(work)
        try:
            case["apply"](work)
        except Exception as e:  # noqa: BLE001
            results.append({"id": case["id"], "name": case["name"], "result": "ERROR",
                            "error": str(e)})
            print(f"[{case['id']}] ERROR {e}")
            continue
        rc, out = run_check(work)
        killed = rc != 0 and case["expect"] in out
        results.append({
            "id": case["id"],
            "name": case["name"],
            "expected_code": case["expect"],
            "exit_code": rc,
            "killed": killed,
            "result": "KILLED" if killed else "SURVIVED",
            "matched_lines": [l for l in out.splitlines() if case["expect"] in l][:3],
        })
        print(f"[{case['id']}] {case['name']}: exit={rc} expect={case['expect']} "
              f"-> {'KILLED' if killed else 'SURVIVED'}")

    killed = sum(1 for r in results if r["result"] == "KILLED")
    report = {
        "baseline": baseline,
        "cases": results,
        "total": len(results),
        "killed": killed,
        "all_killed": killed == len(results),
    }
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")
    shutil.rmtree(tmpbase, ignore_errors=True)

    print(f"negative: {killed}/{len(results)} KILLED")
    return 0 if killed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
