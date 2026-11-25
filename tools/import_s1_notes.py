# -*- coding: utf-8 -*-
"""Validate an S1-INT payload and write docs/s1-intake-report.md.

Usage:
    python tools/import_s1_notes.py
    python tools/import_s1_notes.py --input path/to/notes.json --out docs/s1-intake-report.md

This script does not modify the diagram. If real notes contradict the task text,
the diagram must be revised by a human (edit tools/model.py, rebuild, bump
version, and record the revision source); the task text wins until the client
confirms in writing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_IN = os.path.join(ROOT, "integrations", "s1_int_mock", "fixtures", "fictional-notes.json")
DEFAULT_OUT = os.path.join(ROOT, "docs", "s1-intake-report.md")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def validate(data):
    errors = []
    meta = data.get("meta", {})
    if meta.get("source") != "S1-INT":
        errors.append("meta.source != S1-INT")
    if not isinstance(meta.get("fictional"), bool):
        errors.append("meta.fictional missing")
    for key in ("interviews", "sop_cards"):
        if not isinstance(data.get(key), list):
            errors.append(f"{key} must be a list")
    interviews = data.get("interviews", [])
    for it in interviews:
        for k in ("id", "title", "captured_at", "statements"):
            if not it.get(k):
                errors.append(f"interview {it.get('id', '?')} missing {k}")
        for st in it.get("statements", []):
            for k in ("id", "quote", "requirement_hint"):
                if not st.get(k):
                    errors.append(f"statement {st.get('id', '?')} missing {k}")
            if not re.fullmatch(r"R\d{2}", str(st.get("requirement_hint", ""))):
                errors.append(f"statement {st.get('id', '?')} bad requirement_hint")
    for card in data.get("sop_cards", []):
        for k in ("id", "title", "items", "requirement_hint"):
            if not card.get(k):
                errors.append(f"sop card {card.get('id', '?')} missing {k}")
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=DEFAULT_IN)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    data = json.load(open(args.input, encoding="utf-8"))
    errors = validate(data)
    meta = data.get("meta", {})
    fictional = bool(meta.get("fictional"))
    digest = sha256_file(args.input)

    rows = []
    for it in data.get("interviews", []):
        for st in it.get("statements", []):
            confirmed = "是" if st.get("confirmed") else "待确认"
            note = st.get("note", "")
            rows.append((st["id"], it["id"], st["requirement_hint"], st["quote"], confirmed, note))
    sop_rows = [(c["id"], c["requirement_hint"], "；".join(c["items"])) for c in data.get("sop_cards", [])]

    lines = []
    lines.append("# S1-INT 导入报告（MOCK / 虚构）")
    lines.append("")
    lines.append("- 任务：#2267（S1-BP-025）")
    lines.append("- 生成时间：2026-11-25")
    lines.append(f"- 输入：`{os.path.relpath(args.input, ROOT).replace(os.sep, '/')}`")
    lines.append(f"- 输入 SHA-256：`{digest}`")
    lines.append(f"- 数据性质：**{'虚构（fictional=true）' if fictional else '未声明'}**")
    lines.append("")
    lines.append("> **重要**：本报告由 mock fixture 生成。**未收到真实访谈纪要或 SOP 卡片**；")
    lines.append("> 本报告只验证 S1-INT 接口/schema 可解析，**不得作为客户输入或验收证据**。")
    lines.append("> 真实材料到达后，按第 5 节替换，并逐条标注修订来源。")
    lines.append("")
    if errors:
        lines.append("## 0. 校验结果：FAIL")
        for e in errors:
            lines.append(f"- {e}")
    else:
        lines.append("## 0. 校验结果：PASS（schema 与 requirement_hint 格式）")
    lines.append("")
    lines.append("## 1. 解析计数")
    lines.append("")
    lines.append(f"- 访谈：{len(data.get('interviews', []))} 条")
    lines.append(f"- 陈述：{len(rows)} 条")
    lines.append(f"- SOP 卡片：{len(sop_rows)} 张")
    lines.append("")
    lines.append("## 2. 陈述 → 需求映射")
    lines.append("")
    lines.append("| 陈述 ID | 来源访谈 | 需求 ID | 原文 | 已确认 | 备注 |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        lines.append("| " + " | ".join(str(x) for x in r) + " |")
    lines.append("")
    lines.append("## 3. SOP 卡片")
    lines.append("")
    lines.append("| 卡片 ID | 需求 ID | 条目 |")
    lines.append("|---|---|---|")
    for r in sop_rows:
        lines.append("| " + " | ".join(str(x) for x in r) + " |")
    lines.append("")
    lines.append("## 4. 与当前候选的关系")
    lines.append("")
    lines.append("- 本 fixture 的陈述与任务原文一致的部分：仅用于回归接口解析，不改变图。")
    lines.append("- 标为「待确认」的陈述（补件期限、12 个月复审）：图中已将复审周期标「待客户确认」，补件期限未入图。")
    lines.append("- 未发现与任务原文冲突的陈述；如真实材料冲突，按 AGENT-CONTRACT 优先级（任务原文 > 客户书面澄清 > 竞标承诺 > 假设）处理。")
    lines.append("")
    lines.append("## 5. 真实材料到达后的替换步骤")
    lines.append("")
    lines.append("1. 将真实材料放入 `handoff/client-inputs/`，在 `INPUT-INDEX.csv` 登记（含 sha256、分类、支撑的需求 ID）。")
    lines.append("2. 把真实导出保存为与 fixture 相同 schema 的 JSON（或让 S1-INT 提供同构接口）。")
    lines.append("3. 运行 `python tools/import_s1_notes.py --input <real.json>`，生成本报告的新版本。")
    lines.append("4. 逐条比对：一致的保留；冲突的以任务原文/客户书面澄清为准，修改 `tools/model.py` 并重建。")
    lines.append("5. 升 patch 版本，在图脚注与 `03-EVIDENCE.md` 写「修订来源：S1-INT:<id>#<statement>」。")
    lines.append("")
    lines.append("## 6. 对接点（与 README 一致）")
    lines.append("")
    lines.append("- `GET /api/v1/interviews?project=2267` → `{meta, data:[{id,title,captured_at,statements:[...]}]}`")
    lines.append("- `GET /api/v1/sop-cards?project=2267` → `{meta, data:[{id,title,items,requirement_hint}]}`")
    lines.append("- mock 仅绑定 `127.0.0.1`，端口从 `PORT` 环境变量读取；不访问外网、不读取凭据。")
    lines.append("")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[s1-int] schema errors={len(errors)} statements={len(rows)} sop={len(sop_rows)}")
    print(f"[s1-int] wrote {os.path.relpath(args.out, ROOT)}")
    if errors:
        for e in errors:
            print(" -", e)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
