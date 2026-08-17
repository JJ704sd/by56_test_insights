# 非阻塞影子运行手册（P0）

本手册把现有 `qualityctl` CLI、v1 Schema 和五个 MCP 工具串成旁路流程，不新增规则核心、
不改变现有发布流程，也不提供生产写入能力。它只在 R2-G0 签署后用于真实试点；当前
`R2-G0` 未通过，不能用本手册启动 8 周时钟。

## 1. 运行前硬检查

每个变更先做以下检查，任何一项失败都停止：

- [ ] `pilot_id`、模块、owner、受控存储和策略版本均已批准且可定位。
- [ ] 变更有唯一 `change_id`、提交/构建引用和版本类型。
- [ ] 测试负责人已经在 [manual-scope 模板](templates/manual-scope.template.md) 中冻结人工风险/回归范围，
  并记录冻结时间；工具结果尚未展示给冻结人。
- [ ] manifest、catalog、Agent spec/runs（如适用）均复制到本次唯一证据目录，输入摘要已
  做 Secret/敏感数据检查。
- [ ] 证据目录不存在；如果目录已经存在，停止并创建新的 `run_id`，不得覆盖或清理旧目录。
- [ ] 运行环境是隔离测试环境；没有生产凭据、部署 token、写库权限、放量或回滚权限。
- [ ] 已确认本次使用的 `qualityctl`/Schema/插件版本和五个工具名称；版本不一致时新建运行
  记录，不在旧证据上覆盖。
- [ ] `qualityctl --help` 和已批准的 MCP host/stdio 启动检查已完成；检查只读，不把影子
  job 设置为 required check。

人工范围未冻结时允许的唯一动作是记录一次 `EXCLUDED_PRE_FREEZE` 的流程演练；该结果
不得进入主分母，不得展示为试点结论。

## 2. 推荐证据目录

以下路径是逻辑结构，实际根目录必须替换为已批准的受控存储位置；不要在仓库创建真实
`pilots/` 目录：

```text
<approved-evidence-root>/pilots/<pilot_id>/changes/<change_id>/<run_id>/
├── input/
│   ├── risk-manifest.json
│   ├── test-catalog.json
│   ├── agent-spec.json          # Agent 适用时
│   └── agent-runs.jsonl         # Agent 适用时
├── freeze/
│   └── manual-scope.md
├── raw/
│   ├── risk-check.json
│   ├── selection.json
│   ├── agent-report.json        # Agent 适用时
│   ├── roi/                     # 每个候选一个不可覆盖输出
│   └── gate-report.json
├── logs/
│   ├── commands.stdout.log
│   ├── commands.stderr.log
│   └── exit-codes.json
├── reruns/<rerun_id>/           # 首次运行和每次重跑分目录保存
├── adjudication.md
└── checksums.sha256
```

原始输入、原始输出、重跑、差异和裁决不可覆盖。汇总只能引用这些文件；不要手工编辑
`raw/` 下的工具输出。

## 3. 冻结后运行现有 CLI

以下命令只在隔离环境执行，并将每次 stdout、stderr、退出码和运行时间保存到本次唯一
目录。PowerShell 中先确认目标目录不存在；`qualityctl` 的 `--output` 会写文件，因此
禁止对已有目录重跑。

```powershell
$env:PYTHONPATH = "src"
$evidenceRoot = "<approved-evidence-root>"
$pilotId = "<approved-pilot-id>"
$changeId = "<unique-change-id>"
$runId = "<unique-run-id>"
$runDir = Join-Path $evidenceRoot "pilots\$pilotId\changes\$changeId\$runId"

if (Test-Path -LiteralPath $runDir) {
    throw "Evidence directory already exists; use a new runId. No overwrite is allowed."
}
New-Item -ItemType Directory -Path $runDir -Force | Out-Null
New-Item -ItemType Directory -Force -Path @(
    (Join-Path $runDir "input"),
    (Join-Path $runDir "freeze"),
    (Join-Path $runDir "raw"),
    (Join-Path $runDir "logs"),
    (Join-Path $runDir "reruns")
) | Out-Null

# 仅从已批准的受控来源复制脱敏输入；不要从 examples 或仓库 output 复制。
# Copy-Item -LiteralPath "<approved-source>\risk-manifest.json" -Destination (Join-Path $runDir "input\risk-manifest.json")
# Copy-Item -LiteralPath "<approved-source>\test-catalog.json" -Destination (Join-Path $runDir "input\test-catalog.json")
# 复制后先写入 checksums/脱敏检查，再执行下面的命令。

# 人工冻结文件必须先进入 $runDir\freeze；以下命令不执行生产动作。
python -m qualityctl risk-check `
  "$runDir\input\risk-manifest.json" `
  --output "$runDir\raw\risk-check.json"

python -m qualityctl select `
  "$runDir\input\test-catalog.json" `
  "$runDir\input\risk-manifest.json" `
  --output "$runDir\raw\selection.json"

