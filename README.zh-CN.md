# AgomTUI

[English](./README.md)

**把后端 API 和业务逻辑直接变成可用的前端操作台 TUI。**

AgomTUI 面向已经有后端 API、但还缺内部操作界面的系统开发者。它把 API 和业务能力转换成 metadata，再用 metadata 自动生成可用的前端控制台。

目标很直接：几乎 0 前端编码、低痛苦生成内部工具 UI。

## 最短用法

把这个仓库地址交给 Codex / Claude Code，让它先理解项目边界和 contract，再接你的后端：

```text
请阅读 https://github.com/guiyinan/AgomTUI，理解 AgomTUI 的 metadata、runtime、compiler 和 host adapter 边界。
基于我的后端仓库/API，按 AgomTUI contract 生成或接入一个可运行的内部操作台 TUI，并补齐必要的测试和文档。
```

## 开发文档

- [开发文档总入口](docs/README.md)
- [架构说明](docs/architecture/README.md)
- [开发标准](docs/development/development-standards.md)
- [测试命令](docs/development/testing.md)
- [CI 护栏](docs/development/ci-guardrails.md)

## 它做什么

AgomTUI 提供一条从后端能力到可用界面的完整路径：

1. 你已有的 API 和业务逻辑描述系统能做什么。
2. AgomTUI 根据这些证据生成 runtime metadata。
3. 浏览器 runtime 根据 metadata 渲染 UI。
4. 使用者拿到列表、详情、筛选、动作表单、确认弹窗和调试能力，而不是每个流程都重新写一个前端页面。

它的核心价值不是某个单独组件库，而是一套把系统能力稳定转成操作界面的生成路径。

## 对开发者意味着什么

- 现有 API 和后端逻辑可以继续沿用。
- 不用为每个内部工具重复写表格、表单、详情页、动作面板和确认流程。
- 可以先生成一套能用的 UI，再只在真正有业务差异的地方微调 metadata 或宿主集成。
- 可以独立运行，也可以把同一套 runtime 挂进现有系统。

## 通用性如何？

AgomTUI 对“基于 API 的内部操作台”有较强通用性，但它不是所有前端 UI 的通用替代品。

它最适合这类产品形态：

- 数据列表、详情页、筛选和搜索
- 带参数和结果的操作动作
- 确认、权限、审计、重新验证身份等治理规则
- 业务逻辑由后端持有，并通过 API 或 action executor 暴露

所以它适合内部运营台、管理后台、风控工作台、审核系统、治理面板和内部数据管理界面。

它不适合作为 C 端产品页、营销站、可视化编辑器、游戏或高度定制交互体验的主 UI 方案。这些界面仍然可以调用同样的 API，但通常需要专门设计和手写前端，而不是主要依赖 metadata 生成页面。

## UI 能二次开发吗？

可以。AgomTUI 应该被理解为“生成出来的基础 UI + 可扩展机制”。

推荐的二次开发层次是：

- 通过 metadata 调整页面名称、分组、排序、字段文案和 action 位置
- 通过 host adapter 接入鉴权、权限、action 执行、审计存储和部署形态
- 扩展 renderer，支持新的 metadata-driven 视图类型
- 调整主题和 shell，让它适配产品品牌或宿主系统
- 使用经过 review 的 override 文件，保留那些需要跨生成周期存在的手工调整

核心规则是：业务逻辑留在宿主系统，界面尽量由 metadata 驱动。能被多个工具复用的能力，应该沉到 runtime 或 metadata contract；只服务某个宿主的能力，应该放在 host adapter 或 metadata override 里。

## 能插入图表和富组件吗？

可以。AgomTUI 应该支持 ECharts、Chart.js、HTMX partial、Mermaid、Markdown renderer、日期选择器、代码编辑器这类富组件，但它们应该通过扩展点接入，而不是写死到每个生成页面里。

AgomTradePro 的经典前端里已经有类似模式：

- ECharts 用在宏观时间线、筛选 dashboard、股票详情图、组合配置 / 收益图、公开分享收益曲线
- Chart.js 用在部分审计图和估值图
- HTMX 用于服务端 partial 局部刷新和交互面板
- Flatpickr、SweetAlert2、Alpine.js 用作轻量页面增强
- Mermaid、Marked、CodeMirror 用于图示、Markdown 渲染和脚本编辑

AgomTUI 适合分三层支持这些能力：

- 内置 metadata renderer：支持常见 line、bar、pie、KPI trend、表格 + 图表等通用视图
- 自定义 renderer extension：让宿主注册 `renderer: "echarts"`、`renderer: "code-editor"` 这类专用组件
- host slot：允许宿主插入受控的服务端渲染片段；如果宿主本来就使用 HTMX，可以在这些 slot 里使用 HTMX partial

HTMX 更适合宿主挂载和服务端渲染集成，尤其是 Django 这类页面。独立 metadata runtime 的默认路径仍应是 API 数据 + runtime renderer。这样 core 保持可移植，同时宿主又可以在 metadata 不够表达的地方插入更强的组件。

## 开发护栏

