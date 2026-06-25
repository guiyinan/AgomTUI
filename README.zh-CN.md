# AgomTUI

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)

[English](./README.md)

**把后端 API 和业务逻辑直接变成可用的内部操作台 TUI。**

AgomTUI 面向已经有后端 API、action executor 和业务规则，但还缺操作界面的团队。它把 API 和代码里的证据转换成 runtime metadata，再由浏览器 runtime 渲染成可用的内部控制台。

这个项目的目标刻意收窄：用尽量少的前端编码生成内部工具 UI，同时让业务执行、权限和审计继续由宿主系统掌控。

## 最短用法

把这个仓库地址交给 Codex / Claude Code，让它先理解项目边界和 contract，再接你的后端：

```text
请阅读 https://github.com/guiyinan/AgomTUI，理解 AgomTUI 的 metadata、runtime、compiler 和 host adapter 边界。
基于我的后端仓库/API，按 AgomTUI contract 生成或接入一个可运行的内部操作台 TUI，并补齐必要的测试和文档。
```

## 快速开始

在仓库根目录运行 demo 栈：

```powershell
.\scripts\start_frontend.ps1
```

当前前端界面不是通过 npm/Vite dev server 启动，而是由 Python demo server 承载浏览器 runtime。完整启动脚本会同时启动两个本地服务：

- `http://localhost:8020/`：独立产品前端和 runtime demo
- `http://localhost:8030/`：Django 宿主 demo
- `http://localhost:8030/tui/`：挂载到 Django 宿主里的 runtime

等价的原始命令：

```powershell
python demo\run_demo_stack.py
```

打开：

- `http://localhost:8020/`：产品概览
- `http://localhost:8020/standalone/`：独立运行时工作台
- `http://localhost:8020/compiler/`：compiler walkthrough
- `http://localhost:8020/integration/`：宿主集成 contract demo
- `http://localhost:8020/migration/`：迁移清单
- `http://localhost:8030/`：Django 宿主页
- `http://localhost:8030/tui/`：挂载到 Django 的 runtime

只跑独立 demo：

```powershell
.\scripts\start_standalone.ps1
```

等价的原始命令：

```powershell
python demo\standalone_server.py
```

只跑 Django 宿主 demo：

```powershell
.\scripts\start_django_host.ps1
```

等价的原始命令：

```powershell
python demo\django_host\manage.py runserver 127.0.0.1:8030 --noreload
```

查看非 Django host 示例：

```powershell
python examples\hosts\stdlib_host.py
```

然后打开 `http://127.0.0.1:8040/`。

## 它做什么

AgomTUI 提供一条从后端能力到可用界面的稳定路径：

1. 从宿主系统收集 API 或代码证据。
2. 把这些证据编译成 AgomTUI runtime metadata。
3. 把 metadata 提供给浏览器 runtime shell。
4. 把 action 执行、鉴权、权限和审计接回宿主系统。

使用者会拿到列表、详情、筛选、动作表单、确认弹窗、补填缺失字段和原始响应调试能力。开发者不用为每个内部工具重复写表格、表单、详情页和确认流程。

## 适用场景

AgomTUI 适合：

- 内部运营 / 运维控制台
- 管理后台和内部数据管理工具
- 风控、审核、治理、审计较重的工作流
- 挂载到 Django 或其他 Web 宿主中的 TUI 界面
- 已经有 API，但还缺稳定操作体验的内部平台

它不适合作为 C 端产品页、营销站、可视化编辑器、游戏或高度定制交互体验的主 UI 方案。这些界面仍然可以调用同样的 API，但通常需要专门设计和手写前端，而不是主要依赖 metadata 生成页面。

## Demo 截图

### 概览工作区

![AgomTUI 概览工作区](docs/assets/demo-overview.png)

### 独立运行时工作台

![AgomTUI 独立运行时](docs/assets/demo-standalone.png)

### 宿主挂载运行时

![AgomTUI 宿主挂载运行时](docs/assets/demo-host-mounted.png)

## 核心概念

AgomTUI 围绕四个边界组织：

- `metadata`：runtime 消费的 screen、view、action、field 和治理 contract
- `runtime`：根据 metadata 渲染界面并管理操作交互的浏览器 shell
- `compiler`：从 API / 代码证据生成、校验、发布 metadata 的编译期路径
- `host adapter`：负责 metadata 服务、action 执行、鉴权、权限、审计和部署形态的接入层

关键规则是：业务逻辑留在宿主系统。AgomTUI 负责描述和渲染操作界面，不接管业务执行权。

## 定制方式

AgomTUI 应被理解为“生成出来的基础 UI + 扩展点”：

- 通过 metadata override 调整页面名称、分组、排序、字段文案和 action 位置
- 通过 host adapter 接入鉴权、权限、action 执行、审计存储和路由
- 通过 renderer extension 支持新的 metadata-driven 视图类型
- 调整主题和 shell，让它适配产品品牌或宿主系统
- 使用经过 review 的 override 文件，保留需要跨生成周期存在的手工调整

