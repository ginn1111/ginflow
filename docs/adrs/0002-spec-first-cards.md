---
status: accepted
supersedes: 0001
scope: ginflow workflow model
owner: ginb
---

# ADR 0002: Spec-first cards

## Decision

Each card is backed by one spec (`docs/specs/<KEY>.md`) and one plan (`docs/plans/<KEY>.md`) in the target repo. Front matter carries `card`, `assignee`, `blocked_by`. Cards are created blocked, linked by Hermes `link` edges, executed on stacked branches, reviewed, and published as a PR by `ginflow-gate`. PR feedback becomes new cards. `artifact_baseline` (commit + linked paths) is the completion evidence.

Flow: shape → cards → execute → review → PR → feedback.

## Removed

Unwired, never reached from a hook or command:

- Initiative chain: `initiative`, `execution_package`, `execution_batch`, `card_creation`, `decision`, `review_cycle`, `merge_request`, `followup` (library modules and tests).
- Provider documents: `provider_document`, the gate `document_baseline` check, `docs/work-units/` documents.
- Documents config in `project_config`: `DOC_PROVIDERS`, `STATUS_KEYS`, `DocumentConfigError`, `configured_documents`, `documents_block_error`, `documents_error`, `resolve_documents`, `require_ready`, `set_documents`.
- Routing text for the four-phase Initiative lifecycle (Discovery, Shaping, Execution, Decision).

`card_creation` is rewritten against spec front matter in a later card.

## Trade-offs

- Less ceremony; no Initiative aggregate or Decision phase, so no durable cross-card review record beyond PRs and cards.
- No remote provider-hosted governance document; specs and plans live in git.
- Card creation is manual until the rewrite lands.
