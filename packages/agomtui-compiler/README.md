# agomtui-compiler

`agomtui-compiler` is the compile-time package that should eventually turn code-owned evidence into reviewed AgomTUI metadata.

## Target workflow

1. Collect evidence from host-owned contracts
2. Hand evidence to an LLM synthesizer constrained by schema
3. Validate and compact the candidate graph
4. Publish candidate and evidence artifacts

## Current scope

This package is a product skeleton with explicit boundaries:

- collectors
- AI synthesizer interface
- validation step
- publisher step
- top-level workflow orchestration

It does **not** yet ship a production Django introspector or a live hosted LLM backend.

## Supported compile-time evidence inputs

The current skeleton already supports three evidence entry points:

- `--openapi-file`: OpenAPI JSON spec owned by the host app
- `--django-contract-file`: Django-exported model / aggregate contract manifest
- `--evidence-file`: already-normalized evidence JSON for fallback and tests

The intended direction is to prefer the first two and keep `--evidence-file` as a bridge.

## Skeleton commands

Render the prompt envelope that should be sent to an AI skill or model:

```powershell
agomtui-compile prompt-preview --project-root . --host-kind django --openapi-file examples\metadata\minimal.openapi.json --django-contract-file examples\metadata\minimal.django_contract_manifest.json
```

Emit a structured skill request payload. This is the contract between the compiler and an external AI skill runner:

```powershell
agomtui-compile skill-request --project-root . --host-kind django --openapi-file examples\metadata\minimal.openapi.json --django-contract-file examples\metadata\minimal.django_contract_manifest.json
```

The intended output of that skill is framework-level metadata that the runtime can consume across hosts. It should not default to cloning one product's page map, workflow tour, or business vocabulary unless the supplied evidence explicitly supports that structure.

Validate and publish from a curated candidate file while the LLM backend is still pending:

```powershell
agomtui-compile compile-static --project-root . --host-kind django --openapi-file examples\metadata\minimal.openapi.json --django-contract-file examples\metadata\minimal.django_contract_manifest.json --candidate-file examples\metadata\minimal.tui_operation_graph.json --output tmp\published.json --evidence-output tmp\evidence.json
```

Validate a metadata file without publishing:

```powershell
agomtui-compile validate-metadata --metadata-file examples\metadata\minimal.tui_operation_graph.json
```

Run automated usability checks against a metadata file:

```powershell
agomtui-compile check-usability --metadata-file examples\metadata\minimal.tui_operation_graph.json
```

The usability checker validates the metadata contract first, then reports operator-facing gaps in screen navigation, dashboard panel wiring, action view models, and fields. `error` exits non-zero; `warning` is reported but does not fail unless `--fail-on-warning` is passed.

For user-facing workbench releases, the metadata should also carry explicit UX intent instead of relying on prose-only review notes:

- `screen.user_experience`: `journey`, `primary_task`, `primary_outcome`, `empty_state_hint`, `next_step_hint`
- `dashboard_panels[].user_priority`: `p0/p1/p2`
- `dashboard_panels[].presentation_semantic`: specialized rendering intent such as `copyable_secret`, `endpoint_list`, `multiline_prompt`
- `actions[].result_semantics`: result-level artifact semantics for token / endpoint / prompt outputs
- `actions[].fields[].presentation_semantic`: input intent such as `api_token`, `endpoint_url`, `prompt_text`

Hosts may validate these fields downstream, but compiler-generated metadata should already emit them when evidence supports a user-facing screen.

Validate and compact a metadata file without running collectors:

```powershell
agomtui-compile compact-metadata --metadata-file examples\metadata\minimal.tui_operation_graph.json --output tmp\published.compact.json
```

Validate and publish from a JSON result produced by an AI skill:

```powershell
agomtui-compile compile-skill-result --project-root . --host-kind django --openapi-file examples\metadata\minimal.openapi.json --django-contract-file examples\metadata\minimal.django_contract_manifest.json --skill-result-file examples\metadata\minimal.skill_result.json --output tmp\published.skill.json --evidence-output tmp\evidence.skill.json
```

## Manual overrides

Published metadata is an output artifact. If the same `--output` path is used again, the publisher overwrites it. Terminal manual edits should therefore live in a reviewed override file and be applied on every compile:

```powershell
agomtui-compile compile-static --project-root . --host-kind django --openapi-file examples\metadata\minimal.openapi.json --django-contract-file examples\metadata\minimal.django_contract_manifest.json --candidate-file examples\metadata\minimal.tui_operation_graph.json --override-file examples\metadata\minimal.override.json --output tmp\published.override.json --evidence-output tmp\evidence.override.json
```

Override files are applied after synthesis and before validation / compaction. The evidence artifact records whether overrides were applied and how many action / field patches were used.

Supported override shape:

```json
{
  "schema_version": "tui-metadata-override.v1",
  "registry_key": "default",
  "action_patches": {
    "overview.status": {
      "label": "Sync Latest Quotes",
      "method": "POST",
      "endpoint": "/api/tui-example/quotes/sync/",
      "intent": "sync_latest_quotes",
      "risk": "write",
      "task_tier": "operation",
      "task_group": "00 Governed Actions",
      "executor": "sync_latest_quotes"
    }
  },
  "field_patches": {
    "overview.status": [
      {
        "key": "symbols",
        "label": "Asset Codes",
        "input_type": "text",
        "value_type": "string",
        "required": true,
        "binding": "body",
        "placeholder": "AAPL,MSFT"
      }
    ]
  },
  "remove_fields": {
    "overview.status": ["old_field"]
  }
}
```

Use `action_patches` for titles, grouping, `method`, `risk`, `executor`, and governance fields. Use `field_patches` to add or update fields by key. Use `remove_fields` to delete generated fields by key.

Governance fields validated by `tui-metadata.v3`:

- `risk`: `read`, `ai`, `write`, `unsafe`, or `admin`
- `confirmation_required`: boolean; write actions and non-GET admin actions must keep this true
- `requires_password`: boolean metadata hint; host adapters still enforce real password checks
- `audit_required`: boolean; write / admin non-GET actions must keep this true
- `sensitive_level`: `none`, `low`, `medium`, `high`, or `critical`
- `executor`: optional host executor label; dispatch is still host-owned

## Django contract manifest shape

The Django adapter should export machine-readable contracts from code, not product prose. The current collector expects JSON in this shape:

```json
{
  "models": [
    {
      "app_label": "terminal",
      "model": "SystemStatus",
      "db_table": "terminal_system_status",
      "fields": [
        {"name": "component", "type": "CharField", "null": false, "blank": false}
      ]
    }
  ],
  "aggregates": [
    {
      "key": "status-board",
      "entity": "SystemStatusAggregate",
      "fields": [{"name": "status", "value_type": "string", "required": true}],
      "commands": [{"key": "refresh-status", "method": "POST", "endpoint": "/api/..."}]
    }
  ]
}
```

This keeps metadata generation anchored to Django models and DDD contracts while still letting the compiler stay framework-light.

## Skill result contract

The skill backend must return one JSON object with this shape:

```json
{
  "candidate_payload": {"schema_version": "tui-metadata.v3", "...": "metadata graph"},
  "model_name": "skill-name-or-model",
  "reasoning_note": "optional short note"
}
```

Rules:

- `candidate_payload` must be one JSON object
- the object must already match the AgomTUI schema contract
- prefer host-agnostic runtime structure over product-specific page choreography
- prefer `chart`, `image`, `kpi_trend`, or `table_chart` view models when evidence clearly describes trends, screenshots/previews, proportions, KPIs, or table-plus-chart analysis
- represent ECharts, CodeMirror, Mermaid, HTMX, or similar rich UI through `view_model.renderer` or `host_slot`; do not make those libraries mandatory runtime dependencies
- use `host_slot` only for controlled host-rendered fragments that the host adapter explicitly supports
- do not emit arbitrary HTML as metadata
- only emit workflow steps, business narratives, or screen groupings when they are grounded in collected evidence
- the compiler will validate and compact it before publish
- runtime must only consume the published artifact, never raw skill output

In this repository, `examples/metadata/minimal.*` shows the baseline generic shape for the skill contract, and `examples/metadata/rich_components.*` shows chart / table-chart / host-slot metadata. The richer `demo/fixtures/` examples are intentionally demo-specific and should not be treated as the default extraction target for other hosts.

## Why this package exists

The runtime TUI should never read source code directly. Source scanning belongs to compile time. This package is where that compile-time pipeline should live.