能被多个内部工具复用的能力，应该沉到 runtime 或 metadata contract；只服务某个宿主的能力，应该放在 host adapter 或 metadata override 里。

## 图表和富组件

AgomTUI 可以支持 ECharts、Chart.js、HTMX partial、Mermaid、Markdown renderer、日期选择器、代码编辑器这类富组件，但它们应该通过扩展点接入，而不是写死到每个生成页面里。

推荐分三层支持：

- 内置 metadata renderer：支持常见 line、bar、pie、KPI trend、表格 + 图表等通用视图
- 自定义 renderer extension：让宿主注册 `renderer: "echarts"`、`renderer: "code-editor"` 这类专用组件
- host slot：允许宿主插入受控的服务端渲染片段；如果宿主本来就使用 HTMX，可以在这些 slot 里使用 HTMX partial

独立 runtime 的默认路径仍应是 API 数据 + runtime renderer。host slot 适合 metadata 表达能力不够，或宿主已经拥有某段 UI 的场景。

## Governance-first runtime

AgomTUI 把确认、补填、重新验证身份和留痕作为 runtime 协议，而不是某个屏幕临时加的 UI。被治理的 action 应统一经过一条强制路径：

1. 缺必填字段时返回 `missing_fields` contract，shell 自动渲染补填提示
2. 需要确认的 action 在执行前被拦截，只有带确认证据重放后才继续
3. 需要验密的 action 必须经过宿主验证，不能靠客户端自称已验证
4. 需要留痕的 action 如果没有 audit sink，不能到达 executor
5. 成功、失败、被拦截、被拒绝的尝试都会产生 `tui-audit.v1` 记录

存储由宿主负责，但审计记录应使用 append-only 或防篡改存储。

## 仓库内容

- `packages/agomtui-core/`：schema、validator、runtime contract，以及通用的服务端运行时 helper
- `packages/agomtui-runtime/`：浏览器 shell 资产、renderer 参考实现和可嵌入资产 helper
- `packages/agomtui-compiler/`：编译期 collector / AI synthesizer / validator / publisher 骨架
- `adapters/django/`：第一版 host adapter 的说明
- `demo/`：可直接运行的独立 demo、compiler walkthrough、integration demo 和 migration 页面
- `examples/metadata/`：最小、富组件和通用运营 metadata 示例
- `examples/hosts/`：宿主集成示例，包括一个非 Django 的标准库 host
- `docs/`：开发文档、架构说明、迁移计划和 CI 护栏

## 包边界

建议的包划分：

- `agomtui-core`：schema、validator、runtime contract
- `agomtui-runtime`：浏览器 shell 与 renderer
- `agomtui-compiler`：证据 collector 与发布流水线
- `agomtui-adapters-*`：Django / FastAPI / OpenAPI-only 等宿主集成

Django 和 Python 是这个仓库提供的集成路径，不是 runtime contract 的硬性前提。任何宿主只要能提供 metadata、执行 action，并返回 AgomTUI 约定的响应 contract，就可以挂载 runtime。

## Compiler 链路

推荐的生成链路是：

1. collector 读取代码拥有的证据
2. `agomtui-compiler skill-request` 生成带 schema 约束的 prompt payload
3. 外部 AI skill 返回一个 `candidate_payload`
4. `agomtui-compiler compile-skill-result` 做校验、压缩并发布批准后的产物

生成出的 metadata 应优先面向宿主无关的 runtime 结构。workflow 顺序、业务词汇和 screen 分组，只有在证据明确支持时才应该带出来。

## 发布态 metadata 手改

发布态 metadata 是产物，不是源头。compiler 下一次写同一个发布路径时会覆盖该文件。需要保留的手改应写进经过 review 的 override 文件：

```powershell
agomtui-compile compile-static --project-root . --host-kind django --openapi-file examples\metadata\minimal.openapi.json --django-contract-file examples\metadata\minimal.django_contract_manifest.json --candidate-file examples\metadata\minimal.tui_operation_graph.json --override-file examples\metadata\minimal.override.json --output tmp\published.override.json --evidence-output tmp\evidence.override.json
```

不发布的本地校验 / 压缩命令：

```powershell
agomtui-compile validate-metadata --metadata-file examples\metadata\minimal.tui_operation_graph.json
agomtui-compile compact-metadata --metadata-file examples\metadata\minimal.tui_operation_graph.json --output tmp\published.compact.json
```

action 级治理字段已经纳入 schema 校验：`risk`、`confirmation_required`、`requires_password`、`audit_required`、`sensitive_level`、`executor`。`write` action 和非 GET 的 `admin` action 不能关闭必需的确认与审计。

## 开发文档

- [开发文档总入口](docs/README.md)
- [架构说明](docs/architecture/README.md)
- [开发标准](docs/development/development-standards.md)
- [测试命令](docs/development/testing.md)
- [CI 护栏](docs/development/ci-guardrails.md)