# Agent 适用且策略已批准时才运行；不适用时保留批准的 NOT_APPLICABLE 证据。
python -m qualityctl agent-eval `
  "$runDir\input\agent-spec.json" `
  "$runDir\input\agent-runs.jsonl" `
  --output "$runDir\raw\agent-report.json"
```

命令返回非零时仍要保存 stderr、退出码和输入引用，不要删除失败记录或用重试结果覆盖
首次失败。`risk-check`/`select`/`agent-eval` 的结果只能描述校验、选集或 Agent 评测状态，
不能描述测试已执行或发布已通过。

## 4. 五个 MCP 工具的旁路调用顺序

使用现有 `qualityctl-mcp` stdio 服务或已批准的 MCP host；不要在本手册中增加另一个规则
实现。每次调用的原始请求、响应、结构化结果、`is_error`、时间和工具版本都保存到独立
文件。

| 顺序 | MCP 工具 | 传入原始证据 | 影子用途与限制 |
| --- | --- | --- | --- |
| 1 | `validate_change_risks` | `risk-manifest.json` | 校验八维风险；结构/语义失败原样记录 |
| 2 | `select_regression_scope` | `test-catalog.json` + `risk-manifest.json` | 生成选集、排除和覆盖缺口；不得改写人工基线 |
| 3 | `evaluate_agent_evidence` | 冻结 `agent-spec` + 全部 runs | 仅 Agent 适用且 policy 已批准时调用；保留失败域和全部重试 |
| 4 | `assess_automation_roi` | catalog 候选 + 已批准 ROI policy | 仅提供候选建议；不参与发布 Gate，不补造成本 |
| 5 | `decide_release_gate` | 原始 manifest、catalog、Agent spec/runs（如适用） | 重新计算权威影子 Gate；不能传调用方自填的 PASS 或 evidence ref |

`decide_release_gate` 的 `release_allowed` 即使为 `true`，在 Round 2 也只是工具原始
结果，不能改变正式发布结论。任何 `FAIL`、`BLOCKED`、`REVIEW_REQUIRED` 或策略不完整
都必须保留并由责任人处理，不能由 LLM、报告模板或重试改成 `PASS`。

CLI 当前只提供 `risk-check`、`select`、`agent-eval` 三个确定性入口；最终 Gate、ROI
和五个 MCP 工具的传输验证使用现有 `qualityctl-mcp`/已批准 MCP host 完成，不在本手册或
模板中复制一套规则实现。

## 5. 解盲、差异和正式发布

1. 测试负责人确认 `freeze/manual-scope.md` 已签名/版本化后，才把工具结果提供给差异
   裁决人。
2. 生成 [adjudication 模板](templates/adjudication.template.md)，每个差异必须有分类、
   证据引用、裁决人和时间。高风险差异在下一次发布前关闭或明确阻塞。
3. 继续执行现有正式测试和发布流程。影子结果不能自动修改正式选集、发布状态、豁免或
   回滚；影子任务的失败不得成为现有发布流水线的 required check。
4. 回填实际执行结果、逃逸、人工耗时、维护/误报/flaky/runner 数据，并生成迭代摘要。
5. 任何冻结计划之外的运行放入独立 `out_of_plan/` 或新的变更记录，不合并原计划分母。

## 6. 非阻塞和安全证明

- 本 P0 选择运行手册作为非阻塞入口，没有新增 required CI workflow，也没有修改现有
  `.github/workflows/python-qualityctl.yml` 的发布依赖关系。
- 运行器只读隔离输入和代码；不得持有生产发布权限、生产写入权限或生产数据访问权限。
- 影子结果不触发部署、放量、回滚、审批、范围修改或系统写回。
- 发生错误 `PASS`、确认的高风险漏选、敏感数据事件、未经授权自动放行或原始证据覆盖时，
  立即停止扩面，通知停止责任人并回到现有正式流程。
- 如果需要以 CI 运行，必须单独创建只读、`workflow_dispatch`/非 required 的 job，显式
  设置最小权限并通过审批；不得把本手册的占位路径直接接入生产流水线。
