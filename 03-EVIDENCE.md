# 03-EVIDENCE · #2267（S1-BP-025）

- 任务号：2267（S1-BP-025）· 版本：v1.0.1
- 生成时间：2026-11-25T23:23:30+0800
- 验收状态：**PASS**
- 证据性质：生产方机器证据 + 生产方目检，**不是独立审核**；最终裁决权在 reviewer。
- 数字来源：`artifacts/acceptance.json`、`check-report.json`、`negative-report.json`、`metrics-check.json`、`render-report.json`；本文件不手写计数。

## 1. 环境

- Python：3.12.14
- Node：v26.7.0
- 浏览器：Edg/156.0.4314.58
- 画布：3000 × 2050，scale=2

## 2. 验收阶段与真实命令

| 阶段 | 命令 | 退出码 | 耗时(s) | 输出尾部 |
|---|---|---|---|---|
| build | `python tools/build.py` | 0 | 0.15 | [build] lanes=5 xor=2 steps=15 states=7 fields=28 types=6 |
| s1-int | `python tools/import_s1_notes.py` | 0 | 0.13 | [s1-int] wrote docs\s1-intake-report.md |
| render | `node tools/render.mjs` | 0 | 4.63 | [render] pdf 350960 bytes -> <repo>\diagram\resource-onboarding-swimlane.pdf |
| negative | `python scripts/run_negative_tests.py` | 0 | 3.68 | negative: 7/7 KILLED |
| check | `python scripts/check_delivery.py --root . --full --json artifacts/check-report.json` | 0 | 0.3 | PASS: all structural assertions satisfied |
| numbers | `python tools/metrics.py` | 0 | 0.14 | png=6000x4100 pdf_pages=1 lanes=5 xor=2 steps=15 states=7 fields=28 |
| clean-copy | `python scripts/check_delivery.py --root <clean-copy> --full` | 0 | 0.31 | PASS: all structural assertions satisfied |
| mock | `python integrations/s1_int_mock/mock_server.py + GET` | 0 | — | http=200 fictional=True interviews=3 |

- 检查：107 项，失败 0
- 反例：7 / 7 KILLED
- 数字：13 / 13 matched
- 渲染：128 个 text，溢出 0

## 3. 结构检查（check_delivery.py）

- 断言总数：107；失败：0

| 断言 | 结果 | 说明 |
|---|---|---|
| `lanes.count` | PASS | lanes=5 expected 5 |
| `lanes.names` | PASS | lanes=['资源方', '会员经理', '运营', '管理层', '会员空间平台'] |
| `xor.count` | PASS | xor=2 expected 2 |
| `xor.资质审核.branch.补件` | PASS | 资质审核 branch '补件' present in outgoing labels |
| `xor.管理层复核.branch.不通过` | PASS | 管理层复核 branch '不通过' present in outgoing labels |
| `states.table.names` | PASS | names=['申请中', '待补件', '审核中', '已上架', '已暂停', '已下架', '已拒绝'] |
| `triggers.pause.section` | PASS | pause trigger section |
| `triggers.delist.section` | PASS | delist trigger section |
| `fields.count` | PASS | field rows=28 min=12 |
| `fields.visibility` | PASS | bad visibility rows=[] |
| `steps.svg.crossref` | PASS | step ids missing from svg: [] |
| `svg.confirm.kinds` | PASS | confirm kinds=['cycle', 'threshold'] |
| `render.overflow` | PASS | fit overflow=0 |
| `png.dimensions` | PASS | png=6000x4100 |
| `pdf.text_ops` | PASS | text-show ops=1435 |
| `hygiene.pii` | PASS | phone/id-like=[] |

## 4. 真实反例（临时副本，工作树不变）

- 基线：exit=0（PASS）

| 用例 | 篡改 | 期望错误码 | 实际退出码 | 结果 |
|---|---|---|---|---|
| N1 | 删除运营泳道 | `E-LANES` | 1 | **KILLED** |
| N2 | 把「已暂停」改名为「暂停中」 | `E-STATES` | 1 | **KILLED** |
| N3 | 删除字段 F07（软删除） | `E-FIELDS` | 1 | **KILLED** |
| N4 | 删除管理层复核网关 | `E-GW-COUNT` | 1 | **KILLED** |
| N5 | 删除「有效投诉」触发条件 | `E-PAUSE-TRIGGER` | 1 | **KILLED** |
| N6 | 删除 S15→S14 退出边 | `E-S15-PATH` | 1 | **KILLED** |
| N7 | 向文档注入 U+FFFD（编码破坏） | `E-ENCODING` | 1 | **KILLED** |

## 5. 数字独立重算（不读 METRICS.json 作为证明）

- 结果：13 / 13 matched

| 项目 | 声明 | 实测 | 结果 |
|---|---|---|---|
| METRICS.lanes | 5 | 5 | PASS |
| METRICS.xor_gateways | 2 | 2 | PASS |
| METRICS.steps | 15 | 15 | PASS |
| METRICS.states | 7 | 7 | PASS |
| METRICS.fields | 28 | 28 | PASS |
| METRICS.resource_types | 6 | 6 | PASS |
| steps_drawio==steps_table | 15 | 15 | PASS |
| fields_header | 28 | 28 | PASS |
| states_header | 7 | 7 | PASS |
| steps_header | 15 | 15 | PASS |
| visibility.可见 | 10 | 10 | PASS |
| visibility.部分可见 | 6 | 6 | PASS |
| visibility.不可见 | 12 | 12 | PASS |

## 6. 渲染与目检

