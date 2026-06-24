# agomtui-core

Framework-free core for AgomTUI metadata validation, runtime contracts, and host-side execution helpers.

## Included

- `validate_tui_metadata()`
- `compact_tui_metadata_payload()`
- `apply_tui_metadata_overrides()`
- generic server-side runtime helpers for:
  - view-model inference
  - confirmation / missing-fields contracts
  - password-challenge detection
  - governed action execution
  - canonical audit record generation
  - runtime metadata normalization hooks
- `tui_metadata.schema.v3.json`
- runtime-facing protocols for metadata repositories, action executors, and audit sinks

## Metadata governance fields

`tui-metadata.v3` now validates these action-level governance fields:

- `risk`: `read`, `ai`, `write`, `unsafe`, or `admin`
- `confirmation_required`: boolean; defaults to true for `write` actions and non-GET `admin` actions
- `requires_password`: boolean metadata hint; host adapters still enforce the real challenge
- `audit_required`: boolean; defaults to true for non-GET `write` / `admin` actions
- `sensitive_level`: `none`, `low`, `medium`, `high`, or `critical`
- `executor`: optional host executor label

The validator rejects governed actions that explicitly disable required confirmation or audit. The compactor removes default governance values so storage output stays small while runtime validation restores the normalized shape.

## No-bypass execution

`GovernedActionRunner` is the core no-bypass wrapper for host action execution. Host adapters should route every runtime action through it instead of calling their executor directly.

The enforced order is:

1. apply field defaults and reject missing required fields
2. require confirmation when metadata says so
3. require host-verified re-authentication when metadata says so
4. require an audit sink before any `audit_required` action can reach the executor
5. execute the host action
6. append a canonical audit record for success, failure, blocked confirmation, missing fields, or failed re-auth

An `audit_required` action without an `AuditSink` raises before executor dispatch. A `requires_password` action without a host `reauth_verifier` cannot reach the executor.

## Audit contract

Core emits append-only audit records with schema version `tui-audit.v1`. Records include:

- actor
- action key / label
- risk and sensitive level
- masked input params
- confirmation evidence
- re-auth evidence
- outcome
- response status, missing fields, and error text
- timestamp

Host adapters own storage, but the storage layer should be append-only or tamper-evident. At minimum, do not update or delete existing audit rows in normal application code; corrections should be new records linked to the original record.

## Manual override hook

`apply_tui_metadata_overrides()` applies reviewed terminal edits before validation and compaction. It supports:

- `action_patches`: deep-merge action properties by action key
- `field_patches`: add or update fields by action key and field key
- `remove_fields`: delete generated fields by action key and field key

This keeps published artifacts reproducible: rerun the compiler with the same override file instead of editing the published artifact directly.

## Not included yet

- Django models and DB repositories
- host auth or permission checks
- Agom-specific view-model vocabulary packs
- compile-time code/OpenAPI/Django scanners
