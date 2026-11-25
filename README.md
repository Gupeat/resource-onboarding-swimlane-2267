# 资源方入库审核与资源目录维护 · 流程泳道图

- 任务：#2267（S1-BP-025）· Stage i 蓝图与命名 · 业务蓝图与流程图
- 版本：v1.0.1 · 2026-11-25
- 交付性质：**设计交付（候选）**。本仓库是供 reviewer 独立复核的候选，不是已发布版本，也不代表“可提交”。
- 数据性质：**全部为虚构示例**。不含客户名称、真实个人信息或企业信息。

## 1. 这是什么

用一条泳道流程描述资源方从入库申请到上架、暂停、复审、下架的完整生命周期，并配套三张可直接用于评审的表：

| 文件 | 内容 |
|---|---|
| `diagram/resource-onboarding-swimlane.drawio` | 可编辑源文件（5 条泳道、2 个排他网关、1 个定时事件、7 个状态） |
| `diagram/resource-onboarding-swimlane.svg` | 与 drawio 同坐标的矢量源（渲染基准） |
| `diagram/resource-onboarding-swimlane.png` | 6000×4100 位图（2x，目检用） |
| `diagram/resource-onboarding-swimlane.pdf` | A2 横向矢量 PDF（594×405.9 mm，1 页） |
| `docs/step-table.md` | 步骤说明表 S01–S15，与图中角标一一对应 |
| `docs/state-enum.md` | 7 状态枚举（ST01–ST07）+ 暂停/下架触发条件 |
| `docs/catalog-fields.md` | 资源目录字段清单 28 项，逐项标注会员可见性 |
| `docs/s1-intake-report.md` | S1-INT mock 导入报告（明确标注虚构，非客户输入） |
| `docs/drawio-open-check.md` | draw.io 桌面版 32.7.4 实开验证记录 + 截图 |
| `docs/METRICS.json` | 计数单一来源；由 `tools/metrics.py` 独立复核 |

**不在本单范围**：撮合交易、结算、合同正文、后端/前端/小程序实现、客户访谈结论。

## 2. 怎么打开

- **drawio**：用 draw.io / diagrams.net 桌面版或网页版打开 `.drawio`；泳道为容器，节点可拖动，连线带正交路由。
- **PNG**：任意图片查看器；建议 100% 或更高缩放查看细节。
- **PDF**：任意 PDF 阅读器；A2 横向，适合打印或投屏。文字为矢量，可搜索。
- **drawio 实开验证**：见 `docs/drawio-open-check.md`（桌面版 32.7.4，含 `drawio-open-check.png` 与 `drawio-export.png`）。

> SVG 是视觉基准；drawio 中 HTML 标签的换行由 draw.io 自行排版，可能与 SVG 有 1–2 px 差异。以 PNG/PDF 为准。

## 3. 图中约定

- **5 条岗位泳道**（自上而下）：资源方、会员经理、运营、管理层、会员空间平台。
- **2 个排他网关**（菱形 + × 标记）：
  - 资质审核：通过 / 补件 / 拒绝；
  - 金融、投资类管理层复核：通过 / 不通过（仅金融、投资类进入）。
- **7 个状态**（圆角标签）：申请中、待补件、审核中、已上架、已暂停、已下架、已拒绝。
- **定时事件**：双圆时钟，标注“每 12 个月 · 定时事件”。
- **建议值**：评分阈值（平均分 < 3）与复审周期（12 个月）在图中两处标注「待客户确认」。
- **6 类资源**：客户渠道、供应商服务、投资机构、人才服务、政策服务、专家顾问（图注 A1）。
- **评价**：每次撮合结束后由需求方在 1–5 分中打分；平均分 < 3 或收到有效投诉时暂停并复查。
- **退出**：资源方可主动提出退出，经运营确认后下架。

## 4. 复跑与检查

环境：

- Python 3.11+（检查脚本只使用标准库，无 pip 依赖）。
- 重新渲染时才需要 Node 22+ 与系统自带 Edge/Chrome；仓库已提交 PNG/PDF，阅读不需要 Node。
- 操作系统：Windows（已验证）；Linux/macOS 需把 `render.mjs` 的浏览器路径改为本机 Chrome/Chromium，其余脚本跨平台。

命令（在本目录执行）：

