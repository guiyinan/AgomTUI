# Product Split

## What can be a standalone product

### 1. Metadata contract
The schema-first contract is already a product boundary.

It defines:
- fields
- widgets
- risks
- panel kinds
- view-model mapping
- publish-time validation

This belongs in `agomtui-core`.

### 2. Runtime shell
The TUI shell is reusable across products if the host can provide:
- catalog payload
- screen payload
- action-runner payload

This belongs in `agomtui-runtime`.

What should move:
- HTML/CSS/JS shell
- keyboard model
- theme system
- generic datagrid / detail / message / dashboard renderers
- task grouping, confirmation, row-fill, inspector, filter, pager, and modal behaviors

What should not move:
- hand-authored business screens
- host-specific workflow sequencing
- published business metadata for one product
- screen copy that only makes sense in AgomTradePro

### 3. Publish workflow
The metadata compiler is also productizable, but only after splitting collector adapters from Agom-specific heuristics.

This should become `agomtui-compiler`.

Its target internal boundary is:
- collectors
- AI synthesizer
- validator
- publisher

## What is not standalone yet

### 1. View-model vocabulary
`TuiWorkbenchService` currently knows too much about Agom business labels.

Required refactor:
- replace hardcoded business vocabulary with pluggable dictionaries / formatters

### 2. Django runtime wiring
Current runtime still depends on:
- Django login
- DRF views
- ORM-backed published registry
- internal API execution through Django request context

Required refactor:
- move host integration behind adapters

### 3. Compiler collectors
The current generator scans Agom code and uses Agom-specific label rewrites.

Required refactor:
- separate generic collectors from product vocabulary rules

## Standalone package recommendation

### Core
- schema
- validator
- compactor
- contracts

### Runtime
- shell HTML/CSS/JS
- theme token system
- keyboard model
- generic DataGrid / detail / message renderers
- generic action execution UX: row-fill, confirmation, inspector, filter, pager, raw drawer

### Adapters
- django metadata repository
- django action executor
- fastapi action executor
- openapi collector

### Optional product features
- publish audit registry
- metadata diff UI
- review / approval workflow
- hosted metadata registry

## Naming

`AgomTUI` works.

It is short, product-like, and still preserves the origin story without forcing the product to stay tied to the full AgomTradePro application.
