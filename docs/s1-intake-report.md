# S1-INT 导入报告（MOCK / 虚构）

- 任务：#2267（S1-BP-025）
- 生成时间：2026-11-25
- 输入：`integrations/s1_int_mock/fixtures/fictional-notes.json`
- 输入 SHA-256：`7ddb93eca917ea98f7cfbb6ddfaef88d68abf0d269dedc50db97ec09931133e7`
- 数据性质：**虚构（fictional=true）**

> **重要**：本报告由 mock fixture 生成。**未收到真实访谈纪要或 SOP 卡片**；
> 本报告只验证 S1-INT 接口/schema 可解析，**不得作为客户输入或验收证据**。
> 真实材料到达后，按第 5 节替换，并逐条标注修订来源。

## 0. 校验结果：PASS（schema 与 requirement_hint 格式）

## 1. 解析计数

- 访谈：3 条
- 陈述：7 条
- SOP 卡片：2 张

## 2. 陈述 → 需求映射

| 陈述 ID | 来源访谈 | 需求 ID | 原文 | 已确认 | 备注 |
|---|---|---|---|---|---|
| STMT-001 | INT-FAKE-001 | R14 | 资源方可能是会员企业，也可能是外面的服务机构，两种都要能入库。 | 是 |  |
| STMT-002 | INT-FAKE-001 | R19 | 资质审核就看营业执照、资质证书，再查一下公开的负面信息。 | 是 |  |
| STMT-003 | INT-FAKE-001 | R19 | 补件一般给五个工作日，最多补两轮。 | 待确认 | 与图中“建议 2 轮补件”一致；期限未在图中标注，待客户确认。 |
| STMT-004 | INT-FAKE-002 | R22 | 可见范围就三档：全部会员、指定会员等级、只给内部看；只给内部看的不要上到会员端。 | 是 |  |
| STMT-005 | INT-FAKE-002 | R23 | 上架之后每次撮合完，让需求方在 1 到 5 分里打分。 | 是 |  |
| STMT-006 | INT-FAKE-003 | R24 | 平均分低于 3 分，或者有核实过的有效投诉，就先暂停，让资源方整改。 | 是 |  |
| STMT-007 | INT-FAKE-003 | R25 | 每 12 个月复审一次，没通过就下架。 | 待确认 | 12 个月与图中一致，但仍是建议值，需客户书面确认。 |

## 3. SOP 卡片

| 卡片 ID | 需求 ID | 条目 |
|---|---|---|
| SOP-FAKE-001 | R18 | 营业执照复印件（加盖公章）；资质证书或授权文件；服务说明与报价口径（如有）；对接联系人及联系方式 |
| SOP-FAKE-002 | R24 | 暂停原因（评分 / 投诉 / 资质）；整改要求与期限（建议 10 个工作日）；复查方式与联系人 |

## 4. 与当前候选的关系

- 本 fixture 的陈述与任务原文一致的部分：仅用于回归接口解析，不改变图。
- 标为「待确认」的陈述（补件期限、12 个月复审）：图中已将复审周期标「待客户确认」，补件期限未入图。
- 未发现与任务原文冲突的陈述；如真实材料冲突，按 AGENT-CONTRACT 优先级（任务原文 > 客户书面澄清 > 竞标承诺 > 假设）处理。

## 5. 真实材料到达后的替换步骤

1. 将真实材料放入 `handoff/client-inputs/`，在 `INPUT-INDEX.csv` 登记（含 sha256、分类、支撑的需求 ID）。
2. 把真实导出保存为与 fixture 相同 schema 的 JSON（或让 S1-INT 提供同构接口）。
3. 运行 `python tools/import_s1_notes.py --input <real.json>`，生成本报告的新版本。
4. 逐条比对：一致的保留；冲突的以任务原文/客户书面澄清为准，修改 `tools/model.py` 并重建。
5. 升 patch 版本，在图脚注与 `03-EVIDENCE.md` 写「修订来源：S1-INT:<id>#<statement>」。

## 6. 对接点（与 README 一致）

- `GET /api/v1/interviews?project=2267` → `{meta, data:[{id,title,captured_at,statements:[...]}]}`
- `GET /api/v1/sop-cards?project=2267` → `{meta, data:[{id,title,items,requirement_hint}]}`
- mock 仅绑定 `127.0.0.1`，端口从 `PORT` 环境变量读取；不访问外网、不读取凭据。
