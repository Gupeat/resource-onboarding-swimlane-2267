# REVIEW-REQUEST · #2267（S1-BP-025）

- 任务号：2267
- 版本：v1.0.0
- 候选目录：`projects/2267/repo/`
- 候选包：`projects/2267/artifacts/candidate.zip`（包 SHA-256 见项目级 `artifacts/gate-report.md` 与包内 `MANIFEST.sha256`）
- 生成时间：2026-11-25
- 包内 `MANIFEST.sha256` 覆盖除自身外的全部候选文件；本文件不内嵌 zip 自身的 SHA，避免自引用。

## 1. 一句话结论

**候选完成，待 reviewer 独立复核。** 不是“可提交”；发布、打 tag、平台提交均由 reviewer 执行。

## 2. 需求覆盖

- 需求条目共 **36 行**（R01–R36）
- done：**33**
- n/a：**2**（R03 背景/工单数量上下文；R06 金额约定在本设计交付中不适用）
- assumption：**1**（R30 未收到访谈纪要/SOP，已提供 mock 与导入点）
- blocked：**0**
- 反例缺失：**0**

逐条见项目级 `00-UNDERSTANDING.md` §3（候选目录上层；包内为摘要）。没有把 n/a 或 assumption 冒充 done。

## 3. 本次改了什么

- 从 `task-2267.json` 原文独立生产，未使用 DSH 侧冻结尝试的结论或素材（已隔离到 `_frozen-prior-attempt/`）。
- 产出 drawio/SVG/PNG/PDF、步骤表 S01–S15、状态表 ST01–ST07、字段表 F01–F28。
- 图中：5 泳道、2 个排他网关、7 状态、6 类资源、1–5 分评价、暂停/下架条件、12 个月定时复审、两处「待客户确认」。
- 检查器独立解析 drawio/SVG/Markdown，共 106 项断言；6 个真实篡改反例。
- S1-INT 使用 127.0.0.1 mock 与虚构 fixture；README 写明端点、schema 与替换步骤。
- draw.io 桌面版 32.7.4 实开并导出成功（5 泳道/2 网关/15 步/7 状态/无文字溢出/可编辑）；记录与截图见 `docs/drawio-open-check.md`。
- 图与表一致性：S15（资源方退出）改为汇入 S14（下架并归档），S14 再进已下架终态；删除 S15 直达终态的边。

## 4. 复跑命令与最近一次结果

```bash
python tools/build.py
python tools/import_s1_notes.py
node tools/render.mjs
python scripts/check_delivery.py --root . --full
python scripts/run_negative_tests.py
python tools/metrics.py
python scripts/run_acceptance.py
python tools/package.py
```

最近一次（`artifacts/acceptance.json`，PASS）：

- 结构检查：106 项，0 失败（`check-report.json`）
- 反例：6/6 KILLED（`negative-report.json`）
- 数字独立重算：13/13（`metrics-check.json`）
- 干净副本：`check_delivery.py --full` exit 0
- 渲染：128 个 text、25 个容器，0 溢出
- 外部闸门：10 PASS / 2 WARN / 0 FAIL（WARN：mock 回环、无 pytest 计数，均已在 gate 说明）
- 包内复跑：解压到空目录后 check exit 0，负例探针 exit 1（EXPECTED-FAILURE）

## 5. 已知缺口/未覆盖（对应需求）

| ID | 缺口 | 影响 | 当前处置 |
|---|---|---|---|
| R30 | 未收到真实访谈纪要/SOP 卡片 | 无法按材料修订并标注来源 | mock + 导入脚本；报告标注虚构；收到后按 README §5 替换 |
| R29 | 评分阈值 3 分、复审周期 12 个月未获客户书面确认 | 数值可能变 | 图中两处标「待客户确认」 |
| R24 | “有效投诉”判定人与留痕未定义 | 暂停触发可能不可判定 | 状态表写“运营核实、必要时管理层复核”，标实现选择 |
| R22 | 会员评价的泳道归属（会员不在 5 条岗位泳道内） | 可能被质疑 | 放在“会员空间平台”泳道并标注“会员经小程序” |
| — | 平台 deadline 已过期（2026-11-23T15:59:59） | 可能无法提交 | 生产不受影响；请 reviewer 确认提交窗口/延期 |
| — | drawio HTML 标签换行与 SVG 有 1–2px 差异；泳道标题因 horizontal=0 竖向显示 | 视觉可能不完全一致 | 以 PNG/PDF 为视觉基准；drawio 实开记录见 `docs/drawio-open-check.md` |
| — | 版式 minor：会员空间平台泳道左侧留白较大；补件回路与 P1→G1 主线有 1 处交叉 | 不影响语义与验收 | 保留不改，避免为好看改坏语义；已在 `artifacts/visual-review.json` 记录 |

## 6. 需要 reviewer 决定的问题

1. deadline 已过，是否仍提交、申请延期，或放弃本轮？
2. 会员评价放在“会员空间平台”泳道是否可接受？还是加第 6 条“会员/需求方”泳道？（当前严格遵守 5 条岗位泳道）
3. “有效投诉”的最终判定人、留痕字段与申诉机制。
4. 评分阈值、有效评价最少条数、复审周期、整改期限是否按建议值定稿？
5. 资源方主动退出是否涉及结算/违约，本图只画到“下架并归档”。

## 7. 证据路径

- `03-EVIDENCE.md`（由 `tools/write_evidence.py` 机器生成）
- `artifacts/acceptance.json`（FAIL-first 验收）
- `artifacts/check-report.json`（106 项）
- `artifacts/negative-report.json`（6 个真实反例）
- `artifacts/metrics-check.json`（13 项数字对账）
- `artifacts/render-report.json`（浏览器文字测量）
- `artifacts/visual-review.json`（PNG 目检锚点与结论）
- `docs/drawio-open-check.md`（桌面版 32.7.4 实开、截图与检查表）
- 项目级 `artifacts/gate-report.md`（包 SHA、MANIFEST、空目录复跑）
- 项目级 `artifacts/pre-submit-gate.md`（kit 闸门 10/2/0）

## 8. 声明

- 未调用平台写接口
- 本候选不创建公开仓库/tag/Release；发布由 reviewer 执行。
- 未使用 token
- 未声称“可提交”
- 候选完成 ≠ 可提交；最终裁决权在 reviewer 与用户