AgomTUI 需要 CI 和开发规则，因为它的价值依赖稳定的 metadata、runtime contract、governed action 和 adapter 边界。当前标准见 [docs/development/development-standards.md](docs/development/development-standards.md)，第一版 CI 护栏见 [docs/development/ci-guardrails.md](docs/development/ci-guardrails.md)。

## 它解决的痛点

大多数内部工具都会卡在同一类问题上：

- 数据接口已经有了，但真正能给运营或风控人员用的界面还没有
- 每做一个新工具，都要重新拼表格、详情页、筛选、分页、任务表单
- 系统开发者不得不花前端时间描述那些其实已经隐含在 API 里的页面结构
- 有风险的操作需要确认和约束，但这些规则总是每个页面重复做
- 有的团队想先把它当成独立控制台快速跑起来，另一些团队则希望把同一套工作台能力直接嵌入现有 Django 或内部系统里

AgomTUI 就是为这类空档准备的。你不需要为每个工具手写表格、详情、筛选、表单和确认弹窗，只需要让生成出来的 metadata 描述界面，并在宿主系统真正有差异的地方做少量接入和定制。

## 适合什么场景

当你想做下面这些东西时，这个项目比较合适：

- 内部运营 / 运维控制台
- 强治理、强确认、强审计的中后台工具
- 挂载到 Django 或其他 Web 宿主中的 TUI 界面
- 已经有 API，但还缺一套稳定操作体验的内部平台

## 为什么上手会有感觉

只看 demo，用户就能马上理解三件事：

- 独立工作台长什么样
- 同一套 runtime 怎么挂回宿主系统
- 导航和动作面板是怎么由 metadata 驱动，而不是每页手写一遍 UI

## Demo

### 概览工作区

![AgomTUI 概览工作区](docs/assets/demo-overview.png)

### 独立运行时工作台

![AgomTUI 独立运行时](docs/assets/demo-standalone.png)

### 宿主挂载运行时

![AgomTUI 宿主挂载运行时](docs/assets/demo-host-mounted.png)

## 你实际拿到什么

- 一个已经带导航、说明栏、筛选、分页、任务表单、确认弹窗、原始响应调试抽屉的终端式工作台
- 一套 metadata contract，让生成出来的 metadata 描述 screen 和 action，而不是反复重写整套 UI
- 一条从 API 和代码证据到已发布 runtime metadata 的 compiler 路径
- 一种 host adapter 模式，让同一套 runtime 可以独立运行，也可以挂进别的应用外壳

## 高层工作方式

技术路径可以概括为四步：

1. 从宿主系统收集 API 或代码证据
2. 编译生成 AgomTUI runtime metadata
3. 把 metadata 提供给 runtime shell
4. 把 action 执行、鉴权和审计接回宿主系统

前端界面由 metadata 生成；业务逻辑和执行权仍然留在宿主系统里。

## 必须基于 Django 或 Python 吗？

不必须。AgomTUI 的前端 runtime 框架本质上是浏览器端 shell，加上一套 metadata / action contract。它不要求宿主必须是 Django，也不要求运行时 UI 必须接 Python 后端。

这个仓库里的 Python / Django 分工是：

- Python 是当前 schema helper、compiler 骨架、测试和 demo server 的实现语言。
- Django 是第一版 host adapter 示例，因为它是当前优先集成目标。
- 非 Django 宿主也可以使用同一套 runtime，只要它能提供 metadata、执行 action，并返回 AgomTUI 约定的响应 contract。

换句话说：Django / Python 是已提供的集成路径，不是这套前端框架的硬性前提。后续 adapter 可以面向 FastAPI、Flask、Node 服务、Java 服务，或者只基于 OpenAPI 的后端。

## 仓库内容

- `packages/agomtui-core/`：schema、validator、runtime contract，以及通用的服务端运行时 helper
- `packages/agomtui-runtime/`：提取出来的浏览器端 shell 资产、renderer 参考实现和可嵌入资产 helper
- `packages/agomtui-compiler/`：编译期 collector / AI synthesizer / validator / publisher 骨架
- `demo/`：可直接运行的独立 demo、compiler walkthrough、integration demo 和 migration 页面
- `adapters/django/`：第一版 Django adapter 的说明
- `examples/metadata/`：最小、富组件和通用运营 metadata 示例
- `examples/hosts/`：宿主集成示例，包括一个非 Django 的标准库 host
- `docs/`：开发文档、架构说明、迁移计划和 CI 护栏

## 对使用者最直接的价值

如果你在判断它到底省不省事，最直接的答案是：

- API 可以继续沿用，不用推倒重来
- metadata 可以从 API / 代码证据生成，不需要手工描述每个页面
- 标准内部工具场景下，几乎可以不写前端代码就得到可用 UI
- 不用每做一个内部工具都重写一遍操作界面
- 一套 runtime 可以服务多块内部工作流
- 可以先做独立控制台，后面再挂回宿主系统，不用把 runtime 再重做一次

## 现在已经可复用的部分

