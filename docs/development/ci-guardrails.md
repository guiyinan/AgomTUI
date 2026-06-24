# CI Guardrails

第一版 CI 使用 GitHub Actions，目标是把当前已经存在且稳定的质量检查固化为 PR 护栏。

## 触发条件

- push 到 `main`
- pull request 指向 `main`

## Python 版本

CI 使用 Python `3.11`，与当前包配置中的 `requires-python = ">=3.11"` 对齐。

## 当前检查项

- core runtime contract tests
- compiler tests
- runtime asset helper and non-Django host example tests
- Django host tests
- `examples/metadata/minimal.tui_operation_graph.json` schema 校验
- `examples/metadata/rich_components.tui_operation_graph.json` schema 校验
- `examples/metadata/generic_operations.tui_operation_graph.json` schema 校验
- `examples/metadata/minimal.tui_operation_graph.json` 可用性检查
- `examples/metadata/rich_components.tui_operation_graph.json` 可用性检查
- `examples/metadata/generic_operations.tui_operation_graph.json` 可用性检查

## 第一版依赖策略

仓库暂时没有统一 requirements 文件。CI 只安装当前检查必需的最小依赖：

- `jsonschema>=4.21`
- `django>=5.0,<6`

后续如果引入统一 workspace 安装、包构建或 adapter 依赖，应把 CI 改成使用同一套安装入口，避免本地和 CI 分叉。

## 明确不做的事

第一版不引入 Ruff、Black、mypy、coverage 或 pre-commit。等包边界、adapter 形态和发布流程更稳定后，再升级为标准质量门。

## 失败处理

- metadata 校验失败：先确认 artifact 是否被直接手改；需要保留的终态调整应进入 override。
- metadata 可用性检查失败：优先检查 screen 是否有 action / panel、默认 action 是否跨 screen、chart / host_slot view_model 是否缺路径、必填隐藏字段是否缺默认值。
- governed action 测试失败：优先检查 confirmation、reauth、audit 是否被绕过。
- Django host 测试失败：优先确认 adapter contract、metadata endpoint 和 action endpoint 是否仍符合 runtime 预期。
