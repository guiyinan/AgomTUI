# AgomTUI

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)

[中文说明](./README.zh-CN.md)

**Turn backend APIs and business logic into a usable internal operations TUI.**

AgomTUI is for teams that already have backend APIs, action executors, and business rules, but still need a practical operator-facing UI. It converts API and code-owned evidence into runtime metadata, then renders that metadata as a browser-based operations console.

The product goal is narrow on purpose: get useful internal-tool UI with minimal frontend coding, while keeping business execution, permissions, and audit ownership in the host system.

## Quick prompt

Give this repository URL to Codex / Claude Code before wiring your backend:

```text
Read https://github.com/guiyinan/AgomTUI and understand the AgomTUI metadata, runtime, compiler, and host adapter boundaries.
Using my backend repository/API, generate or integrate a working internal operations TUI that follows the AgomTUI contract, including the necessary tests and docs.
```

## Quick start

Run the demo stack from the repository root:

```powershell
python demo\run_demo_stack.py
```

Open:

- `http://localhost:8020/` for the product overview
- `http://localhost:8020/standalone/` for the standalone runtime
- `http://localhost:8020/compiler/` for the compiler walkthrough
- `http://localhost:8020/integration/` for the host integration contract demo
- `http://localhost:8020/migration/` for the migration checklist
- `http://localhost:8030/` for the Django host page
- `http://localhost:8030/tui/` for the Django-mounted runtime

Standalone-only demo:

```powershell
python demo\standalone_server.py
```

Non-Django host example:

```powershell
python examples\hosts\stdlib_host.py
```

Then open `http://127.0.0.1:8040/`.

## What It Does

AgomTUI gives you a repeatable path from backend capability to usable UI:

1. Collect API or code evidence from the host system.
2. Compile that evidence into AgomTUI runtime metadata.
3. Serve metadata to the browser runtime shell.
4. Route action execution, auth, permissions, and audit back to the host.

Operators get generated screens for lists, details, filters, actions, confirmations, missing-field recovery, and raw-response debugging. Developers keep the backend as the source of truth instead of rebuilding internal-tool primitives page by page.

## Where It Fits

AgomTUI is a strong fit for:

- internal operations consoles
- admin and data-management tools
- risk-control, review, governance, and audit-heavy workflows
- host-mounted TUI surfaces inside Django or another web application
- teams that already have APIs but lack a consistent operator experience

It is not intended to replace hand-designed frontend work for consumer product pages, marketing sites, visual editors, games, or highly bespoke interactive experiences. Those can call the same APIs, but they usually need custom UI rather than metadata-generated screens.

## Demo Screens

### Overview workspace

![AgomTUI overview workspace](docs/assets/demo-overview.png)

### Standalone runtime workbench

![AgomTUI standalone runtime](docs/assets/demo-standalone.png)

### Host-mounted runtime

![AgomTUI host-mounted runtime](docs/assets/demo-host-mounted.png)

## Core Concepts

AgomTUI is built around four boundaries:

- `metadata`: the screen, view, action, field, and governance contract consumed by the runtime
- `runtime`: the browser shell that renders metadata and manages operator interactions
- `compiler`: the compile-time path from API/code evidence to reviewed metadata artifacts
- `host adapter`: the integration layer for metadata serving, action execution, auth, permissions, audit, and deployment shape

The important rule is that business logic stays in the host system. AgomTUI describes and renders the operation surface; it does not become the owner of business execution.

## Customization Model

Treat AgomTUI as a generated baseline plus extension points:

- metadata overrides for screen names, grouping, ordering, labels, and action placement
- host adapters for auth, permissions, action execution, audit storage, and routing
- renderer extensions for additional metadata-driven view types
- theme and shell customization for host embedding
- reviewed override files for manual edits that must survive regeneration

If a capability is useful across many internal tools, it belongs in the runtime or metadata contract. If it is specific to one host, it belongs in that host adapter or metadata override.

## Rich Components

AgomTUI can support richer surfaces such as ECharts, Chart.js, HTMX partials, Mermaid, Markdown renderers, date pickers, and code editors. They should be added through extension points instead of being hard-coded into generated screens.

