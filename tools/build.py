# -*- coding: utf-8 -*-
"""Build the #2267 swimlane deliverables from tools/model.py.

Outputs (paths relative to repo/):
  diagram/resource-onboarding-swimlane.svg
  diagram/resource-onboarding-swimlane.drawio
  docs/step-table.md
  docs/state-enum.md
  docs/catalog-fields.md
  docs/METRICS.json
  artifacts/render.html

No third-party dependencies.
"""

from __future__ import annotations

import html
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_NAME = "resource-onboarding-swimlane"

FONT = "Microsoft YaHei, PingFang SC, Noto Sans CJK SC, Source Han Sans SC, sans-serif"


# ---------------------------------------------------------------------------
# text metrics (conservative estimate; the browser measurement is the truth)
# ---------------------------------------------------------------------------

_CJK_PUNCT = "，。；：、（）【】「」『』…—·《》！？"


def char_w(ch: str, size: float) -> float:
    if "\u4e00" <= ch <= "\u9fff" or ch in _CJK_PUNCT:
        return size
    if ch == " ":
        return size * 0.28
    if ch in "ilI.,:;|!'()[]":
        return size * 0.28
    if ch in "mwMW@#%&":
        return size * 0.86
    if ch.isupper():
        return size * 0.66
    if ch.isdigit():
        return size * 0.56
    return size * 0.53


def text_w(s: str, size: float, bold: bool = False) -> float:
    w = sum(char_w(c, size) for c in s)
    return w * (1.04 if bold else 1.0)


def wrap(text: str, max_w: float, size: float, bold: bool = False) -> list[str]:
    """Wrap Chinese/Latin mixed text. Explicit \n is honoured."""
    out: list[str] = []
    for hard in str(text).split("\n"):
        if hard == "":
            out.append("")
            continue
        tokens: list[str] = []
        buf = ""
        for ch in hard:
            if "\u4e00" <= ch <= "\u9fff" or ch in _CJK_PUNCT:
                if buf:
                    tokens.append(buf)
                    buf = ""
                tokens.append(ch)
            elif ch == " ":
                if buf:
                    tokens.append(buf)
                    buf = ""
                tokens.append(" ")
            else:
                buf += ch
        if buf:
            tokens.append(buf)

        line = ""
        for tok in tokens:
            candidate = line + tok
            if text_w(candidate.rstrip(), size, bold) <= max_w or not line:
                line = candidate
            else:
                out.append(line.rstrip())
                line = tok.lstrip() if tok == " " else tok
        if line.strip() or not out:
            out.append(line.rstrip())
    return out


def esc(s: str) -> str:
    return html.escape(str(s), quote=False)


def attr(s: str) -> str:
    return html.escape(str(s), quote=True)


# ---------------------------------------------------------------------------
# SVG primitives
# ---------------------------------------------------------------------------

def svg_text(x, y, s, size, fill, weight="400", anchor="start", family=FONT,
             opacity=None, ls=None, cls="", extra=""):
    op = f' opacity="{opacity}"' if opacity is not None else ""
    lsp = f' letter-spacing="{ls}"' if ls is not None else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{op}{lsp} '
            f'class="{cls}"{extra}>{esc(s)}</text>')


def svg_lines(x, y, lines, size, fill, lh, weight="400", anchor="start",
              family=FONT, opacity=None):
    out = [f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" '
           f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"'
           + (f' opacity="{opacity}"' if opacity is not None else "") + ">"]
    for i, line in enumerate(lines):
        dy = 0 if i == 0 else lh
        out.append(f'<tspan x="{x:.1f}" dy="{dy}">{esc(line)}</tspan>')
    out.append("</text>")
    return "".join(out)


