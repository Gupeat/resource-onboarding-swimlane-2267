# -*- coding: utf-8 -*-
"""Structural checker for the #2267 candidate delivery.

The expectations below are literals copied from task-2267.json (quoted in
comments).  The checker never imports tools/model.py and never trusts
docs/METRICS.json as proof: it re-derives every count from the artifacts.

Exit codes: 0 = pass, 1 = violations, 2 = cannot parse / missing input.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# --- expectations copied from the task text (do not import model.py) -------
LANES = ["资源方", "会员经理", "运营", "管理层", "会员空间平台"]          # 泳道到岗位
RESOURCE_TYPES = ["客户渠道", "供应商服务", "投资机构", "人才服务", "政策服务", "专家顾问"]
STATES = ["申请中", "待补件", "审核中", "已上架", "已暂停", "已下架", "已拒绝"]
GATEWAYS = {
    "资质审核": {"branches": ["通过", "补件", "拒绝"], "min_out": 3},   # 排他网关：通过/补件/拒绝
    "管理层复核": {"branches": ["通过", "不通过"], "min_out": 2},      # 金融/投资类复核（排他网关）
}
MIN_FIELDS = 12
VISIBILITY = {"可见", "部分可见", "不可见"}
CANVAS = (3000, 2050)

TEXT_EXTS = {".md", ".py", ".mjs", ".js", ".json", ".svg", ".drawio", ".html", ".txt", ".csv", ".yml", ".yaml"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "artifacts"}


class Checker:
    def __init__(self, root: str, full: bool = False):
        self.root = os.path.abspath(root)
        self.full = full
        self.checks = []
        self.errors = []

    def add(self, cid, code, ok, detail=""):
        self.checks.append({"id": cid, "code": code, "ok": bool(ok), "detail": detail})
        if not ok:
            self.errors.append(f"{code}: {detail}")

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    # -- parsing helpers ---------------------------------------------------
    def text_of(self, el):
        return "".join(el.itertext()).strip()

    def parse_drawio(self):
        p = self.path("diagram", "resource-onboarding-swimlane.drawio")
        if not os.path.exists(p):
            raise FileNotFoundError(p)
        tree = ET.parse(p)
        root = tree.getroot()
        objects = []
        for obj in root.iter("object"):
            cell = obj.find("mxCell")
            if cell is None:
                continue
            objects.append({
                "id": obj.get("id", ""),
                "kind": obj.get("kind", ""),
                "label": obj.get("label", ""),
                "lane": obj.get("lane", ""),
                "step": obj.get("step", ""),
                "state": obj.get("state", ""),
                "branches": obj.get("branches", ""),
                "lane_name": obj.get("lane_name", ""),
                "start_label": obj.get("start_label", ""),
                "cell": cell,
            })
        edges = []
        edge_labels = {}
        child_values = {}
        for cell in root.iter("mxCell"):
            cid = cell.get("id", "")
            parent = cell.get("parent", "")
            if parent:
                child_values[parent] = child_values.get(parent, "") + " " + (cell.get("value") or "")
            if cell.get("edge") == "1":
                edges.append({
                    "id": cid,
                    "source": cell.get("source", ""),
                    "target": cell.get("target", ""),
                    "value": cell.get("value", ""),
                })
            elif cid.startswith("el-"):
                edge_labels[cid[3:]] = cell.get("value", "")
        return objects, edges, edge_labels, child_values

    def parse_svg(self):
        p = self.path("diagram", "resource-onboarding-swimlane.svg")
        if not os.path.exists(p):
            raise FileNotFoundError(p)
        tree = ET.parse(p)
        root = tree.getroot()
        return root

    def svg_text(self, root):
        return "\n".join(self.text_of(t) for t in root.iter("{http://www.w3.org/2000/svg}text"))

    def parse_md_table(self, rel, prefix_re):
        p = self.path(*rel.split("/"))
        if not os.path.exists(p):
            raise FileNotFoundError(p)
        rows = []
        for line in open(p, encoding="utf-8").read().splitlines():
            if line.startswith("|") and re.match(r"^\|\s*" + prefix_re + r"\d+", line):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                rows.append(cells)
        return rows

    # -- checks ------------------------------------------------------------
    def check_files(self):
        required = [
            ("diagram/resource-onboarding-swimlane.drawio", "E-DELIVERABLE"),
            ("diagram/resource-onboarding-swimlane.svg", "E-DELIVERABLE"),
            ("diagram/resource-onboarding-swimlane.png", "E-DELIVERABLE"),
            ("diagram/resource-onboarding-swimlane.pdf", "E-DELIVERABLE"),
            ("docs/step-table.md", "E-DELIVERABLE"),
            ("docs/state-enum.md", "E-DELIVERABLE"),
            ("docs/catalog-fields.md", "E-DELIVERABLE"),
            ("artifacts/render-report.json", "E-RENDER-REPORT"),
        ]
        if self.full:
            required += [
                ("README.md", "E-DELIVERABLE"),
                ("03-EVIDENCE.md", "E-DELIVERABLE"),
                ("STATUS.md", "E-DELIVERABLE"),
                ("REVIEW-REQUEST.md", "E-DELIVERABLE"),
                ("integrations/s1_int_mock/mock_server.py", "E-S1MOCK"),
                ("integrations/s1_int_mock/fixtures/fictional-notes.json", "E-S1MOCK"),
            ]
        for rel, code in required:
            p = self.path(*rel.split("/"))
            ok = os.path.exists(p) and os.path.getsize(p) > 0
            self.add(f"file:{rel}", code, ok, f"{rel} exists and is non-empty")

    def check_drawio(self, objects, edges, edge_labels, child_values):
        lanes = [o for o in objects if o["kind"] == "lane"]
        names = [o["lane_name"] for o in lanes]
        self.add("lanes.count", "E-LANES", len(lanes) == 5, f"lanes={len(lanes)} expected 5")
        self.add("lanes.names", "E-LANES", names == LANES, f"lanes={names}")

        xors = [o for o in objects if o["kind"] == "xor"]
        self.add("xor.count", "E-GW-COUNT", len(xors) == 2, f"xor={len(xors)} expected 2")
        labels = " | ".join(o["label"] for o in xors)
        for gw, spec in GATEWAYS.items():
            hit = [o for o in xors if gw in o["label"]]
            self.add(f"xor.{gw}.present", "E-GW-COUNT", len(hit) == 1,
                     f"gateway '{gw}' count={len(hit)}")
            if hit:
                gid = hit[0]["id"]
                out = [e for e in edges if e["source"] == gid]
                self.add(f"xor.{gw}.out", "E-GW-BRANCH", len(out) >= spec["min_out"],
                         f"{gw} outgoing={len(out)} min={spec['min_out']}")
                labels_out = " ".join(edge_labels.get(e["id"], e["value"]) for e in out)
                for b in spec["branches"]:
                    self.add(f"xor.{gw}.branch.{b}", "E-GW-BRANCH", b in labels_out,
                             f"{gw} branch '{b}' present in outgoing labels")

        steps = sorted({o["step"] for o in objects if o["step"]})
        self.add("steps.count", "E-STEPS", len(steps) == 15, f"steps={len(steps)} expected 15")

        timers = [o for o in objects if o["kind"] == "timer"]
        self.add("timer.count", "E-TIMER", len(timers) == 1, f"timers={len(timers)}")
        if timers:
            lab = (timers[0]["label"] + " " + ET.tostring(timers[0]["cell"], encoding="unicode")
                   + " " + child_values.get(timers[0]["id"], ""))
            self.add("timer.12m", "E-TIMER", "12 个月" in lab, "timer label contains '12 个月'")
            self.add("timer.waits", "E-TIMER", "待客户确认" in lab, "timer label contains '待客户确认'")

        terms = [o for o in objects if o["kind"] == "terminal"]
        term_states = {o["state"] for o in terms}
        self.add("terminals", "E-TERMINALS", {"已拒绝", "已下架"} <= term_states,
                 f"terminal states={sorted(term_states)}")

        states = {o["state"] for o in objects if o["state"]}
        self.add("states.drawio", "E-STATES", set(STATES) <= states,
                 f"missing={sorted(set(STATES) - states)}")
        self.add("states.count.drawio", "E-STATES", len(states & set(STATES)) == 7,
                 f"states={sorted(states & set(STATES))}")

    def check_paths(self, edges):
        """S15 (resource-provider exit) must reach S14, not the terminal directly."""
        out15 = [e for e in edges if e["source"] == "n-p10"]
        self.add("path.s15_s14", "E-S15-PATH",
                 any(e["target"] == "n-p9" for e in out15),
                 f"S15 outgoing targets={[e['target'] for e in out15]} (expected n-p9)")
        self.add("path.s15_no_terminal", "E-S15-PATH",
                 not any(e["target"] == "n-term2" for e in out15),
                 "S15 must not connect directly to the 已下架 terminal")
        self.add("path.s14_terminal", "E-S15-PATH",
                 any(e["source"] == "n-p9" and e["target"] == "n-term2" for e in edges),
                 "S14 must connect to the 已下架 terminal")

    def check_svg(self, root):
        ns = "{http://www.w3.org/2000/svg}"
        lanes = [g for g in root.iter(ns + "g") if g.get("class") == "lane"]
        self.add("svg.lanes", "E-LANES", len(lanes) == 5, f"svg lanes={len(lanes)}")
        self.add("svg.lane.names", "E-LANES",
                 [g.get("data-name") for g in lanes] == LANES,
                 f"svg lane names={[g.get('data-name') for g in lanes]}")

        xors = [g for g in root.iter(ns + "g") if g.get("data-kind") == "xor"]
        self.add("svg.xor.count", "E-GW-COUNT", len(xors) == 2, f"svg xor={len(xors)}")

        timers = [g for g in root.iter(ns + "g") if g.get("data-kind") == "timer"]
        self.add("svg.timer.count", "E-TIMER", len(timers) == 1, f"svg timers={len(timers)}")

        chip_states = [g.get("data-state") for g in root.iter(ns + "g") if g.get("class") == "state-chip"]
        node_states = [g.get("data-state") for g in root.iter(ns + "g") if g.get("data-state")]
        all_states = set(chip_states) | set(node_states)
        self.add("svg.states", "E-STATES", set(STATES) <= all_states,
                 f"missing={sorted(set(STATES) - all_states)}")
        self.add("svg.chips", "E-STATES", len(set(chip_states)) >= 5,
                 f"distinct chips={sorted(set(chip_states))}")

        text = self.svg_text(root)
        for t in RESOURCE_TYPES:
            self.add(f"svg.type.{t}", "E-TYPES", t in text, f"resource type '{t}' in svg text")
        self.add("svg.rating", "E-RATING", ("1–5" in text or "1-5" in text), "1-5 rating scale")
        self.add("svg.threshold", "E-PAUSE-TRIGGER", "平均分 < 3" in text, "avg < 3 in svg")
        self.add("svg.complaint", "E-PAUSE-TRIGGER", "有效投诉" in text, "valid complaint in svg")
        self.add("svg.timer12", "E-TIMER", "每 12 个月" in text, "12 months in svg")
        self.add("svg.timer.event", "E-TIMER", "定时事件" in text, "timer event label")
        self.add("svg.confirm.count", "E-CONFIRM", text.count("待客户确认") >= 2,
                 f"待客户确认 count={text.count('待客户确认')}")
        confirms = [g.get("data-confirm") for g in root.iter(ns + "g") if g.get("data-confirm")]
        self.add("svg.confirm.kinds", "E-CONFIRM",
                 "threshold" in confirms and "cycle" in confirms,
                 f"confirm kinds={sorted(set(confirms))}")
        self.add("svg.visibility.options", "E-VISIBILITY-OPTIONS",
                 all(x in text for x in ["全部会员", "指定会员等级", "仅内部可见"]),
                 "three visibility options present")
        self.add("svg.agreement", "E-AGREEMENT", "如有" in text, "'如有' condition present")
        self.add("svg.provider.kind", "E-PROVIDER-KIND",
                 "会员企业" in text and "外部服务机构" in text, "both provider kinds present")
        self.add("svg.starts", "E-STARTS", text.count("小程序") >= 1 and "代录" in text,
                 "both entry points present")
        self.add("svg.exit", "E-EXIT", "提出退出" in text and "已下架" in text,
                 "exit branch to delisted present")
        self.add("svg.waiting", "E-EXIT", "待补件" in text, "pending-docs state present")
        self.add("svg.meta", "E-META", all(x in text for x in ["S1-BP-025", "Stage i", "业务蓝图与流程图"]),
                 "task code / stage / module in header")

    def check_step_table(self, svg_text):
        rows = self.parse_md_table("docs/step-table.md", "S")
        ids = [r[0] for r in rows]
        expected = [f"S{i:02d}" for i in range(1, 16)]
        self.add("steps.table.count", "E-STEPS", len(rows) == 15, f"step rows={len(rows)}")
        self.add("steps.table.ids", "E-STEPS", ids == expected, f"ids={ids}")
        for r in rows:
            ok = len(r) >= 11 and all(r[i] for i in (0, 1, 2, 3, 7, 9))
            if not ok:
                self.add(f"steps.table.row.{r[0]}", "E-STEPS", False, f"incomplete row {r}")
        missing = [s for s in expected if s not in svg_text]
        self.add("steps.svg.crossref", "E-STEPS", not missing, f"step ids missing from svg: {missing}")

    def check_state_table(self):
        p = self.path("docs", "state-enum.md")
        content = open(p, encoding="utf-8").read()
        rows = self.parse_md_table("docs/state-enum.md", "ST")
        ids = [r[0] for r in rows]
        names = [r[1] for r in rows]
        self.add("states.table.count", "E-STATES", len(rows) == 7, f"state rows={len(rows)}")
        self.add("states.table.ids", "E-STATES", ids == [f"ST{i:02d}" for i in range(1, 8)], f"ids={ids}")
        self.add("states.table.names", "E-STATES", names == STATES, f"names={names}")
        self.add("triggers.pause.section", "E-TRIGGERS", "## 3. 暂停触发条件" in content,
                 "pause trigger section")
        self.add("triggers.delist.section", "E-TRIGGERS", "## 4. 下架触发条件" in content,
                 "delist trigger section")
        pause_rows = self.parse_md_table("docs/state-enum.md", "P")
        delist_rows = self.parse_md_table("docs/state-enum.md", "D")
        self.add("triggers.pause.count", "E-TRIGGERS", len(pause_rows) >= 2, f"pause rows={len(pause_rows)}")
        self.add("triggers.delist.count", "E-TRIGGERS", len(delist_rows) >= 2, f"delist rows={len(delist_rows)}")
        self.add("states.confirm", "E-CONFIRM", "待客户确认" in content, "待客户确认 in state table")

    def check_field_table(self):
        p = self.path("docs", "catalog-fields.md")
        content = open(p, encoding="utf-8").read()
        rows = self.parse_md_table("docs/catalog-fields.md", "F")
        ids = [r[0] for r in rows]
        self.add("fields.count", "E-FIELDS", len(rows) >= MIN_FIELDS,
                 f"field rows={len(rows)} min={MIN_FIELDS}")
        expected = [f"F{i:02d}" for i in range(1, len(rows) + 1)]
        self.add("fields.ids", "E-FIELDS", ids == expected, f"ids={ids[:5]}...{ids[-3:]}")
        bad = []
        for r in rows:
            if len(r) < 7:
                bad.append((r[0], "short row"))
                continue
            vis = r[6].replace("*", "").strip()
            if vis not in VISIBILITY:
                bad.append((r[0], vis))
        self.add("fields.visibility", "E-VISIBILITY", not bad, f"bad visibility rows={bad}")
        keys = ["id", "org_id", "site_id", "created_at", "created_by", "updated_at", "deleted_at"]
        missing = [k for k in keys if f"`{k}`" not in content]
        self.add("fields.base", "E-FIELDS", not missing, f"missing base keys={missing}")

    def check_field_semantics(self):
        rows = self.parse_md_table("docs/catalog-fields.md", "F")
        by_id = {r[0]: r for r in rows if len(r) >= 9}
        base = {
            "F01": ("id", "UUID"),
            "F04": ("created_at", "timestamptz"),
            "F05": ("created_by", "UUID"),
            "F06": ("updated_at", "timestamptz"),
            "F07": ("deleted_at", "timestamptz"),
        }
        bad = []
        for fid, (key, typ) in base.items():
            r = by_id.get(fid)
            if not r or key not in r[2] or typ.lower() not in r[3].lower():
                bad.append(fid)
        self.add("fields.base.types", "E-FIELD-TYPE", not bad, f"bad base types={bad}")

        money = [r[0] for r in rows if len(r) >= 9 and re.search(r"(price|amount|fee|cost|金额|价格)", r[1] + r[2], re.I)]
        if money:
            ok = all(("分" in r[3] or "int" in r[3].lower()) for r in rows if r[0] in money)
            self.add("fields.money", "E-MONEY", ok, f"money-like fields not integer cents={money}")
        else:
            self.add("fields.money", "E-MONEY", True, "no money-like field in this design")

    def check_external(self):
        allowed = {"127.0.0.1", "localhost", "www.w3.org"}
        urls = []
        imports = []
        scope_imports = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() not in TEXT_EXTS:
                    continue
                p = os.path.join(dirpath, fn)
                rel = os.path.relpath(p, self.root)
                try:
                    s = open(p, encoding="utf-8", errors="ignore").read()
                except OSError:
                    continue
                for m in re.finditer(r"https?://([^\s\"'<>)\]]+)", s):
                    host = m.group(1).split("/")[0].split(":")[0]
                    if host not in allowed:
                        urls.append(f"{rel}:{host}")
                if re.search(r"^\s*(?:import|from)\s+(fastapi|sqlalchemy|alembic|requests|flask|pandas|torch|openai)\b", s, re.M):
                    imports.append(rel)
                if re.search(r"^\s*(?:import|from)\s+(fastapi|sqlalchemy|alembic)\b", s, re.M):
                    scope_imports.append(rel)
        self.add("external.urls", "E-EXTERNAL", not urls, f"external hosts={urls[:5]}")
        self.add("external.sdk", "E-EXTERNAL", not imports, f"third-party imports={imports[:5]}")
        self.add("scope.runtime.imports", "E-SCOPE", not scope_imports, f"runtime imports={scope_imports[:5]}")

    def check_metrics(self, objects, edges):
        p = self.path("docs", "METRICS.json")
        if not os.path.exists(p):
            self.add("metrics.exists", "E-FIELDS", False, "docs/METRICS.json missing")
            return
        m = json.load(open(p, encoding="utf-8"))
        rows = self.parse_md_table("docs/catalog-fields.md", "F")
        vis = {"可见": 0, "部分可见": 0, "不可见": 0}
        for r in rows:
            if len(r) >= 7:
                v = r[6].replace("*", "").strip()
                if v in vis:
                    vis[v] += 1
        actual = {
            "lanes": len([o for o in objects if o["kind"] == "lane"]),
            "xor_gateways": len([o for o in objects if o["kind"] == "xor"]),
            "steps": len({o["step"] for o in objects if o["step"]}),
            "states": len(self.parse_md_table("docs/state-enum.md", "ST")),
            "fields": len(rows),
            "resource_types": len(RESOURCE_TYPES),
        }
        diff = {k: (m.get(k), v) for k, v in actual.items() if m.get(k) != v}
        self.add("metrics.consistency", "E-METRICS", not diff, f"mismatch={diff}")
        self.add("metrics.visibility", "E-METRICS", m.get("field_visibility") == vis,
                 f"declared={m.get('field_visibility')} actual={vis}")

    def check_png_pdf(self, report):
        png = self.path("diagram", "resource-onboarding-swimlane.png")
        data = open(png, "rb").read()
        sig_ok = data[:8] == b"\x89PNG\r\n\x1a\n"
        self.add("png.signature", "E-PNG", sig_ok, "PNG signature")
        if sig_ok and len(data) >= 24:
            w, h = struct.unpack(">II", data[16:24])
            self.add("png.dimensions", "E-PNG", w >= 3000 and abs(w / h - 3000 / 2050) < 0.01,
                     f"png={w}x{h}")
            if report:
                self.add("png.report.bytes", "E-PNG", report.get("png", {}).get("bytes") == len(data),
                         f"report bytes={report.get('png', {}).get('bytes')} actual={len(data)}")

        pdf = self.path("diagram", "resource-onboarding-swimlane.pdf")
        pdata = open(pdf, "rb").read()
        self.add("pdf.header", "E-PDF", pdata[:5] == b"%PDF-", "PDF header")
        mb = re.findall(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", pdata)
        if mb:
            w, h = float(mb[0][0]), float(mb[0][1])
            self.add("pdf.mediabox", "E-PDF", abs(w / h - 594 / 405.9) < 0.01,
                     f"mediabox={w:.2f}x{h:.2f}pt ratio={w/h:.4f}")
        else:
            self.add("pdf.mediabox", "E-PDF", False, "no MediaBox found")
        pages = len(re.findall(rb"/Type\s*/Page[^s]", pdata))
        self.add("pdf.pages", "E-PDF", pages == 1, f"pages={pages}")

        # prove the page is not blank: decompress content streams and count text ops
        import zlib
        streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdata, re.S)
        content = b""
        for st in streams:
            try:
                content += zlib.decompress(st)
            except zlib.error:
                pass
        tj = content.count(b" Tj")
        fonts = len(set(re.findall(rb"/BaseFont\s*/[A-Za-z0-9+\-]+", pdata)))
        self.add("pdf.text_ops", "E-PDF", tj >= 100, f"text-show ops={tj}")
        self.add("pdf.fonts", "E-PDF", fonts >= 1, f"embedded fonts={fonts}")
        if report:
            self.add("pdf.report.bytes", "E-PDF", report.get("pdf", {}).get("bytes") == len(pdata),
                     f"report bytes={report.get('pdf', {}).get('bytes')} actual={len(pdata)}")

    def check_render_report(self):
        p = self.path("artifacts", "render-report.json")
        if not os.path.exists(p):
            raise FileNotFoundError(p)
        r = json.load(open(p, encoding="utf-8"))
        self.add("render.overflow", "E-OVERFLOW", r.get("overflow") == [],
                 f"fit overflow={len(r.get('overflow', []))}")
        self.add("render.canvas", "E-OVERFLOW", r.get("canvas_overflow") == [],
                 f"canvas overflow={len(r.get('canvas_overflow', []))}")
        self.add("render.texts", "E-OVERFLOW", r.get("texts_checked", 0) >= 100,
                 f"texts_checked={r.get('texts_checked')}")
        self.add("render.fit.groups", "E-OVERFLOW", r.get("fit_groups_checked", 0) >= 20,
                 f"fit_groups={r.get('fit_groups_checked')}")
        self.add("render.browser", "E-OVERFLOW", "Edg/" in r.get("browser_version", ""),
                 f"browser={r.get('browser_version')}")
        return r

    def check_hygiene(self):
        bad_paths = []
        bad_secrets = []
        bad_pii = []
        secret_re = re.compile(r"(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY|Bearer\s+[A-Za-z0-9._\-]{20,})")
        phone_re = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
        id_re = re.compile(r"(?<!\d)\d{6}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)")
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in TEXT_EXTS:
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    s = open(p, encoding="utf-8", errors="ignore").read()
                except OSError:
                    continue
                rel = os.path.relpath(p, self.root)
                if re.search(r"(?:[A-Za-z]:[\\/]{1,2}|[/])Users[\\/]", s):
                    bad_paths.append(rel)
                m = secret_re.search(s)
                if m:
                    bad_secrets.append((rel, m.group(0)[:12]))
                if phone_re.search(s) or id_re.search(s):
                    bad_pii.append(rel)
        self.add("hygiene.paths", "E-PATH", not bad_paths, f"absolute user paths={bad_paths}")
        self.add("hygiene.secrets", "E-SECRET", not bad_secrets, f"secret-like={bad_secrets}")
        self.add("hygiene.pii", "E-PII", not bad_pii, f"phone/id-like={bad_pii}")

    def check_scope(self):
        forbidden = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            if os.path.basename(dirpath) in {"app", "alembic"}:
                forbidden.append(os.path.relpath(dirpath, self.root))
        self.add("scope.noapp", "E-SCOPE", not forbidden, f"runtime dirs={forbidden}")
        req = self.path("requirements.txt")
        if os.path.exists(req):
            lines = [l.strip() for l in open(req, encoding="utf-8") if l.strip() and not l.strip().startswith("#")]
            self.add("scope.deps", "E-STACK", not lines, f"third-party deps={lines}")

    def check_s1mock(self):
        mock = self.path("integrations", "s1_int_mock", "mock_server.py")
        if os.path.exists(mock):
            s = open(mock, encoding="utf-8").read()
            self.add("s1mock.localhost", "E-S1MOCK", "127.0.0.1" in s, "mock binds 127.0.0.1")
            self.add("s1mock.endpoints", "E-S1MOCK",
                     "/api/v1/interviews" in s and "/api/v1/sop-cards" in s, "documented endpoints")
        readme = self.path("README.md")
        if os.path.exists(readme):
            s = open(readme, encoding="utf-8").read()
            self.add("s1mock.readme", "E-S1MOCK", "S1-INT 对接点" in s, "README integration section")

    def run(self):
        try:
            objects, edges, edge_labels, child_values = self.parse_drawio()
            svg_root = self.parse_svg()
        except (FileNotFoundError, ET.ParseError) as e:
            print(f"E-PARSE: {e}")
            return 2

        self.check_files()
        self.check_drawio(objects, edges, edge_labels, child_values)
        self.check_paths(edges)
        self.check_svg(svg_root)
        self.check_step_table(self.svg_text(svg_root))
        self.check_state_table()
        self.check_field_table()
        self.check_field_semantics()
        self.check_external()
        self.check_metrics(objects, edges)
        try:
            report = self.check_render_report()
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.add("render.report", "E-RENDER-REPORT", False, str(e))
            report = None
        self.check_png_pdf(report)
        self.check_hygiene()
        self.check_scope()
        if self.full:
            self.check_s1mock()

        total = len(self.checks)
        failed = sum(1 for c in self.checks if not c["ok"])
        print(f"checked={total} failed={failed}")
        for c in self.checks:
            if not c["ok"]:
                print(f"FAIL {c['code']} [{c['id']}] {c['detail']}")
        if failed == 0:
            print("PASS: all structural assertions satisfied")
        return 0 if failed == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--full", action="store_true", help="also require handoff docs and S1 mock")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    ck = Checker(args.root, full=args.full)
    rc = ck.run()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": ".",
        "full": args.full,
        "checks": ck.checks,
        "total": len(ck.checks),
        "failed": len(ck.errors),
        "result": "PASS" if rc == 0 else "FAIL",
    }
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            f.write("\n")
    sys.exit(rc)


if __name__ == "__main__":
    main()
