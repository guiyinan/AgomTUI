# Development Standards

AgomTUI 的开发标准围绕一个目标：让 metadata、runtime contract、governed action 和 adapter 边界长期稳定。

## 分层规则

- `agomtui-core` 保持宿主无关，只放 schema、validator、runtime contract 和通用 helper。
- `agomtui-runtime` 是共享 shell，不放某个产品专属的 workflow、业务文案或权限逻辑。
- 宿主业务词汇、权限判断、action 执行、审计存储和部署形态放在 host adapter。
- 只服务单个宿主的终态调整放在 reviewed metadata override，不进入 core runtime。

## Metadata 规则

- 发布态 metadata artifact 是产物，不是源头；不要直接手改。
- 需要跨生成周期保留的改动必须进入 reviewed override 文件。
- 每个发布态 metadata artifact 都必须通过 `tui-metadata.v3` schema 校验。
- 可变高度的主工件使用 `screen.dashboard_layout=task_flow`，让主工作区承担纵向滚动；有界摘要卡片使用默认的 `adaptive_grid`。
- 新增 view model、renderer、host slot 或 action governance 字段时，先更新文档和 contract test。

## Governed action 规则

- `write` action 和非 GET 的 `admin` action 不能关闭必需的 confirmation 或 audit。
- 需要验密的 action 必须由宿主验证 re-auth，不能相信客户端自报状态。
- `audit_required` action 没有 audit sink 时不能到达 executor。
- 成功、失败、被拦截、被拒绝的 governed action 都应产生 canonical audit record。

## 测试规则

- 修改 metadata schema、action 协议、runtime governance 或 adapter 行为时，必须补 contract test。
- 修改 compiler collector、skill request 或 publish workflow 时，必须补 compiler 测试。
- 新增图表、HTMX slot、代码编辑器、Mermaid 等富组件 renderer 时，后续应补浏览器或视觉回归测试。
- 修复 bug 时优先补一个能复现问题的测试，再改实现。

## 文档规则

- 新增扩展点要先文档化，再在宿主项目里依赖它。
- README 保持产品介绍和快速入口；开发规则、CI、测试细节放在 `docs/development/`。
- 架构边界变化应同步更新 `docs/architecture/`。
