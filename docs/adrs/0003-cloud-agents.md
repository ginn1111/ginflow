---
status: accepted
scope: cloud-agents runtime topology and GitHub ingress
owner: cindy
---

# ADR 0003: Cloud agents — one container, GitHub App, derived Repositories

## Decision

Ginflow runs in one long-lived container serving every Repository: one Hermes home, one board per Repository, all paths derived from `owner/repo` with no registry. GitHub events arrive through a GitHub App webhook. A Repository is onboarded on its first event; granting the App access to a repo is the approval. Only events from allowlisted, non-bot senders advance work. Shaping an Issue yields one spec/plan pair per card (ADR 0002 unchanged); the Issue has no artifact of its own.

## Considered options

- Container per repo: simpler isolation, but N gateways and webhook URLs.
- Container per job: strongest isolation, needs a control plane outside Hermes.
- Explicit `repo add` registration: safest, but a manual step per repo.
- Personal PAT or per-repo webhooks: long-lived secret, bot indistinguishable from Gin.

## Consequences

- `.ginflow.yaml` becomes per-clone local state, not a committed file.
- The webhook filter must stay fast (GitHub 10 s timeout); onboarding runs inside the agent run.
- Bot identity, not comment prefixes, is the loop filter.
