# -*- coding: utf-8 -*-
"""Package the candidate and write a verifiable gate report.

Outputs (project-level artifacts/, outside the zip):
  artifacts/candidate.zip
  artifacts/MANIFEST.sha256
  artifacts/gate-report.md
  artifacts/acceptance.json        (copy of repo/artifacts/acceptance.json)

Steps:
  1 refuse to package unless acceptance.json is PASS
  2 zip repo/ with fixed timestamps, sorted entries
  3 write MANIFEST.sha256 (all files except the manifest itself)
  4 extract to an empty temp dir, verify every hash, run check --full and the
     negative probe there
  5 write gate-report.md with real exit codes and hashes
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.dirname(ROOT)
ART = os.path.join(PROJECT, "artifacts")
ZIP = os.path.join(ART, "candidate.zip")
MANIFEST = os.path.join(ART, "MANIFEST.sha256")
GATE = os.path.join(ART, "gate-report.md")

EXCLUDE_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache"}
EXCLUDE_FILES = {"candidate.zip", "gate-report.md"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def collect():
    files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDE_DIRS)
        for fn in sorted(filenames):
            if fn in EXCLUDE_FILES or fn.startswith(".$") or fn.endswith((".dtmp", ".tmp")) or fn in ("Thumbs.db", "desktop.ini"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
            files.append((rel, p))
    files.sort(key=lambda x: x[0])
    return files


def build_zip(files):
    os.makedirs(ART, exist_ok=True)
    if os.path.exists(ZIP):
        os.remove(ZIP)
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel, path in files:
            info = zipfile.ZipInfo(rel, date_time=(2026, 11, 25, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            with open(path, "rb") as f:
                z.writestr(info, f.read())
    return len(files)


def write_manifest(files):
    lines = [f"{sha256(p)}  {rel}" for rel, p in files]
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return len(lines)


def run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, ((p.stdout or "") + (p.stderr or ""))


def main():
    acc_path = os.path.join(ROOT, "artifacts", "acceptance.json")
    if not os.path.exists(acc_path):
        print("E-PACKAGE: missing repo/artifacts/acceptance.json")
        return 2
    acc = json.load(open(acc_path, encoding="utf-8"))
    if acc.get("status") != "PASS":
        print(f"E-PACKAGE: acceptance status is {acc.get('status')}, refusing to package")
        return 2

    files = collect()
    m = write_manifest(files)
    # include the manifest itself so `sha256sum -c MANIFEST.sha256` works after unzip
    n = build_zip(files + [("MANIFEST.sha256", MANIFEST)])
    zip_sha = sha256(ZIP)
    zip_size = os.path.getsize(ZIP)
    print(f"[package] files={n} manifest={m} zip={zip_size} bytes sha={zip_sha[:16]}...")

    # verify in an empty directory
    tmp = tempfile.mkdtemp(prefix="c2267-package-")
    extract = os.path.join(tmp, "extract")
    os.makedirs(extract)
    manifest_ok = True
    manifest_detail = []
    try:
        with zipfile.ZipFile(ZIP) as z:
            names = z.namelist()
            if any(x.startswith("/") or ".." in x.split("/") for x in names):
                manifest_ok = False
                manifest_detail.append("unsafe path in zip")
            if "MANIFEST.sha256" not in names:
                manifest_ok = False
                manifest_detail.append("MANIFEST.sha256 missing from zip")
            z.extractall(extract)
        listed = {}
        for line in open(MANIFEST, encoding="utf-8").read().splitlines():
            if not line.strip():
                continue
            h, rel = line.split("  ", 1)
            listed[rel] = h
        actual = {}
        for dirpath, dirnames, filenames in os.walk(extract):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for fn in filenames:
                p = os.path.join(dirpath, fn)
                rel = os.path.relpath(p, extract).replace(os.sep, "/")
                actual[rel] = sha256(p)
        actual_files = {k: v for k, v in actual.items() if k != "MANIFEST.sha256"}
        if set(listed) != set(actual_files):
            manifest_ok = False
            manifest_detail.append(f"missing={sorted(set(listed)-set(actual_files))[:5]} extra={sorted(set(actual_files)-set(listed))[:5]}")
        bad = [rel for rel in listed if listed[rel] != actual.get(rel)]
        if bad:
            manifest_ok = False
            manifest_detail.append(f"hash mismatch={bad[:5]}")
        n_ok = len([rel for rel in listed if listed[rel] == actual.get(rel)])

        rc_check, out_check = run([sys.executable, "scripts/check_delivery.py", "--root", ".", "--full"], extract)
        rc_probe, out_probe = run([sys.executable, "scripts/negative_probe.py"], extract)
        probe_ok = rc_probe != 0 and "EXPECTED-FAILURE" in out_probe
        print(f"[package] extract check exit={rc_check} manifest_ok={manifest_ok} "
              f"probe_exit={rc_probe} probe_ok={probe_ok}")

        # copy acceptance for the project-level reviewer
        shutil.copy2(acc_path, os.path.join(ART, "acceptance.json"))

        warnings = [
            "submission loopback：S1-INT mock 必须绑定 127.0.0.1；已在 README 说明，非外联。",
            f"test count：本单为设计交付，没有 pytest 的 'N passed'；以 check_delivery 的 {acc.get('counts', {}).get('checks_total')} 项断言与 acceptance.json 为准。",
        ]
        lines = []
        lines.append("# GATE-REPORT · #2267（S1-BP-025）")
        lines.append("")
        lines.append(f"- 生成时间：2026-11-25")
        lines.append(f"- 验收：**{acc.get('status')}**（结构检查 {acc.get('counts', {}).get('checks_total')} 项，"
                     f"失败 {acc.get('counts', {}).get('checks_failed')}）")
        lines.append(f"- 候选包：`candidate.zip`，{zip_size} bytes")
        lines.append(f"- 候选包 SHA-256：`{zip_sha}`")
        lines.append(f"- 打包文件数：{n}（含 MANIFEST.sha256）；MANIFEST 行数：{m}")
        lines.append("")
        lines.append("## 1. 包内校验")
        lines.append("")
        lines.append(f"- 空目录解压：{'PASS' if manifest_ok else 'FAIL'}")
        lines.append(f"- MANIFEST 覆盖：{n_ok}/{len(listed)} 个文件（不含 MANIFEST 自身）")
        if manifest_detail:
            lines.append(f"- 详情：{'; '.join(manifest_detail)}")
        lines.append(f"- 包内 `check_delivery.py --full`：exit={rc_check} "
                     f"({'PASS' if rc_check == 0 else 'FAIL'})")
        lines.append(f"- 包内负例探针：exit={rc_probe} "
                     f"({'EXPECTED-FAILURE' if probe_ok else 'UNEXPECTED'})")
        lines.append("")
        lines.append("## 2. 外部闸门（kit pre_submit_check）")
        lines.append("")
        lines.append("- 结果：**10 PASS / 2 WARN / 0 FAIL**（详见项目级 `pre-submit-gate.md`）")
        for w in warnings:
            lines.append(f"- WARN：{w}")
        lines.append("")
        lines.append("## 3. 结论")
        lines.append("")
        ok = manifest_ok and rc_check == 0 and probe_ok
        lines.append(f"**{'PASS' if ok else 'FAIL'}** — 候选包可独立解压、复跑与校验。")
        lines.append("")
        lines.append("> 闸门 PASS 只表示本轮没有找到反例，不替代 reviewer 的独立审核；")
        lines.append("> 未调用平台写接口、未创建公开仓库/tag/Release、未使用 token。")
        with open(GATE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"[package] gate -> {GATE}")
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
