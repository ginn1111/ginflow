# ADR 0001: Artifact-first execution packages

## Decision

Ginflow v2 uses one approved Execution Package before implementation dispatch. The package is a normalized Work Package whose Contract, Spec, and Plan sections are stored in one canonical **provider document** per Work Unit, hosted by exactly one provider: `local` (consolidated Markdown), `github` (Issue), or `linear` (Issue). The currently installed contract defines the only executable schema; users do not select workflow versions. Package also holds Work Units, dependency graph, workspace allocation, verification strategy, and Integration Card.

Provider-document rules (supersedes the earlier repository-local-only rule):

- One provider-neutral document reference (provider, stable ID, path or URL) and one `document_baseline` for every provider. Local baseline: Git commit plus normalized content hash. Remote baseline: provider, stable ID, canonical URL, content hash, and fetch time, freshly re-fetched by the adapter (max age 5 minutes) before review and completion. `ginflow-gate` validates supplied evidence without provider credentials. Inaccessible, deleted, stale, or drifted records fail closed.
- Hermes Kanban stays lifecycle authority; cards stay concise and link to the provider document. Setup resolves the provider (explicit directives only, never tool availability); no silent fallback.
- GitHub/Linear tracker Issue workflow status syncs only through explicit mappings: workers own start, block, resume, review-request; reviewers own request-changes and completion. Provider update precedes the Hermes transition, then re-fetch; failure or missing mapping fails closed. Provider document content is not rewritten and no other provider fields sync.
- Newest schema only: installed contract is authoritative.
Shaping owns brainstorming, feedback, read-only investigation, artifact drafting, splitting, and one final approval. Cards are created blocked, then share one committed package baseline. A deterministic validator must pass before root cards unblock. Integration combines Work Units but does not complete its Initiative; successful Integration opens the read-only human Decision phase, and `approved_for_mr` completes Ginflow lifecycle.

Initiative, Execution Batch, Review Cycle, Decision Projection, Notification, and MR Intent are additive provider-neutral contracts. Hermes remains lifecycle authority; target repositories remain product and canonical-verification authority.

TUI, direct Hermes database access, gateway transport/subscription setup, and provider-specific merge-request publication remain deferred.


## Context

Size-based routing permits incomplete scope and subjective execution decisions. Mid-task clarification interrupts workers and weakens auditability. Artifact-first preparation moves decisions before dispatch while retaining Hermes Kanban as lifecycle authority and project-native verification as behavior evidence.

## Trade-offs

- More up-front shaping and artifact maintenance.
- Provider-hosted canonical documents require reliable retrieval; mitigated by stable identity, fresh-fetch evidence (≤ 5 minutes), and fail-closed gates.
- Stable human keys improve links, but require key validation before Hermes task IDs exist.
- One package baseline improves reproducibility, but package revisions require reapproval and revalidation.

## Rejected alternative

Keep XS/S/M/L/XL routing and select Spec/Plan conditionally. This keeps startup small, but preserves subjective routing and lets incomplete work reach workers.
