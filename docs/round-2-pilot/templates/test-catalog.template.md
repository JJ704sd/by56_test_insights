# Test Catalog 登记说明（P0）

对应 JSON 文件：[`test-catalog.template.json`](test-catalog.template.json)。当前 JSON 是
故意 fail-closed 的空模板：`schema_version`、`catalog_version` 和 `tests` 不能直接用于
真实运行。不得填入 examples 的 ID、推测用例或仓库测试名称来凑足目录。

## R2-G0 必须满足

- 来自批准的真实模块范围，完成脱敏和来源登记；
- 30–50 条唯一 `tests[].id`，覆盖 smoke、核心链路、高风险标签以及已评审的组件/上下游；
- 每条测试至少有 `id` 和 `automated`，其余关联字段按 v1 Schema 和受控目录来源填写；
- `schema_version` 使用当前批准的 v1 值，`catalog_version`、来源和评审引用可追溯；
- 如果使用 `automation_policy`，必须由批准来源提供完整策略字段；没有批准的 policy 不得
  写成 `APPROVED`；
- 目录变更生成新版本，不能覆盖运行中或历史证据引用的目录。

## 现有契约与运行方式

规则核心和结构校验复用 `qualityctl.validation`、v1 JSON Schema 与 `qualityctl select`。
在人工范围冻结后使用：

```powershell
$env:PYTHONPATH = "src"
python -m qualityctl select <approved-test-catalog.json> <frozen-risk-manifest.json>
```

只有结构和规则结果可定位、输出已写入新的受控证据目录且没有生产写入权限时，才可进入
影子记录。`READY` 只表示目录输入可供下一步处理，不表示测试已执行或已通过。

## 字段来源登记

| 字段/关系 | 必须引用的来源 | 未提供时 |
| --- | --- | --- |
| `id`、suite、priority、labels | 测试管理/代码仓库批准快照 | 不得进入主分母 |
| `components`、`dimensions`、`risks` | 组件/上下游映射和八维风险评审 | `BLOCKED`/待补证据 |
| `historical_escape` 类标签 | 可复核的历史逃逸记录 | 不得推测填写 |
| `automated`、`automation_fit` | 当前真实执行/维护记录和 ROI policy | 不得用 examples 成本代替 |
| catalog 版本与审批 | 受控来源、批准人、时间、证据引用 | `PENDING_APPROVAL` |