def rounded_path(points, r=9.0):
    pts = [(float(x), float(y)) for x, y in points]
    if len(pts) == 2:
        return f"M {pts[0][0]:.1f} {pts[0][1]:.1f} L {pts[1][0]:.1f} {pts[1][1]:.1f}"
    d = [f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"]
    for i in range(1, len(pts) - 1):
        p0, p1, p2 = pts[i - 1], pts[i], pts[i + 1]
        v1 = (p1[0] - p0[0], p1[1] - p0[1])
        v2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1 = max((v1[0] ** 2 + v1[1] ** 2) ** 0.5, 1e-6)
        l2 = max((v2[0] ** 2 + v2[1] ** 2) ** 0.5, 1e-6)
        rr = min(r, l1 / 2.0, l2 / 2.0)
        a = (p1[0] - v1[0] / l1 * rr, p1[1] - v1[1] / l1 * rr)
        b = (p1[0] + v2[0] / l2 * rr, p1[1] + v2[1] / l2 * rr)
        d.append(f"L {a[0]:.1f} {a[1]:.1f}")
        d.append(f"Q {p1[0]:.1f} {p1[1]:.1f} {b[0]:.1f} {b[1]:.1f}")
    d.append(f"L {pts[-1][0]:.1f} {pts[-1][1]:.1f}")
    return " ".join(d)


def state_palette(name):
    return {
        "已上架": ("#EAF3EC", "#BFD8C6", "#2F6F4E", "#2F6F4E"),
        "已暂停": ("#FBF1E0", "#E6CD9D", "#8A5A1B", "#9A6A1E"),
        "已下架": ("#EEF0F3", "#CBD2DB", "#4B5563", "#4B5563"),
        "已拒绝": ("#FBEAE8", "#E7C0BB", "#A03C33", "#B4453C"),
    }.get(name, ("#EEF2F7", "#C9D2DF", "#364152", "#5B6779"))


def node_by_id(nid):
    for n in M.NODES:
        if n["id"] == nid:
            return n
    raise KeyError(nid)


def lane_by_id(lid):
    for l in M.LANES:
        if l["id"] == lid:
            return l
    raise KeyError(lid)


# ---------------------------------------------------------------------------
# SVG build
# ---------------------------------------------------------------------------

def build_svg() -> str:
    W, H = M.CANVAS_W, M.CANVAS_H
    C = M.COLORS
    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-labelledby="doc-title" '
        f'font-family="{FONT}">'
    )
    out.append(f'<title id="doc-title">{esc(M.DOC_TITLE)} · 流程泳道图</title>')
    out.append("<defs>")
    for mid, color in (("ink", "#52606F"), ("amber", C["exception"]),
                       ("green", C["loop"]), ("gray", C["assoc"])):
        out.append(
            f'<marker id="arrow-{mid}" viewBox="0 0 8 8" refX="7.4" refY="4" '
            f'markerWidth="8" markerHeight="8" orient="auto" markerUnits="strokeWidth">'
            f'<path d="M 0 0 L 8 4 L 0 8 z" fill="{color}"/></marker>'
        )
    out.append("</defs>")
    out.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#FFFFFF"/>')

    # ---- header ----
    out.append(f'<rect x="0" y="0" width="{W}" height="5" fill="{C["ink"]}"/>')
    out.append(svg_text(70, 46,
                        "S1-BP-025 · Stage i 蓝图与命名 · 业务蓝图与流程图",
                        10.5, C["muted"], weight="600", ls="1.1"))
    out.append(svg_text(70, 90, M.DOC_TITLE, 31, C["ink"], weight="700"))
    out.append(svg_text(70, 119, M.DOC_SUBTITLE, 12.2, C["muted"]))
    out.append(svg_text(2930, 52, f"任务 #{M.TASK_ID} · 文档 S1-BP-025-D01 · v{M.VERSION}",
                        10.4, C["body"], weight="600", anchor="end"))
    out.append(svg_text(2930, 72, f"生成日期 {M.GENERATED_ON} · 页面 A2 横向", 9.4,
                        C["muted"], anchor="end"))
    # data notice badge
    out.append(f'<rect x="2582" y="88" width="348" height="24" rx="12" fill="#FFF7ED" stroke="#E9C9A6"/>')
    out.append(f'<circle cx="2598" cy="100" r="3.4" fill="{C["exception"]}"/>')
    out.append(svg_text(2608, 104, "全部为虚构示例 · 不含客户名称与真实信息", 9.2,
                        "#8A5A2B", weight="600"))
    out.append(f'<line x1="70" y1="140" x2="2930" y2="140" stroke="{C["hair"]}" stroke-width="1"/>')

    # ---- lanes ----
    for idx, lane in enumerate(M.LANES):
        top = M.LANE_TOPS[idx]
        accent = lane["accent"]
        out.append(f'<g class="lane" data-lane="{lane["id"]}" data-name="{attr(lane["name"])}">')
        out.append(f'<rect id="lane-{lane["id"]}-box" x="{M.LANE_X}" y="{top}" '
                   f'width="{M.LANE_W}" height="{M.LANE_H}" fill="'
                   + ("#FFFFFF" if idx % 2 == 0 else "#FCFDFF") +
                   f'" stroke="{C["hair_soft"]}" stroke-width="1"/>')
        out.append(f'<rect x="{M.LANE_X}" y="{top}" width="{M.LANE_LABEL_W}" height="{M.LANE_H}" '
                   f'fill="{accent}" fill-opacity="0.075"/>')
        out.append(f'<rect x="{M.LANE_X}" y="{top}" width="4" height="{M.LANE_H}" fill="{accent}"/>')
        out.append(f'<line x1="{M.LANE_X + M.LANE_LABEL_W}" y1="{top}" '
                   f'x2="{M.LANE_X + M.LANE_LABEL_W}" y2="{top + M.LANE_H}" '
                   f'stroke="{C["hair_soft"]}" stroke-width="1"/>')
        out.append(f'<g data-fit="lane-{lane["id"]}-box">')
        out.append(svg_text(M.LANE_X + 22, top + 34, lane["no"], 9.5, accent,
                            weight="700", ls="1.4"))
        out.append(svg_text(M.LANE_X + 22, top + 64, lane["name"], 16.5, C["ink"], weight="700"))
        sub_lines = lane["sub"].split("\n")
        out.append(svg_lines(M.LANE_X + 22, top + 88, sub_lines, 9.3, C["muted"], 14.5))
        out.append("</g>")
        out.append("</g>")

    # ---- edges ----
    out.append('<g class="edges">')
    for e in M.EDGES:
        kind = e["kind"]
        if kind == "exception":
            color, dash, marker = C["exception"], "", "amber"
        elif kind == "loop":
            color, dash, marker = C["loop"], ' stroke-dasharray="6 4"', "green"
        elif kind == "assoc":
            color, dash, marker = C["assoc"], ' stroke-dasharray="2 3"', None
        else:
            color, dash, marker = "#52606F", "", "ink"
        m = f' marker-end="url(#arrow-{marker})"' if marker else ""
        out.append(
            f'<path d="{rounded_path(e["points"])}" fill="none" stroke="{color}" '
            f'stroke-width="{1.1 if kind == "assoc" else 1.45}" stroke-linecap="round" '
            f'stroke-linejoin="round"{dash}{m} class="edge" data-edge="{e["id"]}" '
            f'data-kind="{kind}"/>'
        )
    out.append("</g>")

    # ---- nodes ----
    out.append('<g class="nodes">')
    for n in M.NODES:
        kind = n["kind"]
        lane = lane_by_id(n["lane"])
        accent = lane["accent"]
        common = (f'class="node {kind}" data-kind="{kind}" data-node="{n["id"]}" '
                  f'data-lane="{n["lane"]}"'
                  + (f' data-step="{n["step"]}"' if n.get("step") else "")
                  + (f' data-state="{attr(n["state"])}"' if n.get("state") else ""))
        out.append(f'<g {common}>')

        if kind == "start":
            cx, cy, r = n["cx"], n["cy"], n["r"]
            out.append(f'<circle id="node-{n["id"]}-box" cx="{cx}" cy="{cy}" r="{r}" '
                       f'fill="#FFFFFF" stroke="{accent}" stroke-width="3"/>')
            out.append(f'<circle cx="{cx}" cy="{cy}" r="4.2" fill="{accent}"/>')
            out.append(svg_text(cx + 14, cy - 24, n["label"], 9.6, C["body"],
                                weight="600", anchor="middle"))
            out.append(svg_text(cx + 20, cy + 18, n["step"], 8.2, C["faint"],
                                weight="700", ls="0.6"))
        elif kind == "process":
            x, y, w, h = n["x"], n["y"], n["w"], n["h"]
            out.append(f'<rect id="node-{n["id"]}-box" x="{x}" y="{y}" width="{w}" height="{h}" '
                       f'rx="12" fill="#FFFFFF" stroke="{C["hair"]}" stroke-width="1.2"/>')
            out.append(f'<rect x="{x}" y="{y + 12}" width="3.4" height="{h - 24}" rx="1.7" fill="{accent}" opacity="0.85"/>')
            lines = wrap(n["title"], w - 34, 13.2, bold=True)
            out.append(f'<g data-fit="node-{n["id"]}-box">')
            out.append(svg_lines(x + 16, y + 33, lines, 13.2, C["ink"], 17, weight="700"))
            sub_lines = wrap(n["sub"], w - 32, 9.8)
            out.append(svg_lines(x + 16, y + 33 + 17 * len(lines) + 5, sub_lines, 9.8,
                                 C["muted"], 13.6))
            out.append("</g>")
            out.append(svg_text(x + w - 10, y + 14, n["step"], 8.2, C["faint"],
                                weight="700", anchor="end", ls="0.6"))
        elif kind == "xor":
            cx, cy, w, h = n["cx"], n["cy"], n["w"], n["h"]
            pts = f"{cx},{cy - h/2} {cx + w/2},{cy} {cx},{cy + h/2} {cx - w/2},{cy}"
            out.append(f'<polygon id="node-{n["id"]}-box" points="{pts}" fill="#FFFFFF" '
                       f'stroke="{C["ink"]}" stroke-width="1.7"/>')
            title_lines = wrap(n["title"], 118, 12.4, bold=True)
            total = len(title_lines)
            start_y = cy - 14 - (total - 1) * 8
            out.append(f'<g data-fit="node-{n["id"]}-box">')
            out.append(svg_lines(cx, start_y, title_lines, 12.4, C["ink"], 16,
                                 weight="700", anchor="middle"))
            out.append(svg_lines(cx, cy + 20, wrap(n["sub"], 128, 8.6), 8.6,
                                 C["muted"], 11.5, anchor="middle"))
            out.append("</g>")
            # XOR marker
            out.append(f'<circle cx="{cx}" cy="{cy - h/2 + 15}" r="7.2" fill="#FFFFFF" '
                       f'stroke="{C["ink"]}" stroke-width="1"/>')
            out.append(svg_text(cx, cy - h/2 + 18.2, "×", 8.4, C["ink"],
                                weight="700", anchor="middle"))
            out.append(svg_text(cx - w/2 - 6, cy - h/2 + 14, n["step"], 8.2, C["faint"],
                                weight="700", anchor="end", ls="0.6"))
        elif kind == "timer":
            cx, cy, r = n["cx"], n["cy"], n["r"]
            out.append(f'<circle id="node-{n["id"]}-box" cx="{cx}" cy="{cy}" r="{r}" '
                       f'fill="#FFFFFF" stroke="{C["ink"]}" stroke-width="1.6"/>')
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{r - 4}" fill="none" '
                       f'stroke="{C["ink"]}" stroke-width="1"/>')
            out.append(f'<path d="M {cx} {cy} L {cx} {cy - r + 7}" stroke="{C["ink"]}" stroke-width="1.6" stroke-linecap="round"/>')
            out.append(f'<path d="M {cx} {cy} L {cx + r - 8} {cy + 4}" stroke="{C["ink"]}" stroke-width="1.6" stroke-linecap="round"/>')
            out.append(f'<circle cx="{cx}" cy="{cy}" r="1.8" fill="{C["ink"]}"/>')
            out.append(f'<rect id="node-{n["id"]}-labelbox" x="{cx - 66}" y="{cy + r + 2}" '
                       f'width="132" height="44" fill="#FFFFFF" fill-opacity="0.88" rx="4"/>')
            out.append(f'<g data-confirm="cycle" data-fit="node-{n["id"]}-labelbox">')
            out.append(svg_text(cx, cy + r + 21, "每 12 个月 · 定时事件", 9.0, C["body"],
                                weight="600", anchor="middle"))
            out.append(svg_text(cx, cy + r + 34, "周期建议值 · 待客户确认", 8.6,
                                C["exception"], weight="600", anchor="middle"))
            out.append("</g>")
        elif kind == "terminal":
            x, y, w, h = n["x"], n["y"], n["w"], n["h"]
            fill, stroke, txt, _ = state_palette(n["state"])
            out.append(f'<rect id="node-{n["id"]}-box" x="{x}" y="{y}" width="{w}" height="{h}" '
                       f'rx="{h/2}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
            out.append(f'<rect x="{x + 4}" y="{y + 4}" width="{w - 8}" height="{h - 8}" '
                       f'rx="{(h - 8)/2}" fill="none" stroke="{stroke}" stroke-width="0.8" opacity="0.55"/>')
            out.append(f'<g data-fit="node-{n["id"]}-box">')
            out.append(svg_text(x + w/2, y + h/2 + 4.6, n["title"], 13.2, txt,
                                weight="700", anchor="middle"))
            out.append("</g>")
        elif kind == "state":
            x, y, w, h = n["x"], n["y"], n["w"], n["h"]
            fill, stroke, txt, _ = state_palette(n["state"])
            out.append(f'<rect id="node-{n["id"]}-box" x="{x}" y="{y}" width="{w}" height="{h}" '
                       f'rx="{h/2}" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
            out.append(f'<g data-fit="node-{n["id"]}-box">')
            out.append(svg_text(x + 14, y + 21, "待补件", 12.6, txt, weight="700"))
            out.append(svg_text(x + 14, y + 36, n["sub"], 8.8, txt, opacity="0.85"))
            out.append("</g>")
            out.append(svg_text(x + w - 10, y + 13, n["step"], 8.2, C["faint"],
                                weight="700", anchor="end", ls="0.6"))
        elif kind == "note":
            x, y, w, h = n["x"], n["y"], n["w"], n["h"]
            out.append(f'<rect id="node-{n["id"]}-box" x="{x}" y="{y}" width="{w}" height="{h}" '
                       f'rx="9" fill="#FAFBFC" stroke="#C7D0DC" stroke-width="1" stroke-dasharray="4 3"/>')
            out.append(f'<rect x="{x}" y="{y}" width="3" height="{h}" fill="{accent}" opacity="0.5"/>')
            out.append(f'<g data-fit="node-{n["id"]}-box">')
            out.append(svg_text(x + 14, y + 23, n["title"], 10.3, C["ink"], weight="700"))
            body = []
            for line in n["lines"]:
                body.extend(wrap(line, w - 26, 9.2))
            out.append(svg_lines(x + 14, y + 40, body, 9.2, "#475569", 13.4))
            out.append("</g>")

        out.append("</g>")
    out.append("</g>")

    # ---- state chips (on top of nodes) ----
    out.append('<g class="chips">')
    for n in M.NODES:
        if n["kind"] not in ("process", "state"):
            continue
        if not n.get("state"):
            continue
        name = n["state"]
        fill, stroke, txt, dot = state_palette(name)
        size = 9.4
        cw = 20 + text_w(name, size, True) + 10
        cx = n["x"] + 12
        cy = n["y"] - 11
        out.append(f'<g class="state-chip" data-state="{attr(name)}">')
        out.append(f'<rect x="{cx}" y="{cy}" width="{cw:.1f}" height="22" rx="11" '
                   f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>')
        out.append(f'<circle cx="{cx + 9}" cy="{cy + 11}" r="2.8" fill="{dot}"/>')
        out.append(svg_text(cx + 15, cy + 14.6, name, size, txt, weight="700"))
        out.append("</g>")
    out.append("</g>")

    # ---- edge labels (topmost, white halo) ----
    out.append('<g class="edge-labels">')
    for e in M.EDGES:
        if not e.get("label"):
            continue
        lines = str(e["label"]).split("\n")
        if e.get("confirm"):
            lines = lines + ["阈值建议值 · 待客户确认"]
        x, y = e["label_at"]
        anchor = e.get("anchor", "start")
        size = 9.0
        lh = 12.6
        widths = [text_w(l, size, True) for l in lines]
        bw = max(widths) + 12
        bh = lh * len(lines) + 6
        if anchor == "end":
            bx = x - bw + 6
        elif anchor == "middle":
            bx = x - bw / 2
        else:
            bx = x - 6
        by = y - lh + 2
        extra = f' data-confirm="{e["confirm"]}"' if e.get("confirm") else ""
        out.append(f'<g class="edge-label"{extra}>')
        out.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
                   f'rx="4" fill="#FFFFFF" fill-opacity="0.94"/>')
        out.append(svg_lines(x, y, lines, size, C["body"], lh, weight="600", anchor=anchor))
        out.append("</g>")
    out.append("</g>")

    # ---- footer ----
    out.append(f'<rect x="0" y="1890" width="{W}" height="{H - 1890}" fill="#F8FAFC"/>')
    out.append(f'<line x1="70" y1="1890" x2="2930" y2="1890" stroke="{C["hair"]}" stroke-width="1"/>')
    # legend
    lx = 70
    ly = 1922
    out.append(svg_text(lx, ly - 8, "图例", 8.8, C["faint"], weight="700", ls="1.2"))
    ly = 1924
    items = [
        ("start", "开始 / 入口"),
        ("process", "处理步骤"),
        ("xor", "排他网关"),
        ("timer", "定时事件"),
        ("terminal", "终态"),
        ("chip", "状态标签"),
        ("main", "主流程"),
        ("loop", "恢复 / 继续在架"),
        ("exc", "暂停 / 下架触发"),
        ("assoc", "说明关联"),
    ]
    for kind, label in items:
        if kind == "start":
            out.append(f'<circle cx="{lx + 9}" cy="{ly}" r="9" fill="#FFFFFF" stroke="{C["start"]}" stroke-width="2.4"/>')
        elif kind == "process":
            out.append(f'<rect x="{lx}" y="{ly - 8}" width="22" height="16" rx="4" fill="#FFFFFF" stroke="{C["hair"]}" stroke-width="1.2"/>')
            out.append(f'<rect x="{lx}" y="{ly - 5}" width="2.4" height="10" fill="{C["start"]}" opacity="0.8"/>')
        elif kind == "xor":
            out.append(f'<polygon points="{lx + 11},{ly - 9} {lx + 22},{ly} {lx + 11},{ly + 9} {lx},{ly}" fill="#FFFFFF" stroke="{C["ink"]}" stroke-width="1.3"/>')
        elif kind == "timer":
            out.append(f'<circle cx="{lx + 10}" cy="{ly}" r="8.5" fill="#FFFFFF" stroke="{C["ink"]}" stroke-width="1.3"/>')
            out.append(f'<circle cx="{lx + 10}" cy="{ly}" r="5.8" fill="none" stroke="{C["ink"]}" stroke-width="0.8"/>')
            out.append(f'<path d="M {lx + 10} {ly} L {lx + 10} {ly - 4}" stroke="{C["ink"]}" stroke-width="1.2"/>')
        elif kind == "terminal":
            out.append(f'<rect x="{lx}" y="{ly - 7}" width="24" height="14" rx="7" fill="#EEF0F3" stroke="#4B5563" stroke-width="1.3"/>')
        elif kind == "chip":
            out.append(f'<rect x="{lx}" y="{ly - 7}" width="26" height="14" rx="7" fill="#EEF2F7" stroke="#C9D2DF"/>')
            out.append(f'<circle cx="{lx + 6}" cy="{ly}" r="2" fill="#5B6779"/>')
        elif kind == "main":
            out.append(f'<path d="M {lx} {ly} L {lx + 24} {ly}" stroke="#52606F" stroke-width="1.5" marker-end="url(#arrow-ink)"/>')
        elif kind == "loop":
            out.append(f'<path d="M {lx} {ly} L {lx + 24} {ly}" stroke="{C["loop"]}" stroke-width="1.4" stroke-dasharray="5 3" marker-end="url(#arrow-green)"/>')
        elif kind == "exc":
            out.append(f'<path d="M {lx} {ly} L {lx + 24} {ly}" stroke="{C["exception"]}" stroke-width="1.5" marker-end="url(#arrow-amber)"/>')
        else:
            out.append(f'<path d="M {lx} {ly} L {lx + 24} {ly}" stroke="{C["assoc"]}" stroke-width="1.2" stroke-dasharray="2 3"/>')
        out.append(svg_text(lx + 30, ly + 3.4, label, 9.0, C["muted"], weight="600"))
        lx += 30 + text_w(label, 9.0, True) + 26

    # notes
    ny = 1972
    for key, text in M.FOOTER_NOTES:
        out.append(svg_text(70, ny, key, 9.0, C["ink"], weight="700"))
        out.append(svg_text(112, ny, text, 9.0, C["muted"]))
        ny += 18
    out.append(svg_text(2930, 2028, "drawio + SVG + PNG + PDF · 同一内容源 · v" + M.VERSION,
                        8.6, C["faint"], anchor="end"))

    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------------------
# drawio build
# ---------------------------------------------------------------------------

def _mx_label(n):
    kind = n["kind"]
    if kind == "note":
        parts = [f"<b>{esc(n['title'])}</b>"]
        parts += [esc(l) for l in n["lines"]]
        return "<br>".join(parts)
    if kind == "start":
        return esc(n["label"])
    if kind == "terminal":
        return f"<b>{esc(n['title'])}</b>"
    if kind == "timer":
        return "<b>12</b>"
    if kind == "state":
        return f"<b>{esc(n['title'])}</b><br><font style=\"font-size:9px\">{esc(n['sub'])}</font>"
    sub = esc(n.get("sub", "")).replace("\n", "<br>")
    title = esc(n['title']).replace("\n", "<br>")
    return (f"<b>{title}</b><br>"
            f"<font style=\"font-size:9.5px\" color=\"#5B6779\">{sub}</font>")


def build_drawio() -> str:
    C = M.COLORS
    parts = []
    parts.append(
        '<mxfile host="app.diagrams.net" modified="2026-11-25T00:00:00.000Z" '
        f'agent="hermes-candidate" version="24.7.17" type="device">'
    )
    parts.append(f'<diagram id="d-{M.TASK_ID}" name="{esc(M.DOC_TITLE)}">')
    parts.append(
        f'<mxGraphModel dx="1600" dy="1000" grid="0" gridSize="10" guides="1" '
        f'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
        f'pageWidth="{M.CANVAS_W}" pageHeight="{M.CANVAS_H}" math="0" shadow="0" '
        f'background="#FFFFFF">'
    )
    parts.append("<root>")
    parts.append('<mxCell id="0"/>')
    parts.append('<mxCell id="1" parent="0"/>')

    # lanes
    for idx, lane in enumerate(M.LANES):
        top = M.LANE_TOPS[idx]
        label = (f"<b>{esc(lane['name'])}</b><br>"
                 f"<font style=\"font-size:9px\" color=\"#5B6779\">"
                 + "<br>".join(esc(x) for x in lane["sub"].split("\n")) + "</font>")
        style = ("swimlane;horizontal=0;startSize=180;html=1;whiteSpace=wrap;"
                 "fillColor=#FFFFFF;swimlaneFillColor=#FFFFFF;"
                 f"strokeColor={C['hair_soft']};fontFamily=Microsoft YaHei;"
                 f"fontSize=12;fontStyle=1;align=left;verticalAlign=top;spacingLeft=18;"
                 f"spacingTop=22;")
        parts.append(
            f'<object id="lane-{lane["id"]}" label="{attr(label)}" kind="lane" '
            f'lane_id="{lane["id"]}" lane_name="{attr(lane["name"])}">'
            f'<mxCell style="{attr(style)}" vertex="1" parent="1">'
            f'<mxGeometry x="{M.LANE_X}" y="{top}" width="{M.LANE_W}" height="{M.LANE_H}" as="geometry"/>'
            f'</mxCell></object>'
        )

    # ---- header / footer text (so the drawio export matches the SVG) ----
    def text_cell(cid, value, x, y, w, h, size=9, bold=False, align="left",
                  color="#5B6779", ls=None):
        st = ("text;html=1;strokeColor=none;fillColor=none;whiteSpace=wrap;"
              f"align={align};verticalAlign=middle;fontFamily=Microsoft YaHei;"
              f"fontSize={size};fontColor={color};"
              + ("fontStyle=1;" if bold else "")
              + (f"letterSpacing={ls};" if ls is not None else ""))
        parts.append(
            f'<mxCell id="{cid}" value="{attr(value)}" style="{attr(st)}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
        )

    text_cell("h-eyebrow", "S1-BP-025 · Stage i 蓝图与命名 · 业务蓝图与流程图",
              70, 26, 900, 18, 10, True, "left", "#5B6779", 1.1)
    text_cell("h-title", "<b>资源方入库审核与资源目录维护</b>", 70, 46, 1200, 40, 24, True,
              "left", "#1F2937")
    text_cell("h-sub", "流程泳道图 · 资源方 / 会员经理 / 运营 / 管理层 / 会员空间平台",
              70, 88, 1400, 20, 11, False, "left", "#5B6779")
    text_cell("h-meta", "任务 #2267 · 文档 S1-BP-025-D01 · v1.0.1", 2000, 28, 930, 18,
              10, True, "right", "#334155")
    text_cell("h-date", "生成日期 2026-11-25 · 页面 A2 横向", 2000, 48, 930, 16,
              9, False, "right", "#5B6779")
    text_cell("h-notice", "全部为虚构示例 · 不含客户名称与真实信息", 2400, 70, 530, 20,
              9, True, "right", "#8A5A2B")
    text_cell("f-legend", "图例：○ 开始/入口 · ▭ 处理步骤 · ◇ 排他网关（XOR） · ◎ 定时事件 · ⬭ 终态 · ● 状态标签 · → 主流程 · ⇢ 恢复/继续在架 · ⇢ 暂停/下架触发 · ⋯ 说明关联",
              70, 1906, 2860, 20, 9, False, "left", "#5B6779")
    text_cell("f-note-1", "依据：依据任务 #2267（S1-BP-025）原文绘制；未收到访谈纪要或 SOP 卡片，收到后按 S1-INT 导入并标注修订来源。",
              70, 1930, 2860, 16, 9, False, "left", "#5B6779")
    text_cell("f-note-2", "建议值：评分阈值（平均分 < 3）与复审周期（12 个月）为建议值，图中标注「待客户确认」，待客户书面确认后定稿。",
              70, 1948, 2860, 16, 9, False, "left", "#5B6779")
    text_cell("f-note-3", "数据：所有企业、机构、人名、联系方式与字段示例均为虚构；不含客户名称、真实个人信息或企业信息。",
              70, 1966, 2860, 16, 9, False, "left", "#5B6779")
    text_cell("f-note-4", "范围：本图只覆盖资源方入库、上架与退出；不含撮合交易、结算、合同正文与系统实现。",
              70, 1984, 2860, 16, 9, False, "left", "#5B6779")
    text_cell("f-version", "drawio + SVG + PNG + PDF · 同一内容源 · v1.0.1", 2000, 2008, 930, 14,
              8, False, "right", "#8793A3")

    # nodes
    for n in M.NODES:
        lane = lane_by_id(n["lane"])
        top = M.LANE_TOPS[[l["id"] for l in M.LANES].index(n["lane"])]
        kind = n["kind"]
        if kind == "start":
            style = ("ellipse;whiteSpace=wrap;html=1;fillColor=#FFFFFF;"
                     f"strokeColor={lane['accent']};strokeWidth=3;fontFamily=Microsoft YaHei;"
                     "fontSize=9;")
            gx, gy, gw, gh = n["cx"] - n["r"], n["cy"] - n["r"], n["r"] * 2, n["r"] * 2
        elif kind == "process":
            style = ("rounded=1;arcSize=12;whiteSpace=wrap;html=1;fillColor=#FFFFFF;"
                     f"strokeColor={C['hair']};strokeWidth=1.2;fontFamily=Microsoft YaHei;"
                     "fontSize=12;align=left;verticalAlign=middle;spacingLeft=14;spacingRight=10;")
            gx, gy, gw, gh = n["x"], n["y"], n["w"], n["h"]
        elif kind == "xor":
            style = ("rhombus;whiteSpace=wrap;html=1;fillColor=#FFFFFF;"
                     f"strokeColor={C['ink']};strokeWidth=1.7;fontFamily=Microsoft YaHei;"
                     "fontSize=12;fontStyle=1;align=center;verticalAlign=middle;")
            gx, gy, gw, gh = n["cx"] - n["w"] / 2, n["cy"] - n["h"] / 2, n["w"], n["h"]
        elif kind == "timer":
            style = ("ellipse;shape=doubleEllipse;whiteSpace=wrap;html=1;fillColor=#FFFFFF;"
                     f"strokeColor={C['ink']};strokeWidth=1.6;fontFamily=Microsoft YaHei;fontSize=9;")
            gx, gy, gw, gh = n["cx"] - n["r"], n["cy"] - n["r"], n["r"] * 2, n["r"] * 2
        elif kind == "terminal":
            fill, stroke, _, _ = state_palette(n["state"])
            style = ("rounded=1;arcSize=50;whiteSpace=wrap;html=1;"
                     f"fillColor={fill};strokeColor={stroke};strokeWidth=2;"
                     "fontFamily=Microsoft YaHei;fontSize=13;fontStyle=1;")
            gx, gy, gw, gh = n["x"], n["y"], n["w"], n["h"]
        elif kind == "state":
            fill, stroke, _, _ = state_palette(n["state"])
            style = ("rounded=1;arcSize=50;whiteSpace=wrap;html=1;"
                     f"fillColor={fill};strokeColor={stroke};strokeWidth=1.6;"
                     "fontFamily=Microsoft YaHei;fontSize=12;fontStyle=1;align=left;spacingLeft=14;")
            gx, gy, gw, gh = n["x"], n["y"], n["w"], n["h"]
        else:  # note
            style = ("rounded=1;whiteSpace=wrap;html=1;fillColor=#FAFBFC;strokeColor=#C7D0DC;"
                     "dashed=1;fontFamily=Microsoft YaHei;fontSize=9;align=left;verticalAlign=top;"
                     "spacingLeft=12;spacingTop=8;")
            gx, gy, gw, gh = n["x"], n["y"], n["w"], n["h"]

        if kind == "start":
            # start labels are drawn as separate text cells below
            label = ""
        else:
            label = _mx_label(n)
        rel_x = gx - M.LANE_X
        rel_y = gy - top
        attrs = [f'id="n-{n["id"]}"', f'label="{attr(label)}"', f'kind="{kind}"']
        if n.get("step"):
            attrs.append(f'step="{n["step"]}"')
        if n.get("state"):
            attrs.append(f'state="{attr(n["state"])}"')
        attrs.append(f'lane="{n["lane"]}"')
        if n.get("branches"):
            attrs.append(f'branches="{attr("|".join(n["branches"]))}"')
        if kind == "start":
            attrs.append(f'start_label="{attr(n["label"])}"')
        parts.append(f"<object {' '.join(attrs)}>")
        parts.append(f'<mxCell style="{attr(style)}" vertex="1" parent="lane-{n["lane"]}">')
        parts.append(f'<mxGeometry x="{rel_x:.1f}" y="{rel_y:.1f}" width="{gw:.1f}" height="{gh:.1f}" as="geometry"/>')
        parts.append("</mxCell></object>")

        # state chip as a child label (moves with the node)
        if kind == "process" and n.get("state"):
            fill, stroke, txt, _ = state_palette(n["state"])
            cw = text_w("● " + n["state"], 9, True) + 16
            chip_style = ("rounded=1;arcSize=50;html=1;whiteSpace=wrap;"
                          f"fillColor={fill};strokeColor={stroke};fontColor={txt};"
                          "fontFamily=Microsoft YaHei;fontSize=9;fontStyle=1;"
                          "align=center;verticalAlign=middle;")
            parts.append(
                f'<mxCell id="chip-{n["id"]}" value="{attr("● " + n["state"])}" '
                f'style="{attr(chip_style)}" vertex="1" parent="n-{n["id"]}">'
                f'<mxGeometry x="12" y="-11" width="{cw:.1f}" height="22" as="geometry"/></mxCell>'
            )

        # step id badge as a child text label
        if n.get("step"):
            badge_style = ("text;html=1;strokeColor=none;fillColor=none;align=right;"
                           "verticalAlign=middle;fontFamily=Microsoft YaHei;fontSize=8;"
                           "fontColor=#8793A3;fontStyle=1;")
            if kind == "start":
                bx, by, bw, bh, ba = 26, 20, 34, 14, "left"
            elif kind == "xor":
                bx, by, bw, bh, ba = -42, 6, 36, 14, "right"
            else:
                bx, by, bw, bh, ba = gw - 40, 3, 36, 14, "right"
            badge_style = badge_style.replace("align=right", f"align={ba}")
            parts.append(
                f'<mxCell id="badge-{n["id"]}" value="{n["step"]}" style="{attr(badge_style)}" '
                f'vertex="1" parent="n-{n["id"]}">'
                f'<mxGeometry x="{bx:.1f}" y="{by:.1f}" width="{bw}" height="{bh}" as="geometry"/></mxCell>'
            )

        if kind == "timer":
            tval = ('<font style="font-size:9px">每 12 个月 · 定时事件</font><br>'
                    '<font style="font-size:8.6px" color="#9A5A2B">周期建议值 · 待客户确认</font>')
            tstyle = ("text;html=1;strokeColor=none;fillColor=none;align=center;"
                      "verticalAlign=middle;fontFamily=Microsoft YaHei;fontSize=9;")
            parts.append(
                f'<mxCell id="t1-label" value="{attr(tval)}" style="{attr(tstyle)}" '
                f'vertex="1" parent="n-t1">'
                f'<mxGeometry x="-48" y="44" width="132" height="40" as="geometry"/></mxCell>'
            )

    # start labels as text cells (so they match the SVG)
    for n in M.NODES:
        if n["kind"] != "start":
            continue
        top = M.LANE_TOPS[[l["id"] for l in M.LANES].index(n["lane"])]
        style = ("text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;"
                "fontFamily=Microsoft YaHei;fontSize=9;fontStyle=1;")
        parts.append(
            f'<mxCell id="lbl-{n["id"]}" value="{attr(n["label"])}" style="{attr(style)}" vertex="1" parent="1">'
            f'<mxGeometry x="{n["cx"] - 80}" y="{n["cy"] - 38}" width="160" height="18" as="geometry"/>'
            f'</mxCell>'
        )

    # edge labels as text cells (absolute positions, matching SVG)
    for e in M.EDGES:
        if not e.get("label"):
            continue
        lines = str(e["label"]).split("\n")
        if e.get("confirm"):
            lines.append("阈值建议值 · 待客户确认")
        value = "<br>".join(esc(x) for x in lines)
        x, y = e["label_at"]
        anchor = e.get("anchor", "start")
        width = max(text_w(l, 9.0, True) for l in lines) + 14
        if anchor == "end":
            bx = x - width + 7
        elif anchor == "middle":
            bx = x - width / 2
        else:
            bx = x - 7
        style = ("text;html=1;strokeColor=none;fillColor=#FFFFFF;align=left;verticalAlign=middle;"
                "fontFamily=Microsoft YaHei;fontSize=9;fontStyle=1;labelBackgroundColor=#FFFFFF;")
        parts.append(
            f'<mxCell id="el-{e["id"]}" value="{attr(value)}" style="{attr(style)}" vertex="1" parent="1">'
            f'<mxGeometry x="{bx:.1f}" y="{y - 14:.1f}" width="{width:.1f}" height="{28 if len(lines) == 2 else 16}" as="geometry"/>'
            f'</mxCell>'
        )

    # edges
    for e in M.EDGES:
        kind = e["kind"]
        if kind == "exception":
            color, dash = C["exception"], ""
        elif kind == "loop":
            color, dash = C["loop"], "dashed=1;dashPattern=6 4;"
        elif kind == "assoc":
            color, dash = C["assoc"], "dashed=1;dashPattern=2 3;"
        else:
            color, dash = "#52606F", ""
        end_arrow = "none" if kind == "assoc" else "block"
        style = ("edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;"
                 f"strokeColor={color};strokeWidth=1.45;{dash}"
                 f"endArrow={end_arrow};endFill=1;fontFamily=Microsoft YaHei;fontSize=9;")
        pts = e["points"][1:-1]
        pts_xml = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in pts)
        parts.append(
            f'<mxCell id="{e["id"]}" edge="1" parent="1" source="n-{e["src"]}" '
            f'target="n-{e["dst"]}" style="{attr(style)}">'
            f'<mxGeometry relative="1" as="geometry"><Array as="points">{pts_xml}</Array></mxGeometry>'
            f'</mxCell>'
        )

    parts.append("</root></mxGraphModel></diagram></mxfile>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Markdown tables
# ---------------------------------------------------------------------------

def build_step_table() -> str:
    rows = []
    for s in M.STEPS:
        rows.append(
            f"| {s['id']} | {s['lane']} | {s['actor']} | {s['name']} | {s['inputs']} | "
            f"{s['actions']} | {s['outputs']} | {s['state']} | {s['next']} | {s['reqs']} | {s['note']} |"
        )
    body = "\n".join(rows)
    return f"""# 步骤说明表 · 资源方入库审核与资源目录维护

- 任务：#2267（S1-BP-025）· 版本 v{M.VERSION} · 生成日期 {M.GENERATED_ON}
- 用途：与泳道图一一对应；图中每个处理节点右上角的 `Sxx` 即本表行号。
- 数据说明：表中出现的资源方、联系人、机构均为**虚构示例**；不含客户名称与真实个人信息。
- 状态取值见 `state-enum.md`（7 个状态）；字段见 `catalog-fields.md`。

| 步骤 | 泳道 | 执行角色 | 步骤名称 | 输入 | 处理要点 | 输出 | 状态 | 下一步 | 需求 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|
{body}

## 入口与终点

- 入口①：资源方在小程序自助提交（S01）。
- 入口②：会员经理代为录入（S02，需资源方文字授权）。
- 终点①：资源上架进入资源目录（S10 → 状态“已上架”）。
- 终点②：申请被拒绝（S04/S06 → 状态“已拒绝”）。
- 终点③：资源下架（S14/S15 → 状态“已下架”）。

## 排他网关

| 网关 | 步骤 | 出口（互斥） | 说明 |
|---|---|---|---|
| 资质审核 | S04 | 通过 / 补件 / 拒绝 | 营业执照、资质证书核验 + 公开负面信息核查；三选一 |
| 金融/投资类管理层复核 | S06 | 通过 / 不通过 | 仅金融、投资类资源进入；不通过记录理由 |

## 评分与复审（建议值）

- 评价：每次撮合结束后由需求方打 1–5 分（S11）；仅有效撮合可评。
- 暂停：滚动平均分 < 3 分，或收到经运营核实的有效投诉（S12）。“3 分”与“有效评价最少条数”为**建议值，待客户确认**。
- 复审：每 12 个月定时触发（S13）；未通过则下架。“12 个月”为**建议值，待客户确认**。

## 覆盖计数（由 `tools/build.py` 生成）

- 步骤：{len(M.STEPS)} 行（S01–S{len(M.STEPS):02d}）
- 排他网关：2 个
- 状态：{len(M.STATES)} 个
- 资源类型：{len(M.RESOURCE_TYPES)} 类
"""


def build_state_table() -> str:
    rows = []
    for s in M.STATES:
        rows.append(
            f"| {s['id']} | {s['name']} | `{s['key']}` | {s['definition']} | {s['enter']} | "
            f"{s['exit']} | {s['member_visible']} | {s['owner']} |"
        )
    state_rows = "\n".join(rows)
    pause = "\n".join(
        f"| {pid} | {name} | {rule} | {owner} |" for pid, name, rule, owner in M.PAUSE_TRIGGERS
    )
    delist = "\n".join(
        f"| {pid} | {name} | {rule} | {owner} |" for pid, name, rule, owner in M.DELIST_TRIGGERS
    )
    return f"""# 资源状态枚举表 · 资源方入库审核与资源目录维护

- 任务：#2267（S1-BP-025）· 版本 v{M.VERSION} · 生成日期 {M.GENERATED_ON}
- 状态数量：**{len(M.STATES)} 个**（ST01–ST{len(M.STATES):02d}），与任务原文逐字一致。
- 数据说明：本表为流程设计，不含真实企业或个人信息。
- 状态标签在泳道图中以圆角标签显示；终态（已拒绝 / 已下架）同时以双边框终态节点显示。

## 1. 状态定义与流转

| 状态 ID | 状态 | 英文键 | 定义 | 进入条件 | 允许转出 | 会员端可见性 | 责任角色 |
|---|---|---|---|---|---|---|---|
{state_rows}

## 2. 状态流转总览

```text
申请中 ──提交审核──▶ 审核中 ──上架──▶ 已上架 ──暂停──▶ 已暂停
   │                   │                 ▲               │
   └──缺件──▶ 待补件 ──┘                 └──整改通过─────┘
   │                   └──拒绝──▶ 已拒绝
   └──撤回/前置拒绝──▶ 已拒绝

已上架 ──12 个月复审不通过 / 主动退出 / 严重违规──▶ 已下架
已暂停 ──整改不通过 / 严重违规──▶ 已下架
```

说明：`已拒绝` 与 `已下架` 为终态；如需重新合作，按新申请单重新走 S01–S10，不直接复活旧记录。

## 3. 暂停触发条件

任一条件成立即进入 `已暂停`（S12 暂停并复查）：

| 编号 | 触发条件 | 判定规则 | 责任角色 |
|---|---|---|---|
{pause}

**评分阈值说明**：`平均分 < 3` 为建议值，图中标注「待客户确认」；有效评价的最小条数（建议 ≥ 3 条）同样待确认。评分只统计有效撮合后的评价（1–5 分整数）。

## 4. 下架触发条件

任一条件成立即进入 `已下架`（S14 下架并归档）：

| 编号 | 触发条件 | 判定规则 | 责任角色 |
|---|---|---|---|
{delist}

## 5. 恢复规则

{M.RECOVERY_RULE}

## 6. 待客户确认

- 评分阈值 `3` 分与有效评价最小条数。
- 复审周期 `12` 个月；是否按资源类型分档。
- 暂停后的整改期限（建议 10 个工作日）。
- “有效投诉”的最终判定人（当前设计为运营，必要时管理层复核）。

> 本表所有数字与状态名称由 `tools/model.py` 单一来源生成；修改后需重建图与检查。
"""


def build_field_table() -> str:
    rows = []
    for f in M.FIELDS:
        fid, name, key, typ, req, src, vis, note, basis = f
        rows.append(f"| {fid} | {name} | `{key}` | {typ} | {req} | {src} | **{vis}** | {note} | {basis} |")
    body = "\n".join(rows)
    counts = {"可见": 0, "部分可见": 0, "不可见": 0}
    for f in M.FIELDS:
        counts[f[6]] += 1
    return f"""# 资源目录字段清单 · 资源方入库审核与资源目录维护

- 任务：#2267（S1-BP-025）· 版本 v{M.VERSION} · 生成日期 {M.GENERATED_ON}
- 字段数量：**{len(M.FIELDS)} 个**（F01–F{len(M.FIELDS):02d}），满足“不少于 12 个字段”。
- 会员可见性逐项标注，取值只有三种：**可见 / 部分可见 / 不可见**。
- 数据说明：字段示例值与资源方名称均为虚构；不含真实个人信息或企业信息。
- 依据：任务原文 + 统一技术约定（基础字段 id/org_id/site_id/created_at/created_by/updated_at/deleted_at）。

## 1. 可见性口径

| 可见性 | 含义 | 会员端表现 |
|---|---|---|
| 可见 | 登录会员与游客均可看到（若资源已上架且在其可见范围内） | 目录卡片、详情页正常展示 |
| 部分可见 | 仅在特定条件下展示，或展示脱敏/摘要 | 如“已核验”标识、脱敏电话、“登录查看” |
| 不可见 | 仅内部角色可见，会员端不出现 | 审核材料、风控结论、内部状态 |

> 可见范围（`visibility_scope`）由运营设置：全部会员 / 指定会员等级 / 仅内部可见。**仅内部可见的资源不发布到会员端**。

## 2. 字段清单

| 字段 ID | 字段 | 英文键 | 类型/取值 | 必填 | 来源 | 会员可见性 | 会员端展示说明 | 依据/备注 |
|---|---|---|---|---|---|---|---|---|
{body}

## 3. 统计（由 `tools/build.py` 从同一数据源生成）

- 字段总数：{len(M.FIELDS)}
- 可见：{counts['可见']}；部分可见：{counts['部分可见']}；不可见：{counts['不可见']}
- 基础字段：F01–F07（7 个，全部不可见）
- 业务字段：F08–F{len(M.FIELDS):02d}

## 4. 与统一技术约定的对应

- `id`(UUID)、`org_id`、`site_id`、`created_at`、`created_by`、`updated_at`、`deleted_at`（软删除）逐项列入 F01–F07。
- 本单不涉及金额字段；如后续加入价格/结算字段，按约定以“分”存整数，并在本表补充可见性。
- 配置与密钥不属于资源目录字段，不入表。

## 5. 待客户确认

- “会员专属条件”是否需要审批后才展示（当前：登录会员可见）。
- 联系电话的脱敏规则与授权查看流程。
- 是否需要向会员展示“资质有效期”。
"""


def build_metrics() -> dict:
    vis = {"可见": 0, "部分可见": 0, "不可见": 0}
    for f in M.FIELDS:
        vis[f[6]] += 1
    return {
        "task_id": M.TASK_ID,
        "task_code": M.TASK_CODE,
        "version": M.VERSION,
        "generated_on": M.GENERATED_ON,
        "lanes": len(M.LANES),
        "lanes_names": [l["name"] for l in M.LANES],
        "xor_gateways": sum(1 for n in M.NODES if n["kind"] == "xor"),
        "process_nodes": sum(1 for n in M.NODES if n["kind"] == "process"),
        "steps": len(M.STEPS),
        "states": len(M.STATES),
        "fields": len(M.FIELDS),
        "field_visibility": vis,
        "resource_types": len(M.RESOURCE_TYPES),
        "edges": len(M.EDGES),
        "timer_nodes": sum(1 for n in M.NODES if n["kind"] == "timer"),
        "terminals": sum(1 for n in M.NODES if n["kind"] == "terminal"),
        "ratings_scale": "1-5",
        "pause_threshold": 3,
        "review_cycle_months": 12,
    }


def build_render_html(svg: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>{esc(M.DOC_TITLE)}</title>
<style>
  @page {{ size: 594mm 405.9mm; margin: 0; }}
  html, body {{ margin: 0; padding: 0; background: #FFFFFF; }}
  svg {{ display: block; }}
  @media screen {{ svg {{ width: 3000px; height: 2050px; }} }}
  @media print {{ svg {{ width: 594mm; height: 405.9mm; }} }}
</style></head>
<body>
{svg}
</body></html>"""


def main():
    os.makedirs(os.path.join(ROOT, "diagram"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "artifacts"), exist_ok=True)

    svg = build_svg()
    # well-formed check before writing
    ET.fromstring(svg)
    with open(os.path.join(ROOT, "diagram", SVG_NAME + ".svg"), "w", encoding="utf-8") as f:
        f.write(svg)

    drawio = build_drawio()
    ET.fromstring(drawio)
    with open(os.path.join(ROOT, "diagram", SVG_NAME + ".drawio"), "w", encoding="utf-8") as f:
        f.write(drawio)

    with open(os.path.join(ROOT, "docs", "step-table.md"), "w", encoding="utf-8") as f:
        f.write(build_step_table())
    with open(os.path.join(ROOT, "docs", "state-enum.md"), "w", encoding="utf-8") as f:
        f.write(build_state_table())
    with open(os.path.join(ROOT, "docs", "catalog-fields.md"), "w", encoding="utf-8") as f:
        f.write(build_field_table())

    metrics = build_metrics()
    with open(os.path.join(ROOT, "docs", "METRICS.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
        f.write("\n")

    with open(os.path.join(ROOT, "artifacts", "render.html"), "w", encoding="utf-8") as f:
        f.write(build_render_html(svg))

    print(f"[build] svg      {len(svg):,} bytes")
    print(f"[build] drawio   {len(drawio):,} bytes")
    print(f"[build] lanes={metrics['lanes']} xor={metrics['xor_gateways']} "
          f"steps={metrics['steps']} states={metrics['states']} fields={metrics['fields']} "
          f"types={metrics['resource_types']}")


if __name__ == "__main__":
    main()
