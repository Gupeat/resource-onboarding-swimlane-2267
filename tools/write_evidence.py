# -*- coding: utf-8 -*-
"""Generate 03-EVIDENCE.md from machine artifacts. No handwritten counts.

Refuses to write a clean PASS if:
  - acceptance.json is not PASS
  - artifacts/visual-review.json is missing, not PASS, or its PNG hash does not
    match the shipped PNG (i.e. the image was not inspected after the last render)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "artifacts")
OUT = os.path.join(ROOT, "03-EVIDENCE.md")


def load(name, default=None):
    p = os.path.join(ART, name)
    if not os.path.exists(p):
        return default if default is not None else {}
    return json.load(open(p, encoding="utf-8"))


def clean_cmd(cmd):
    """Keep the command semantics, strip local absolute paths from evidence."""
    cmd = str(cmd)
    cmd = re.sub(r"[A-Za-z]:\\[^\s]*?[\\/]python(?:\.exe)?", "python", cmd, flags=re.I)
    cmd = re.sub(r"[A-Za-z]:\\[^\s]*?[\\/]node(?:\.exe)?(?=\s|$)", "node", cmd, flags=re.I)
    cmd = re.sub(r"[A-Za-z]:\\[^\s]*c2267-clean-[^\s]*", "<clean-copy>", cmd)
    cmd = cmd.replace(ROOT, "<repo>")
    return cmd


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def main():
    acc = load("acceptance.json")
    check = load("check-report.json")
    neg = load("negative-report.json")
    num = load("metrics-check.json")
    ren = load("render-report.json")
    vis = load("visual-review.json")

    png = os.path.join(ROOT, "diagram", "resource-onboarding-swimlane.png")
    png_hash = sha256(png) if os.path.exists(png) else ""
    vis_ok = bool(vis) and vis.get("conclusion") == "PASS" and vis.get("image_sha256") == png_hash
    status = acc.get("status", "MISSING")
    ok = status == "PASS" and vis_ok

    lines = []
    lines.append("# 03-EVIDENCE · #2267（S1-BP-025）")
    lines.append("")
    ver = str(acc.get("version", "1.0.0"))
    lines.append(f"- 任务号：2267（S1-BP-025）· 版本：{'v' if not ver.startswith('v') else ''}{ver}")
    lines.append(f"- 生成时间：{acc.get('finished_at', '—')}")
    lines.append(f"- 验收状态：**{status}**")
    lines.append(f"- 证据性质：生产方机器证据 + 生产方目检，**不是独立审核**；最终裁决权在 reviewer。")
    lines.append(f"- 数字来源：`artifacts/acceptance.json`、`check-report.json`、`negative-report.json`、"
                 f"`metrics-check.json`、`render-report.json`；本文件不手写计数。")
    lines.append("")
    if not ok:
        lines.append(f"> **EVIDENCE NOT CLEAN**：acceptance={status}；visual-review={'PASS' if vis_ok else 'MISSING/HASH-MISMATCH'}。")
        lines.append("")

    lines.append("## 1. 环境")
    lines.append("")
    lines.append(f"- Python：{acc.get('python', '—')}")
    lines.append(f"- Node：{acc.get('node', '—')}")
    lines.append(f"- 浏览器：{ren.get('browser_version', '—')}")
    lines.append(f"- 画布：{ren.get('canvas', {}).get('width')} × {ren.get('canvas', {}).get('height')}，"
                 f"scale={ren.get('canvas', {}).get('scale')}")
    lines.append("")

    lines.append("## 2. 验收阶段与真实命令")
    lines.append("")
    lines.append("| 阶段 | 命令 | 退出码 | 耗时(s) | 输出尾部 |")
    lines.append("|---|---|---|---|---|")
    for st in acc.get("stages", []):
        tail = " / ".join(clean_cmd(x) for x in (st.get("output_tail") or [])[-1:]).replace("|", "\\|")
        dur = st.get("duration_s") if st.get("duration_s") is not None else "—"
        lines.append(f"| {st.get('name')} | `{clean_cmd(st.get('command'))}` | {st.get('exit_code')} | "
                     f"{dur} | {tail} |")
    lines.append("")
    c = acc.get("counts", {})
    lines.append(f"- 检查：{c.get('checks_total')} 项，失败 {c.get('checks_failed')}")
    lines.append(f"- 反例：{c.get('negative_killed')} / {c.get('negative_total')} KILLED")
    lines.append(f"- 数字：{c.get('numbers_matched')} / {c.get('numbers_total')} matched")
    lines.append(f"- 渲染：{c.get('render_texts')} 个 text，溢出 {c.get('render_overflow')}")
    lines.append("")

    lines.append("## 3. 结构检查（check_delivery.py）")
    lines.append("")
    lines.append(f"- 断言总数：{check.get('total')}；失败：{check.get('failed')}")
    lines.append("")
    key = {x.get("id"): x for x in check.get("checks", [])}
    key_ids = [
        "lanes.count", "lanes.names", "xor.count", "xor.资质审核.branch.补件",
        "xor.管理层复核.branch.不通过", "states.table.names", "triggers.pause.section",
        "triggers.delist.section", "fields.count", "fields.visibility", "steps.svg.crossref",
        "svg.confirm.kinds", "render.overflow", "png.dimensions", "pdf.text_ops", "hygiene.pii",
    ]
    lines.append("| 断言 | 结果 | 说明 |")
    lines.append("|---|---|---|")
    for k in key_ids:
        x = key.get(k)
        if x:
            lines.append(f"| `{k}` | {'PASS' if x.get('ok') else 'FAIL'} | {x.get('detail', '')} |")
    lines.append("")

    lines.append("## 4. 真实反例（临时副本，工作树不变）")
    lines.append("")
    bl = neg.get("baseline", {})
    lines.append(f"- 基线：exit={bl.get('exit_code')}（{'PASS' if bl.get('exit_code') == 0 else 'FAIL'}）")
    lines.append("")
    lines.append("| 用例 | 篡改 | 期望错误码 | 实际退出码 | 结果 |")
    lines.append("|---|---|---|---|---|")
    for case in neg.get("cases", []):
        lines.append(f"| {case.get('id')} | {case.get('name')} | `{case.get('expected_code')}` | "
                     f"{case.get('exit_code')} | **{case.get('result')}** |")
    lines.append("")

    lines.append("## 5. 数字独立重算（不读 METRICS.json 作为证明）")
    lines.append("")
    lines.append(f"- 结果：{num.get('matched')} / {num.get('total')} matched")
    lines.append("")
    lines.append("| 项目 | 声明 | 实测 | 结果 |")
    lines.append("|---|---|---|---|")
    for x in num.get("checks", []):
        lines.append(f"| {x.get('item')} | {x.get('declared')} | {x.get('actual')} | "
                     f"{'PASS' if x.get('ok') else 'FAIL'} |")
    lines.append("")

    lines.append("## 6. 渲染与目检")
    lines.append("")
    lines.append(f"- 浏览器实测：{ren.get('texts_checked')} 个 text、{ren.get('fit_groups_checked')} 个容器；"
                 f"溢出 {len(ren.get('overflow', []))}，画布外 {len(ren.get('canvas_overflow', []))}。")
    png_info = num.get("actual", {}).get("png", {})
    pdf_info = num.get("actual", {}).get("pdf", {})
    lines.append(f"- PNG：{png_info.get('width')}×{png_info.get('height')}，{png_info.get('bytes')} bytes。")
    lines.append(f"- PDF：{pdf_info.get('pages')} 页，MediaBox={pdf_info.get('mediabox')}，{pdf_info.get('bytes')} bytes。")
    lines.append(f"- 目检锚点：PNG SHA-256 `{png_hash}`；visual-review={'PASS' if vis_ok else 'MISSING/HASH-MISMATCH'}。")
    lines.append("")
    lines.append("| 目检项 | 结果 | 说明 |")
    lines.append("|---|---|---|")
    for x in vis.get("checks", []):
        lines.append(f"| {x.get('item')} | {x.get('result')} | {x.get('note')} |")
    lines.append("")
    lines.append(f"> 目检方法：{vis.get('method', '—')}。目检是生产方自检，不替代 reviewer 的客户视角审核。")
    lines.append("")
    drawio_doc = os.path.join(ROOT, "docs", "drawio-open-check.md")
    if os.path.exists(drawio_doc):
        lines.append("- drawio 实开验证：`docs/drawio-open-check.md`（桌面版 32.7.4；打开/导出 PASS，含 GUI 截图与浅色导出）。")
    else:
        lines.append("- drawio 实开验证：**未提供**（docs/drawio-open-check.md 缺失）。")
    lines.append("")
    lines.append("> 稳定性：PNG 为稳定视觉锚点（渲染确定）；PDF 的 SHA 仅对应本次 Chromium 渲染，重渲染会变，不作为跨次锚点。树哈希含 PDF，仅用于本次候选一致性。")
    lines.append("")

    lines.append("## 7. 文件与 SHA-256")
    lines.append("")
    lines.append("| 文件 | SHA-256 |")
    lines.append("|---|---|")
    for rel, h in acc.get("hashes", {}).items():
        lines.append(f"| `{rel}` | `{h}` |")
    lines.append("")
    lines.append(f"- 树哈希（排除 `artifacts/`）：`{acc.get('tree_hash_excluding_artifacts')}`")
    lines.append("")

    lines.append("## 8. 复跑")
    lines.append("")
    lines.append("```bash")
    lines.append("python tools/build.py")
    lines.append("python tools/import_s1_notes.py")
    lines.append("node tools/render.mjs")
    lines.append("python scripts/check_delivery.py --root . --full")
    lines.append("python scripts/run_negative_tests.py")
    lines.append("python tools/metrics.py")
    lines.append("python scripts/run_acceptance.py")
    lines.append("```")
    lines.append("")

    lines.append("## 9. 未覆盖与已知缺口")
    lines.append("")
    lines.append("- **deadline 已过期**（2026-11-23T15:59:59）：提交窗口需 reviewer/平台确认。")
    lines.append("- **未收到真实访谈纪要/SOP**：S1-INT 仅 mock；`docs/s1-intake-report.md` 明确标注虚构。")
    lines.append("- **评分阈值/有效评价条数/复审周期/整改期限/有效投诉判定人**：待客户确认。")
    lines.append("- **会员评价泳道归属**：按 5 泳道约束放在“会员空间平台”并标注“会员经小程序”；是否加第 6 条泳道待客户确认。")
    lines.append("- **PDF 字节不稳定**：Chromium 每次渲染写入文档 ID，SHA 会变；PDF 的 SHA 不作为跨次稳定锚点，内容与 MediaBox 稳定。")
    lines.append("- **drawio 排版差异**：HTML 标签换行由 draw.io 决定；桌面版泳道标题因 horizontal=0 竖向显示，SVG/PDF 为水平标签带。视觉以 PNG/PDF 为准。")
    lines.append("")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[evidence] status={status} visual={'PASS' if vis_ok else 'FAIL'} -> {OUT}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