- 浏览器实测：128 个 text、25 个容器；溢出 0，画布外 0。
- PNG：6000×4100，696455 bytes。
- PDF：1 页，MediaBox=[1684.08, 1151.03992]，350960 bytes。
- 目检锚点：PNG SHA-256 `d8df2994c75f89c96bf1a82f14764593f0bf3d9eece76787d3825d9eb8f1d102`；visual-review=PASS。

| 目检项 | 结果 | 说明 |
|---|---|---|
| 文字溢出 | PASS | 浏览器实测 128 个 text、25 个 fit 容器，0 溢出；目检卡片/注记/页脚无截断或压边 |
| 泳道与状态标签 | PASS | 5 条泳道齐全；状态标签未遮挡节点标题；7 个状态名均可见 |
| S15 → S14 一致性 | PASS | 资源方退出（S15）改为汇入下架并归档（S14），S14 再进已下架终态；S15 不再直达终态，与步骤表一致 |
| 箭头与连线 | PASS | 无穿框；S15 的竖直通道在终态左侧 20px 处下行，进入 S14 东侧；S14→终态的「归档」标签移到边下方，不再压 S14 角标 |
| 排他网关 | PASS | G1/G2 菱形、× 标记与分支标签（通过/补件/拒绝；通过/不通过）清楚 |
| 定时器与待确认 | PASS | 双圆时钟 + 12 个月；阈值与周期两处「待客户确认」可读 |
| drawio 实开 | PASS | draw.io 桌面版 32.7.4 打开并导出成功；详见 docs/drawio-open-check.md |
| 页眉页脚 | PASS | 标题、文档号、版本 v1.0.1、虚构数据徽标、图例、4 条脚注齐全 |
| 已知 minor | NOTE | ① 会员空间平台泳道左侧留白较大（该泳道仅评价一步，保留不改语义）；② 补件回路与 P1→G1 主线有 1 处交叉，线型可区分；③ drawio 泳道标题因 horizontal=0 竖向显示，SVG/PDF 为水平标签带；④ PDF 字节含生成 ID，重渲染 SHA 会变 |

> 目检方法：v1.0.1 6000x4100 PNG full view + 2x crops; layout unchanged from v1.0.0, header version re-checked。目检是生产方自检，不替代 reviewer 的客户视角审核。

- drawio 实开验证：`docs/drawio-open-check.md`（桌面版 32.7.4；打开/导出 PASS，含 GUI 截图与浅色导出）。

> 稳定性：PNG 为稳定视觉锚点（渲染确定）；PDF 的 SHA 仅对应本次 Chromium 渲染，重渲染会变，不作为跨次锚点。树哈希含 PDF，仅用于本次候选一致性。

## 7. 文件与 SHA-256

| 文件 | SHA-256 |
|---|---|
| `diagram/resource-onboarding-swimlane.drawio` | `d15a16e915a1cc31c0e605aac35fc52cc32d411d33e88f5c5726a27ce7429a6b` |
| `diagram/resource-onboarding-swimlane.svg` | `187e7890b382b03a5698e9ccede81c16e9f2174c955a8034e50574c74f5fecf5` |
| `diagram/resource-onboarding-swimlane.png` | `d8df2994c75f89c96bf1a82f14764593f0bf3d9eece76787d3825d9eb8f1d102` |
| `diagram/resource-onboarding-swimlane.pdf` | `cd8d453b50e54d98aaedc423142788dd089765f423cf3a8708f5bbdb72d176cb` |
| `docs/step-table.md` | `3c90c9ba5a34eea6ea3185cfda695dc453eedcebebbc05af5ef4c77f2a1b0636` |
| `docs/state-enum.md` | `09fa9810cd64043337c11484f20aa7cb5926ab46f2570aceda5a4eaffc72c00d` |
| `docs/catalog-fields.md` | `f556d02b17138e187aedd68045ee97819c3bc24ebd06a6d4094707b4917e193a` |
| `docs/s1-intake-report.md` | `71f42e331e39206adb551a2e82f872d4744279abd0e581a5746f76f45f324178` |
| `docs/METRICS.json` | `908faa5b72cd29576e880777998a87aaef9bb3c0849eb794db3e90d48f5a4b4e` |
| `README.md` | `24093747eaccad840f24ffa7f2f408aebbdebcceee75bdd5b260ec9a1d1c85a7` |

- 树哈希（排除 `artifacts/`）：`39fc2b207f12ab5138eff6187a85637691eb1731c93bda50850bdaecab819de5`

## 8. 复跑

```bash
python tools/build.py
python tools/import_s1_notes.py
node tools/render.mjs
python scripts/check_delivery.py --root . --full
python scripts/run_negative_tests.py
python tools/metrics.py
python scripts/run_acceptance.py
```

## 9. 未覆盖与已知缺口

- **deadline 已过期**（2026-11-23T15:59:59）：提交窗口需 reviewer/平台确认。
- **未收到真实访谈纪要/SOP**：S1-INT 仅 mock；`docs/s1-intake-report.md` 明确标注虚构。
- **评分阈值/有效评价条数/复审周期/整改期限/有效投诉判定人**：待客户确认。
- **会员评价泳道归属**：按 5 泳道约束放在“会员空间平台”并标注“会员经小程序”；是否加第 6 条泳道待客户确认。
- **PDF 字节不稳定**：Chromium 每次渲染写入文档 ID，SHA 会变；PDF 的 SHA 不作为跨次稳定锚点，内容与 MediaBox 稳定。
- **drawio 排版差异**：HTML 标签换行由 draw.io 决定；桌面版泳道标题因 horizontal=0 竖向显示，SVG/PDF 为水平标签带。视觉以 PNG/PDF 为准。