The recommended layers are:

- native metadata renderers for common charts such as line, bar, pie, KPI trend, and table-plus-chart views
- custom renderer extensions for host-owned components, for example `renderer: "echarts"` or `renderer: "code-editor"`
- host slots for controlled server-rendered fragments, including HTMX partials when the host application already uses HTMX

For the standalone runtime, the default path should remain API data plus runtime renderers. Host slots are for cases where metadata alone is not expressive enough or where an existing host already owns part of the UI.

## Governance-First Runtime

AgomTUI treats confirmation, missing-field recovery, re-authentication, and audit as runtime protocol, not per-screen decoration. A governed action should go through one enforced path:

1. missing required fields return a `missing_fields` contract and the shell renders a refill prompt
2. confirmation-required actions stop before execution and replay only with confirmation evidence
3. password-challenge actions stop until the host verifies re-authentication
4. audit-required actions cannot reach the executor unless an audit sink is present
5. success, failure, blocked, and rejected attempts emit `tui-audit.v1` records

Hosts own storage, but audit records should be append-only or tamper-evident.

## Repository Map

- `packages/agomtui-core/`: schema, validator, runtime contracts, and generic server-side runtime helpers
- `packages/agomtui-runtime/`: browser shell assets, renderer reference, and embeddable asset helpers
- `packages/agomtui-compiler/`: compile-time collector / AI synthesizer / validator / publisher skeleton
- `adapters/django/`: notes for the first host adapter
- `demo/`: runnable standalone demo, compiler walkthrough, integration demo, and migration pages
- `examples/metadata/`: minimal, rich-component, and generic-operations metadata fixtures
- `examples/hosts/`: host integration examples, including a non-Django standard-library host
- `docs/`: development docs, architecture notes, migration plan, and CI guardrails

## Package Boundary

Suggested package line:

- `agomtui-core`: schema, validator, runtime contracts
- `agomtui-runtime`: browser shell and renderer
- `agomtui-compiler`: evidence collectors and publish pipeline
- `agomtui-adapters-*`: host integrations such as Django / FastAPI / OpenAPI-only

Django and Python are provided integration paths in this repository, not requirements for the runtime contract. Any host that can serve metadata, execute actions, and return the AgomTUI response contracts can mount the runtime.

## Compiler Flow

The intended generation path is:

1. collectors read code-owned evidence
2. `agomtui-compiler skill-request` emits a schema-constrained prompt payload
3. an external AI skill returns one `candidate_payload`
4. `agomtui-compiler compile-skill-result` validates, compacts, and publishes the approved artifact

Generated metadata should target host-agnostic runtime structure first. Workflow ordering, business vocabulary, and screen grouping should be included only when the collected evidence supports them.

## Published Metadata Edits

Published metadata is an artifact, not the source of truth. Re-running the compiler against the same publish path overwrites that file. Manual edits that must survive regeneration should live in a reviewed override file:

```powershell
agomtui-compile compile-static --project-root . --host-kind django --openapi-file examples\metadata\minimal.openapi.json --django-contract-file examples\metadata\minimal.django_contract_manifest.json --candidate-file examples\metadata\minimal.tui_operation_graph.json --override-file examples\metadata\minimal.override.json --output tmp\published.override.json --evidence-output tmp\evidence.override.json
```

Dry-run validation:

```powershell
agomtui-compile validate-metadata --metadata-file examples\metadata\minimal.tui_operation_graph.json
agomtui-compile compact-metadata --metadata-file examples\metadata\minimal.tui_operation_graph.json --output tmp\published.compact.json
```

Action governance fields are schema-validated: `risk`, `confirmation_required`, `requires_password`, `audit_required`, `sensitive_level`, and `executor`. Write actions and non-GET admin actions cannot disable required confirmation or audit.

## Documentation

- [Development docs](docs/README.md)
- [Architecture notes](docs/architecture/README.md)
- [Development standards](docs/development/development-standards.md)
- [Testing](docs/development/testing.md)
- [CI guardrails](docs/development/ci-guardrails.md)

