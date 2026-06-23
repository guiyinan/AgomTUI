# agomtui-core

Framework-free core extracted from the AgomTradePro TUI workbench.

## Included

- `validate_tui_metadata()`
- `compact_tui_metadata_payload()`
- generic server-side runtime helpers for:
  - view-model inference
  - confirmation / missing-fields contracts
  - password-challenge detection
  - runtime metadata normalization hooks
- `tui_metadata.schema.v3.json`
- runtime-facing protocols for metadata repositories and action executors

## Not included yet

- Django models and DB repositories
- host auth or permission checks
- Agom-specific view-model vocabulary packs
- compile-time code/OpenAPI/Django scanners
