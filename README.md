# qualityctl 测试智能原型

LLM 插件 MVP 见 [插件 MVP Spec](docs/plugin-mvp-spec.md)，后续维护先阅读
[插件开发者指南](docs/plugin-developer-guide.md)。插件源码位于
`plugins/quality-gatekeeper/`。

本仓库把现有测试规范和 `D:\quality_tests_skills` 中的 5 个质量技能，落成一组可复用、可审计的确定性组件。它不替代业务判断、产品验收或人工语义复核；它优先自动化高频、稳定、重复、判据清晰且人工成本高的环节。

当前包含：

- `risk-check`：强制从业务流程、异常路径、边界、权限、数据一致性、上下游依赖、副作用和恢复性八个维度完成变更风险盘点。
- `select`：依据版本类型、变更组件、上下游、风险维度和历史逃逸选择最小有效回归集，并识别值得自动化的人工用例。
- `agent-eval`：聚合 Agent 多次运行，分离 runner 无效、技术失败、确定性断言失败和人工语义复核，输出 Wilson 置信区间与门禁结论。
- `qualityctl evidence summarize-iteration`：只读取冻结的脱敏 `iteration-index@1.0`，校验 identity/digest/attestation/exact matrix，并确定性生成 `iteration-summary@1.0`；输出始终 `formal_release_effect: NONE`，不改变发布状态。

三类入参（manifest / catalog / agent_spec）与每条 Agent run 都有版本化 JSON Schema 与 Pydantic v2 校验器，详见 [`docs/schemas/v1/README.md`](docs/schemas/v1/README.md)。MCP 工具与 CLI 子命令均在边界先做结构校验，非 `ok` 时返回结构化错误。CI 流水线见 `.github/workflows/python-qualityctl.yml`（windows-latest + Python 3.11 + 单元测试 + MCP stdio smoke）。

截至 2026-08-19，当前工作区在 Python 3.14.6 下为 `148/148` 项单元测试通过；Python 3.11 CI 尚待对当前未提交增量运行。该数量是仓库验证快照，不是任何真实业务试点证据。Round 2 目前只有 [P0 试点脚手架](docs/round-2-pilot/README.md)，`R2-G0` 尚未满足，本次阶段输出为 `REMAIN_BLOCKED`，8 周影子时钟尚未启动。P1c §2.3 门槛拆分仍未获批准，stage core/CLI 未开始。

## 快速开始

规则核心使用 Python 3.10+；LLM 插件通过官方 Python MCP SDK 暴露工具。先安装：

```powershell
python -m pip install -e .
```

然后运行：

```powershell
$env:PYTHONPATH = "src"
python -m qualityctl risk-check examples/risk-manifest.json
python -m qualityctl select examples/test-catalog.json examples/risk-manifest.json --output output/selection.json
python -m qualityctl agent-eval examples/agent-cases.json examples/agent-runs.jsonl --output output/agent-report.json
python -m qualityctl evidence summarize-iteration <iteration-index.json> --output <new-summary.json>
python -m unittest discover -s tests -v
```

也可以安装为本地命令：

```powershell
python -m pip install -e .
qualityctl --help
```

设计结论、开源项目映射和分阶段路线图见 [自动化机会地图](docs/automation-opportunity-map.md)；可评审、可拆票、可验收的首版规划见 [MVP Spec](docs/mvp-spec.md)。下一阶段的真实业务影子试点、指标门槛和有限硬门禁准入标准见 [Round 2 Spec](docs/round-2-shadow-pilot-spec.md)；当前启动准备的工作包、依赖、证据合同和可拆票清单见 [R2-G0 Execution Spec](docs/round-2-g0-execution-spec.md)；启动审计与模板见 [Round 2 P0 脚手架](docs/round-2-pilot/README.md)。`R2-G0_READY` 之后的证据包、差异裁决、迭代聚合和 G1–G3 执行契约见 [Round 2 P1 Evidence Pipeline Spec](docs/round-2-p1-evidence-pipeline-spec.md)；当前可用脱敏 fixture 实施的完整性硬化与冻结迭代汇总见 [Round 2 P1b Spec](docs/round-2-p1b-iteration-summary-spec.md)；P1b 之后的可回放阶段建议、单调安全检查和 G1–G3 审计设计见 [Round 2 P1c Spec](docs/round-2-p1c-stage-recommendation-harness-spec.md)。这些文档当前都不表示真实试点已启动。

## 核心边界

- 不根据“自动化率”凑用例；没有稳定性、重复频率、清晰 Oracle 和正向节省时，不建议自动化。
- 不把 3-5 次采样包装成充分统计把握；报告样本数和区间。
- 不用重试覆盖首次失败；runner 无效、系统技术失败和语义失败分开统计。
- 不用 LLM Judge 独占计费、权限、安全、数据写入和核心业务判定。
- 不执行生产压测、安全扫描、故障注入、放量或回滚。
- P1b 只在脱敏 fixture/临时目录执行；`FIXTURE` summary 会显式标记 `business_evidence: false`。`REAL` index 在 `R2-G0_READY` 之前固定为 `BLOCKED_BY_R2_G0`，不会启动 8 周时钟。
