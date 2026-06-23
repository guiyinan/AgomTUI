# Upstream Extraction Memo

This memo keeps the upstream origin notes out of the public-facing README while preserving the working rules for extraction and sync.

## Scope

The current runtime reference and some extraction conventions originated from an upstream host project. That origin should not define the standalone product boundary.

The extraction target remains:

1. schema-first metadata core
2. compile-time metadata generator / promotion pipeline
3. runtime TUI shell and host adapters

Not the full upstream product surface.

## Skill boundary

The extracted skill should target host-agnostic runtime metadata first. It should not assume the upstream product's page splits, workflow ordering, or business prose unless those structures are explicitly present in the evidence bundle.

## Runtime shell sync notes

The current runtime-shell sync tooling is still organized around a one-way upstream-to-reference flow.

Key files:

- `sync/agomtradepro/runtime-shell.manifest.json`: allowlist of source-to-target mappings
- `sync/agomtradepro/runtime-shell.config.example.json`: local config template for machine-specific paths
- `scripts/sync_from_agomtradepro.py`: sync executor with transform hooks and target guardrails
- `sync/agomtradepro/README.md`: sync boundary and review rules

Machine-specific source paths should live in `sync/agomtradepro/runtime-shell.config.json`, not in the committed manifest.

Dry run:

```powershell
python scripts\sync_from_agomtradepro.py --check
```

Apply:

```powershell
python scripts\sync_from_agomtradepro.py --apply
```

Compare current source material to a git baseline:

```powershell
python scripts\sync_from_agomtradepro.py --compare-baseline --baseline-ref HEAD
```

This sync only updates `packages/agomtui-runtime/reference/`. It does not touch schema, compiler, adapters, demo pages, or migration docs.

## Why this memo exists

The public README should explain the standalone product clearly. Upstream origin, legacy naming, and extraction mechanics belong here instead of the front page.
