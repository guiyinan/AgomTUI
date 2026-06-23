# Compiler Architecture

## Goal

Turn host-owned code evidence into reviewed TUI metadata without letting the runtime parse source code directly.

## Four layers

### 1. Collectors
Collectors read host-owned evidence:

- OpenAPI contracts
- Django/ORM model fields
- aggregate roots
- typed SDK signatures
- MCP typed tools
- legacy template affordances

Output must be normalized `EvidenceItem` records.

The current skeleton now includes:

- `OpenApiSpecCollector`
- `DjangoContractManifestCollector`
- `JsonEvidenceCollector` for fallback

### 2. AI synthesizer
This is the product-critical boundary.

The synthesizer should:
- receive schema text plus normalized evidence
- emit one metadata candidate
- stay constrained by the schema
- never invent new structural shapes

The current skeleton exposes this through `LlmMetadataSynthesizer`.

### 3. Validation
Every candidate must pass:

- schema validation
- domain validation
- optional smoke execution
- manual review when required

This is intentionally deterministic and must remain outside the LLM.

### 4. Publisher
Publishing writes:

- compact candidate graph
- source evidence artifact
- release trace metadata

In a full product this can target files, a DB registry, or a hosted metadata service.

## Why this matters

If the compiler keeps generation, validation, and publishing inside one ad hoc script, the product stays tied to one host app. These boundaries make the compiler portable.