```bash
# 1) 从同一内容源重建图与三张表
python tools/build.py

# 2) 重新渲染 PNG/PDF，并用真实浏览器测量文字是否溢出
node tools/render.mjs

# 3) 结构/数量/一致性检查（不导入 model.py，独立解析产物）
python scripts/check_delivery.py --root . --full

# 4) 真实反例：删泳道、改状态名、删字段、删网关、删触发条件、删 S15→S14 退出边、注入 U+FFFD
python scripts/run_negative_tests.py

# 5) 数字独立重算（与 docs/METRICS.json、文档标题中的数字对账）
python tools/metrics.py

# 6) 一键验收（FAIL-first，含干净副本复跑）
python scripts/run_acceptance.py

# 7) 打包候选 zip + MANIFEST + gate-report
python tools/package.py
```

最近一次结果见 `03-EVIDENCE.md` 与 `artifacts/acceptance.json`；不要引用本文档代替证据。

## 5. S1-INT 对接点（mock 先行）

本单依赖 **S1-INT（调研与访谈工具）**，当前**未收到真实访谈纪要或 SOP 卡片**。为不阻塞交付，提供同构 mock：

```bash
python integrations/s1_int_mock/mock_server.py      # 默认 127.0.0.1:8765
# 或：PORT=8877 python integrations/s1_int_mock/mock_server.py

curl "http://127.0.0.1:8765/api/v1/interviews?project=2267"
curl "http://127.0.0.1:8765/api/v1/sop-cards?project=2267"
```

接口契约：

- `GET /api/v1/interviews?project=2267`
  → `{ "meta": {...,"fictional":true}, "data": [ { "id","title","captured_at","statements":[ {"id","quote","requirement_hint","confirmed"} ] } ] }`
- `GET /api/v1/sop-cards?project=2267`
  → `{ "meta": {...}, "data": [ { "id","title","items":[...],"requirement_hint" } ] }`
- `GET /healthz` → `{"status":"ok"}`
- 非 2267 的 project 返回 404；fixture 不可读返回 500。

替换真实接口的步骤：

1. 把 S1-INT 的真实响应保存为同 schema JSON（或在 `mock_server.py` 中改为调用真实服务）。
2. `python tools/import_s1_notes.py --input <real.json>` 生成新的 `docs/s1-intake-report.md`。
3. 逐条比对；与任务原文冲突时以任务原文/客户书面澄清为准，修改 `tools/model.py` 后重建。
4. 升 patch 版本，在图脚注与 `03-EVIDENCE.md` 记录“修订来源：S1-INT:<id>#<statement>”。

> mock 只验证接口可解析，**不改变图的内容**，也**不是**客户输入的验收证据。

## 6. 数据与保密

- 图中与表中的企业、机构、人名、联系方式、字段示例均为虚构；不含客户名称。
- 联系方式的示例写法为 `138****0000`（脱敏占位），不是真实号码。
- 本仓库不读取、不打印、不保存任何 token、密码或密钥；S1-INT mock 只绑定 `127.0.0.1`，不访问外网。
- 依赖：零第三方 Python 包；渲染仅用系统浏览器。

## 7. 已知限制与待确认

1. **未收到真实访谈纪要/SOP**：图按任务原文绘制；收到材料后按其修订并标注来源（见 §5）。
2. **评分阈值 3 分、有效评价最少条数**：建议值，待客户确认。
3. **复审周期 12 个月**：建议值，待客户确认；是否按资源类型分档未定。
4. **“有效投诉”判定人**：当前设计为运营核实、必要时管理层复核；待客户确认。
5. **暂停整改期限**：表中建议 10 个工作日，图中未画时限；待客户确认。
6. **会员评价的泳道归属**：会员（需求方）不在 5 条岗位泳道内，评价步骤放在“会员空间平台”泳道并标注“会员经小程序”；如需第 6 条泳道，需客户确认。
7. **drawio 与 SVG 的换行差异**：见 §2；以 PNG/PDF 为准。
8. **平台 deadline 已过期**（2026-11-23）：候选生产不依赖它，但是否仍可提交由 reviewer/平台确认。

## 8. 版本

- v1.0.1 · 2026-11-25 · 证据编码修复：子进程强制 UTF-8，检查器新增 U+FFFD 断言与 N7 反例。
- v1.0.0 · 2026-11-25 · 初版候选：5 泳道、2 XOR、7 状态、28 字段、15 步骤、定时复审、S1-INT mock。
- 修改流程：改 `tools/model.py` → `python tools/build.py` → `node tools/render.mjs` → 全套检查 → 升 patch 版本。
