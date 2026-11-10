# Architecture

This directory documents the Ginflow system and its Ginflow routing model.

## Sources and derived views

- [Canonical Draw.io architecture](./ginflow-system.drawio) — source of truth, including the **Ginflow system** and **Harness system overview** pages.
- [Ginflow mental model](./ginflow-flow.md) — GitHub-readable Mermaid documentation derived from the canonical Draw.io page.

Update Draw.io first when workflow behavior changes, then update the Mermaid explanation. Mermaid is derived documentation, not a second authority.

## Implementation boundaries

- [Ginflow skill and distributed harness core](../../skills/ginflow/) — shared workflow, routing, validation, artifacts, and verification guidance.
- [Ginflow routing core](../../core/ginflow-core/routing.py) — framework-agnostic routing primitives.
- [`ginflow-gate` plugin](../../plugins/ginflow-gate/) — routing-context injection and the blocking Kanban completion gate.
- [Provider-document architecture](../specs/GINFLOW-V2.md#provider-documents) — canonical provider document, `document_baseline`, status sync, and newest-schema-only rules; ADR: [0001](../adrs/0001-artifact-first-execution-packages.md).
- [Ginflow v2 spec](../specs/GINFLOW-V2.md) — artifact-first Execution Package, Work Contract, and documentation rules.
