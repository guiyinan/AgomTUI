# Django Adapter Notes

The first practical host adapter for AgomTUI should provide:

- published metadata repository
- action executor that can call internal endpoints with user context
- optional DB-backed publish registry and audit trail
- template view that serves the runtime shell
- compile-time contract export for Django models and DDD aggregates

## Compile-time export requirement

The adapter should export machine-readable evidence from code, not product-manager prose.

Minimum export targets:

- Django model field contracts
- aggregate root field contracts
- aggregate command contracts
- OpenAPI JSON generated from the host API layer

Recommended handoff into `agomtui-compiler`:

1. export OpenAPI JSON
2. export one Django contract manifest JSON
3. run `agomtui-compile skill-request ...`
4. let the AI skill return one candidate payload
5. run `agomtui-compile compile-skill-result ...`

The expected skill output is reusable runtime metadata, not a baked-in clone of one host's page flow. Adapter exports should stay structural so different hosts can layer their own vocabulary, navigation choices, and workflow sequencing on top.

Do not copy host-specific business vocabulary into the adapter itself. Keep that in the host application or a separate vocabulary extension.