- metadata schema（`tui-metadata.v3`）
- metadata 校验与压缩
- 面向终态手改的 metadata override 文件，避免重新生成时被覆盖
- 通用服务端 runtime helper：
  - view-model inference
  - confirmation contract
  - missing-fields contract
  - password-challenge detection
  - 无旁路的 governed action runner
  - 统一审计记录生成
  - runtime metadata normalization hooks
- runtime shell 布局、键盘模型、主题 token
- 通用 renderer：dashboard、datagrid、detail、message
- 通用 action framework：任务分组、确认、行填参、筛选、分页、inspector、modal、raw drawer
- 基于代码证据生成 metadata 的 compiler 边界
- 通用 metadata repository / action-executor contract

## 仍然属于宿主项目的部分

- 业务 screen 定义和 workflow 排序
- 已发布的业务 metadata graph
- 鉴权和登录流程
- DB 发布注册表与审计存储
- 内部 API 执行 adapter
- 宿主自己的业务词汇和 view-model 翻译
- 编译期扫描和采集策略

## 快速开始

### 1. 跑起 demo 栈

在仓库根目录执行：

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

如果你只想跑独立 demo：

```powershell
python demo\standalone_server.py
```

如果你想单独跑 Django 宿主：

```powershell
python demo\django_host\manage.py runserver 127.0.0.1:8030 --noreload
```

如果你想看非 Django 的标准库 host 示例：

```powershell
python examples\hosts\stdlib_host.py
```

然后打开 `http://127.0.0.1:8040/`。

### 2. 跑测试

本地测试和 metadata 校验命令维护在 [docs/development/testing.md](docs/development/testing.md)。同一组检查会在 GitHub Actions 中作为第一版 CI 护栏运行。

## 产品边界

AgomTUI 不是把 Django 模板拆一拆就结束了。真正稳定的产品边界是：

1. schema-first metadata core
2. compile-time metadata generator / promotion pipeline
3. runtime TUI shell and host adapters

建议的包划分：

- `agomtui-core`：schema、validator、runtime contract
- `agomtui-runtime`：浏览器 shell 与 renderer
- `agomtui-compiler`：证据 collector 与发布流水线
- `agomtui-adapters-*`：Django / FastAPI / OpenAPI-only 等宿主集成

## AI skill 路径

推荐的生成链路是：

1. collector 读取代码拥有的证据
2. `agomtui-compiler skill-request` 生成带 schema 约束的 prompt payload
3. 外部 AI skill 返回一个 `candidate_payload`
4. `agomtui-compiler compile-skill-result` 做校验、压缩并发布批准后的产物

提取后的 skill 应该优先生成宿主无关的 runtime metadata，不应该默认复刻某个具体产品的页面拆分、workflow 顺序或业务文案；只有证据里明确存在这些结构时，才应该带出来。

## 发布态 metadata 手改

发布态 metadata 是产物，不是源头。compiler 下一次写同一个发布路径时会覆盖该文件。需要保留的终态手改应写进经过 review 的 override 文件，并在每次 compile 时传入：

```powershell
agomtui-compile compile-static --project-root . --host-kind django --openapi-file examples\metadata\minimal.openapi.json --django-contract-file examples\metadata\minimal.django_contract_manifest.json --candidate-file examples\metadata\minimal.tui_operation_graph.json --override-file examples\metadata\minimal.override.json --output tmp\published.override.json --evidence-output tmp\evidence.override.json
```

不发布的本地校验 / 压缩命令：

```powershell
agomtui-compile validate-metadata --metadata-file examples\metadata\minimal.tui_operation_graph.json
agomtui-compile compact-metadata --metadata-file examples\metadata\minimal.tui_operation_graph.json --output tmp\published.compact.json
```

action 级治理字段已经纳入 schema 校验：`risk`、`confirmation_required`、`requires_password`、`audit_required`、`sensitive_level`、`executor`。`write` action 和非 GET 的 `admin` action 不能关闭必需的确认与审计。

## Governance-first runtime

AgomTUI 把确认、补填、重新验证身份和留痕作为 runtime 协议，而不是某个屏幕临时加的 UI。被治理的 action 应统一经过一条强制路径：

1. 缺必填字段时返回 `missing_fields` contract，shell 自动渲染补填提示
2. 需要确认的 action 在执行前被拦截，只有带确认证据重放后才继续
3. 需要验密的 action 必须经过宿主验证，不能靠客户端自称已验证
4. 需要留痕的 action 如果没有 audit sink，不能到达 executor
5. 成功、失败、被拦截、被拒绝的尝试都会产生 `tui-audit.v1` 记录

core 审计 schema 覆盖操作人、动作标识、脱敏入参、时间戳、确认证据、验密证据和执行结果。存储由宿主负责，但应使用 append-only 或防篡改存储；至少不能在正常业务代码中更新或删除既有审计记录。

## 建议从这里开始

- 先看 `docs/README.md`，确认文档地图
- 再看 `docs/architecture/product-split.md`，明确提取边界
- 再看 `docs/architecture/compiler-architecture.md`，理解编译期结构
- 再打开 `packages/agomtui-runtime/reference/tui_workbench.reference.html`，看当前 shell 参考实现
