# AGENTS.md - AgomTUI Repository Rules

> This file is the repository-level agent guide for `D:\githv\AgomTUI`.
> It is authoritative for this repo. If a subdirectory adds agent notes later, those notes should link back here and stay consistent with these rules.

## Project Overview

AgomTUI is a framework repository, not a business application.

Its job is to define and ship:

- the metadata contract
- the browser runtime shell
- the compile-time pipeline
- reference host integration patterns

It does **not** own host business logic, permissions, authentication, audit storage, or product-specific workflow rules. Those stay in the host system.

## Package Boundaries

### `packages/agomtui-core/`

Owns host-agnostic contract code only:

- `tui_metadata.schema.v3.json`
- metadata validation and compaction
- runtime metadata normalization hooks
- governed action execution helpers
- runtime-facing protocols such as metadata repository, action executor, and audit sink

Do not put product workflow, host routing, ORM, or business vocabulary here.

### `packages/agomtui-runtime/`

Owns the shared browser shell only:

- reference HTML/CSS/JS assets
- generic dashboard, datagrid, detail, message, modal, and renderer behavior
- governed action protocol handling in the browser
- embeddable host helpers

Do not hard-code product screen maps, host auth logic, or one-host business copy into the runtime. Runtime UI behavior changes should be made under `packages/agomtui-runtime/reference/`.

### `packages/agomtui-compiler/`

Owns compile-time behavior only:

- evidence collectors
- AI skill request / result handling
- validation and usability checks
- publish pipeline

Do not move runtime-only presentation logic into compiler heuristics unless it is truly compile-time metadata generation behavior.

### `adapters/`, `demo/`, `examples/`, `sync/`

- `adapters/` documents host integration patterns; host execution still remains host-owned
- `demo/` is for runnable examples and walkthroughs, not framework truth
- `examples/metadata/` contains fixtures and contract examples
- `sync/` is for one-way sync workflows, not a place to redefine the public contract

## Core Contract Rules

When changing the TUI contract, keep schema, runtime, compiler, and tests aligned in the same change.

Current user-facing contract fields that must stay synchronized:

- `screen.user_experience`
- `dashboard_panels[].user_priority`
- `dashboard_panels[].presentation_semantic`
- `actions[].result_semantics`
- `actions[].fields[].presentation_semantic`

The main sync points are:

- `packages/agomtui-core/src/agomtui_core/schema/tui_metadata.schema.v3.json`
- `packages/agomtui-core/src/agomtui_core/metadata.py`
- `packages/agomtui-core/src/agomtui_core/runtime.py`
- `packages/agomtui-runtime/reference/static/js/tui-workbench.js`
- `packages/agomtui-compiler/src/agomtui_compiler/`
- related tests in each package

For user-facing workbench behavior:

- dashboards should be able to surface `p0` information first
- inspector and empty states should prefer `user_experience` copy over generic fallback prose
- `copyable_secret`, `endpoint_list`, and `multiline_prompt` must remain dedicated semantics, not collapsed back into a generic key/value table
- non-dashboard screen flows must continue to support `default_action_key`

## Governance Rules

AgomTUI treats governed actions as runtime protocol, not optional page decoration.

Preserve these protocol shapes and execution rules:

- `missing_fields`
- `confirmation_required`
- `password_challenge_required`
- canonical audit records via `tui-audit.v1`

All host action execution should keep flowing through `GovernedActionRunner` semantics:

1. apply defaults and reject missing required fields
2. require confirmation when metadata says so
3. require host-verified re-auth when metadata says so
4. require an audit sink for `audit_required` actions
5. execute the host action
6. emit canonical audit output for success, failure, blocked, or rejected outcomes

Never weaken these invariants:

- `write` actions and non-GET `admin` actions cannot disable required confirmation or audit
- `requires_password` is a metadata hint; the host must still verify the challenge
- `audit_required` actions must not reach the executor without an audit sink

## Artifact And Override Rules

Published metadata is an artifact, not the long-term source of truth.

- Do not rely on manual edits to published output files surviving regeneration
- Persistent manual adjustments should go through reviewed override files
- Compiler and runtime changes should target host-agnostic contract behavior first, not one demo's page choreography

If a change is specific to one host, prefer:

- host adapter behavior
- reviewed metadata overrides
- renderer extension registration

Do not push one-host business semantics down into `agomtui-core` or the shared runtime unless they are genuinely reusable framework behavior.

## Testing And Validation

Set local package sources before running tests from the repo root:

```powershell
$env:PYTHONPATH="$PWD\packages\agomtui-core\src;$PWD\packages\agomtui-compiler\src;$PWD\packages\agomtui-runtime\src"
```

Run the baseline checks after contract, compiler, or runtime changes:

```powershell
python -m unittest discover packages\agomtui-core\tests
python -m unittest discover packages\agomtui-compiler\tests
python -m unittest discover packages\agomtui-runtime\tests
python demo\django_host\manage.py test django_host
python -m agomtui_compiler.cli validate-metadata --metadata-file examples\metadata\minimal.tui_operation_graph.json
python -m agomtui_compiler.cli validate-metadata --metadata-file examples\metadata\rich_components.tui_operation_graph.json
python -m agomtui_compiler.cli validate-metadata --metadata-file examples\metadata\generic_operations.tui_operation_graph.json
python -m agomtui_compiler.cli check-usability --metadata-file examples\metadata\minimal.tui_operation_graph.json
python -m agomtui_compiler.cli check-usability --metadata-file examples\metadata\rich_components.tui_operation_graph.json
python -m agomtui_compiler.cli check-usability --metadata-file examples\metadata\generic_operations.tui_operation_graph.json
```

When a bug is fixed, add the smallest test that reproduces the regression before or alongside the implementation.

## Demo And Dev Flow

This repo's frontend dev flow is Python-served demos, not npm/Vite.

Common entry points:

```powershell
.\scripts\start_frontend.ps1
python demo\run_demo_stack.py
.\scripts\start_standalone.ps1
.\scripts\start_django_host.ps1
```

Do not introduce a separate frontend toolchain for routine shell edits unless there is a clear repository-wide decision to do so.

## Documentation Rules

Keep repository intent split cleanly:

- `README.md`: product overview and quick start
- `docs/development/`: standards, testing, CI guardrails
- `docs/architecture/`: boundary and architecture decisions

If you change package boundaries, public metadata fields, governance behavior, or renderer extension points, update the relevant docs in the same change.
