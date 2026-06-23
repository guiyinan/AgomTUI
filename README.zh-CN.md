# AgomTUI

[English](./README.md)

如果你已经有 API，却总是卡在“还要再做一套能用的后台工作台界面”，AgomTUI 就是把这部分重复劳动直接收掉的。

## 它解决的痛点

大多数内部工具都会卡在同一类问题上：

- 数据接口已经有了，但真正能给运营或风控人员用的界面还没有
- 每做一个新工具，都要重新拼表格、详情页、筛选、分页、任务表单
- 有风险的操作需要确认和约束，但这些规则总是每个页面重复做
- 有的团队想先把它当成独立控制台快速跑起来，另一些团队则希望把同一套工作台能力直接嵌入现有 Django 或内部系统里

AgomTUI 就是为这类空档准备的。它提供一个可复用的运行时工作台外壳，让你不用每次都从零搭操作界面，同时保留把同一套 runtime 独立运行或挂进宿主应用的能力。

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
- 一套 metadata contract，用来描述 screen 和 action，而不是反复重写整套 UI
- 一条从代码证据到已发布 runtime metadata 的路径
- 一种 host adapter 模式，让同一套 runtime 可以独立运行，也可以挂进别的应用外壳

## 仓库内容

- `packages/agomtui-core/`：schema、validator、runtime contract，以及通用的服务端运行时 helper
- `packages/agomtui-runtime/`：提取出来的浏览器端 shell 资产和 renderer 参考实现
- `packages/agomtui-compiler/`：编译期 collector / AI synthesizer / validator / publisher 骨架
- `demo/`：可直接运行的独立 demo、compiler walkthrough、integration demo 和 migration 页面
- `adapters/django/`：第一版 Django adapter 的说明
- `examples/metadata/`：最小 metadata 示例
- `docs/`：提取边界、迁移和架构说明

## 对使用者最直接的价值

如果你在判断它到底省不省事，最直接的答案是：

- API 可以继续沿用，不用推倒重来
- 不用每做一个内部工具都重写一遍操作界面
- 一套 runtime 可以服务多块内部工作流
- 可以先做独立控制台，后面再挂回宿主系统，不用把 runtime 再重做一次

## 现在已经可复用的部分

- metadata schema（`tui-metadata.v3`）
- metadata 校验与压缩
- 通用服务端 runtime helper：
  - view-model inference
  - confirmation contract
  - missing-fields contract
  - password-challenge detection
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

### 2. 跑测试

Compiler 测试：

```powershell
$env:PYTHONPATH='D:\githv\AgomTUI\packages\agomtui-core\src;D:\githv\AgomTUI\packages\agomtui-compiler\src'
python -m unittest discover packages\agomtui-compiler\tests
```

Core runtime 测试：

```powershell
$env:PYTHONPATH='D:\githv\AgomTUI\packages\agomtui-core\src'
python -m unittest discover packages\agomtui-core\tests
```

Django host 测试：

```powershell
python demo\django_host\manage.py test django_host
```

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

## 建议从这里开始

- 先看 `docs/product-split.md`，明确提取边界
- 再看 `docs/compiler-architecture.md`，理解编译期结构
- 再打开 `packages/agomtui-runtime/reference/tui_workbench.reference.html`，看当前 shell 参考实现
