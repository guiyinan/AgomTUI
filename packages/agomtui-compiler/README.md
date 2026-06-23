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

Validate and publish from a JSON result produced by an AI skill:

```powershell
agomtui-compile compile-skill-result --project-root . --host-kind django --openapi-file examples\metadata\minimal.openapi.json --django-contract-file examples\metadata\minimal.django_contract_manifest.json --skill-result-file examples\metadata\minimal.skill_result.json --output tmp\published.skill.json --evidence-output tmp\evidence.skill.json
```

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
- only emit workflow steps, business narratives, or screen groupings when they are grounded in collected evidence
- the compiler will validate and compact it before publish
- runtime must only consume the published artifact, never raw skill output

In this repository, `examples/metadata/` shows the baseline generic shape for the skill contract. The richer `demo/fixtures/` examples are intentionally demo-specific and should not be treated as the default extraction target for other hosts.

## Why this package exists

The runtime TUI should never read source code directly. Source scanning belongs to compile time. This package is where that compile-time pipeline should live.
