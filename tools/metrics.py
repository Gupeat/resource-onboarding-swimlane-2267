# -*- coding: utf-8 -*-
"""Independently recompute every published count from the artifacts.

This script does not import tools/model.py and does not trust the claims in the
documents: it parses the drawio, SVG, Markdown tables, PNG, PDF and render
report, then compares the result with docs/METRICS.json and with the numbers
written in the document headers.

Output: artifacts/metrics-check.json (+ human summary).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "artifacts", "metrics-check.json")

TYPES = ["客户渠道", "供应商服务", "投资机构", "人才服务", "政策服务", "专家顾问"]
VIS = ["可见", "部分可见", "不可见"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def md_rows(path, prefix):
    rows = []
    for line in open(path, encoding="utf-8").read().splitlines():
        if line.startswith("|") and re.match(r"^\|\s*" + prefix + r"\d+", line):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


def main():
    drawio = os.path.join(ROOT, "diagram", "resource-onboarding-swimlane.drawio")
    svg = os.path.join(ROOT, "diagram", "resource-onboarding-swimlane.svg")
    png = os.path.join(ROOT, "diagram", "resource-onboarding-swimlane.png")
    pdf = os.path.join(ROOT, "diagram", "resource-onboarding-swimlane.pdf")

    droot = ET.parse(drawio).getroot()
    lanes = [o for o in droot.iter("object") if o.get("kind") == "lane"]
    xors = [o for o in droot.iter("object") if o.get("kind") == "xor"]
    steps_drawio = {o.get("step") for o in droot.iter("object") if o.get("step")}

    sroot = ET.parse(svg).getroot()
    ns = "{http://www.w3.org/2000/svg}"
    svg_text = "\n".join("".join(t.itertext()) for t in sroot.iter(ns + "text"))

    step_rows = md_rows(os.path.join(ROOT, "docs", "step-table.md"), "S")
    state_rows = md_rows(os.path.join(ROOT, "docs", "state-enum.md"), "ST")
    field_rows = md_rows(os.path.join(ROOT, "docs", "catalog-fields.md"), "F")

    vis_counts = {v: 0 for v in VIS}
    for r in field_rows:
        if len(r) >= 7:
            v = r[6].replace("*", "").strip()
            if v in vis_counts:
                vis_counts[v] += 1

    with open(png, "rb") as f:
        head = f.read(24)
    png_w, png_h = struct.unpack(">II", head[16:24])
    pdata = open(pdf, "rb").read()
    mb = re.findall(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", pdata)
    pdf_pages = len(re.findall(rb"/Type\s*/Page[^s]", pdata))

    actual = {
        "lanes": len(lanes),
        "lanes_names": [o.get("lane_name") for o in lanes],
        "xor_gateways": len(xors),
        "steps": len(step_rows),
        "steps_drawio": len(steps_drawio),
        "states": len(state_rows),
        "fields": len(field_rows),
        "field_visibility": vis_counts,
        "resource_types": sum(1 for t in TYPES if t in svg_text),
        "types_detail": {t: (t in svg_text) for t in TYPES},
        "png": {"width": png_w, "height": png_h, "bytes": os.path.getsize(png)},
        "pdf": {"pages": pdf_pages,
                "mediabox": [float(mb[0][0]), float(mb[0][1])] if mb else None,
                "bytes": os.path.getsize(pdf)},
        "sha256": {
            "drawio": sha256(drawio),
            "svg": sha256(svg),
            "png": sha256(png),
            "pdf": sha256(pdf),
            "step_table": sha256(os.path.join(ROOT, "docs", "step-table.md")),
            "state_enum": sha256(os.path.join(ROOT, "docs", "state-enum.md")),
            "catalog_fields": sha256(os.path.join(ROOT, "docs", "catalog-fields.md")),
        },
    }

    # claims written in the document headers must match the actual rows
    claims = {}
    cat = open(os.path.join(ROOT, "docs", "catalog-fields.md"), encoding="utf-8").read()
    sta = open(os.path.join(ROOT, "docs", "state-enum.md"), encoding="utf-8").read()
    ste = open(os.path.join(ROOT, "docs", "step-table.md"), encoding="utf-8").read()
    m = re.search(r"字段数量：\*\*(\d+) 个\*\*", cat)
    claims["fields_header"] = int(m.group(1)) if m else None
    m = re.search(r"状态数量：\*\*(\d+) 个\*\*", sta)
    claims["states_header"] = int(m.group(1)) if m else None
    m = re.search(r"步骤：(\d+) 行", ste)
    claims["steps_header"] = int(m.group(1)) if m else None

    expected_path = os.path.join(ROOT, "docs", "METRICS.json")
    declared = json.load(open(expected_path, encoding="utf-8")) if os.path.exists(expected_path) else {}

    checks = []
    for key in ("lanes", "xor_gateways", "steps", "states", "fields", "resource_types"):
        checks.append({"item": f"METRICS.{key}", "declared": declared.get(key),
                       "actual": actual[key], "ok": declared.get(key) == actual[key]})
    checks.append({"item": "steps_drawio==steps_table",
                   "declared": actual["steps"], "actual": actual["steps_drawio"],
                   "ok": actual["steps"] == actual["steps_drawio"]})
    checks.append({"item": "fields_header", "declared": claims["fields_header"],
                   "actual": actual["fields"], "ok": claims["fields_header"] == actual["fields"]})
    checks.append({"item": "states_header", "declared": claims["states_header"],
                   "actual": actual["states"], "ok": claims["states_header"] == actual["states"]})
    checks.append({"item": "steps_header", "declared": claims["steps_header"],
                   "actual": actual["steps"], "ok": claims["steps_header"] == actual["steps"]})
    for k, v in vis_counts.items():
        checks.append({"item": f"visibility.{k}", "declared": declared.get("field_visibility", {}).get(k),
                       "actual": v, "ok": declared.get("field_visibility", {}).get(k) == v})

    matched = sum(1 for c in checks if c["ok"])
    report = {
        "generated_at": "2026-11-25",
        "root": ".",
        "actual": actual,
        "claims": claims,
        "checks": checks,
        "matched": matched,
        "total": len(checks),
        "result": "PASS" if matched == len(checks) else "FAIL",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"numbers: {matched}/{len(checks)} matched")
    for c in checks:
        if not c["ok"]:
            print(f"FAIL {c['item']}: declared={c['declared']} actual={c['actual']}")
    print(f"png={png_w}x{png_h} pdf_pages={pdf_pages} "
          f"lanes={actual['lanes']} xor={actual['xor_gateways']} steps={actual['steps']} "
          f"states={actual['states']} fields={actual['fields']}")
    return 0 if matched == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
