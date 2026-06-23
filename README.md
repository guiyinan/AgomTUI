# AgomTUI

AgomTUI is the extracted standalone product direction for the metadata-driven terminal workbench currently living inside AgomTradePro.

## Short answer

Yes, this can become an independent product.

But the correct product boundary is:

1. **Schema-first metadata core**
2. **Compile-time metadata generator / promotion pipeline**
3. **Runtime TUI shell and host adapters**

It is **not** just a Django template split.

## Repository contents

- `packages/agomtui-core/`: framework-free metadata schema and validator
- `packages/agomtui-runtime/`: extracted reference runtime shell assets
- `packages/agomtui-compiler/`: compile-time collector / AI synthesizer / validator / publisher skeleton
- `demo/`: runnable standalone product demo, compiler walkthrough, and integration contract pages
- `adapters/django/`: notes for the first host adapter
- `examples/metadata/`: minimal payload examples
- `docs/`: extraction boundary and migration plan

## Run the demo

### Standalone demo surface

Start the standalone product demo from the repository root:

```powershell
python demo\standalone_server.py
```

Then open:

- `http://localhost:8020/`: product overview
- `http://localhost:8020/standalone/`: standalone TUI runtime demo
- `http://localhost:8020/standalone/?mode=integration`: simulated host-mounted runtime using `/integration-api/tui/*`
- `http://localhost:8020/compiler/`: compiler walkthrough driven by OpenAPI and Django contracts
- `http://localhost:8020/integration/`: integration contract demo
- `http://localhost:8020/migration/`: migration checklist

### Real Django host demo

To prove the same runtime and metadata contract can mount back into a Django host, start the demo host in a second terminal:

```powershell
python demo\django_host\manage.py runserver 127.0.0.1:8030 --noreload
```

Then open:

- `http://localhost:8030/`: real Django host page
- `http://localhost:8030/tui/`: Django-mounted runtime
- `http://localhost:8030/contracts/openapi.json`: host-owned OpenAPI export
- `http://localhost:8030/contracts/django-contract-manifest.json`: host-owned Django contract export
- `http://localhost:8030/contracts/published-metadata.json`: published metadata artifact

### Combined runner

If you want both surfaces from one command, use:

```powershell
python demo\run_demo_stack.py
```

This starts the standalone demo on `8020` and the real Django host on `8030`.

## Run tests

### Compiler tests

The compiler package is not installed as a site package in this repo layout, so set `PYTHONPATH` first:

```powershell
$env:PYTHONPATH='D:\githv\AgomTUI\packages\agomtui-core\src;D:\githv\AgomTUI\packages\agomtui-compiler\src'
python -m unittest discover packages\agomtui-compiler\tests
```

### Django host tests

```powershell
python demo\django_host\manage.py test django_host
```

## Sync runtime shell from AgomTradePro

The intended long-term flow is one-way sync from `agomTradePro` into the extracted runtime reference only.

Directory convention:

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

When no local `agomTradePro` checkout is available, the script can fall back to a git ref or a remote fetch cache.

This sync only updates `packages/agomtui-runtime/reference/`. It does not touch schema, compiler, adapters, demo pages, or migration docs.

## Product boundary

### Reusable now

- metadata schema (`tui-metadata.v3`)
- metadata validation and compaction
- runtime shell layout, keyboard model, theme tokens
- compiler orchestration boundaries for AI-driven metadata synthesis
- generic repository / action-executor contracts

### Still coupled to AgomTradePro

- Django auth and login flow
- DB publish registry model and audit fields
- internal API execution adapter
- Agom-specific business vocabulary and view-model translation
- compile-time route and OpenAPI harvesting heuristics

## Suggested product architecture

- `agomtui-core`: schema, validator, contracts
- `agomtui-runtime`: browser shell and renderer
- `agomtui-compiler`: evidence collectors and publish pipeline
- `agomtui-adapters-*`: host integrations such as Django / FastAPI / OpenAPI-only

## AI skill path

The intended generation path is now explicit:

1. collectors read code-owned evidence
2. `agomtui-compiler skill-request` emits a schema-constrained prompt payload
3. an external AI skill returns one `candidate_payload`
4. `agomtui-compiler compile-skill-result` validates, compacts, and publishes the approved artifact

The compiler now has direct inputs for:

- OpenAPI JSON
- Django-exported model contracts
- Django-exported aggregate contracts

This is the right shape for your requirement: AI reads code-derived evidence, not PM retellings, and runtime stays dumb.

## Starting point

Open `packages/agomtui-runtime/reference/tui_workbench.reference.html` as the current extracted shell reference, and read `docs/product-split.md` before pulling more code across.

For the next product step, read `docs/compiler-architecture.md` and inspect `packages/agomtui-compiler/`.
