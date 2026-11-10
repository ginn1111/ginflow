# Ginflow glossary

- **Initiative** — stable aggregate identity linking Discovery, approved package revisions, Execution Batches, cards, Review Cycles, notifications, and merge-request intents.
- **Discovery** — read-only problem framing: desired outcome, constraints, non-goals, prototype evidence, vocabulary, and open questions.
- **Shaping handoff** — approved Discovery output that authorizes Shaping to form one Execution Package.
- **Execution Package** — artifact-first Ginflow v2 contract containing approved contract/spec, Tickets, plans, dependencies, workspaces, and baseline verification.
- **Execution Batch** — immutable AFK attempt bound to one package digest, artifact baseline, Ticket set, workspaces, budget, stop conditions, and actor authorization.
- **Work Unit** — one Ticket execution card. Parallel mutation requires isolated worktrees or workspaces.
- **Work Package** — normalized, provider-neutral content of one Work Unit (Contract, Spec, Plan, acceptance, verification, dependencies, risks); rendered into its provider document.
- **Provider document** — the single canonical governance record per Work Unit, hosted by `local` Markdown, a GitHub Issue, or a Linear Issue. Hermes Kanban cards link to it and stay lifecycle authority.
- **Document reference** — provider-neutral `{provider, stable ID, path or URL}` pointing at a provider document.
- **Document baseline** — `document_baseline` integrity evidence: normalized content hash plus Git commit (local) or provider, stable ID, URL, and fresh fetch time ≤ 5 minutes (remote).
- **Tracker status sync** — mapped GitHub/Linear Issue workflow-status update made before a Hermes transition, then re-fetched; never touches provider document content or other provider fields.
- **Integration** — dedicated card and terminal outcome that combines Work Units and verifies the result. Success opens Decision; it does not complete Initiative.
- **Change Group** — behavior-oriented review unit mapping Tickets, acceptance, and changed paths.
- **Decision** — read-only human context recovery and disposition phase after successful or blocked Integration.
- **Review Cycle** — append-only evidence, findings, dispositions, and aggregate Decision revision bound to exact commits and actors.
- **Disposition vs outcome** — a disposition (`accept`, `enhance`, `reject`, `defer`) is the human verb applied to one Change Group; the projection's `choices` offer exactly these. An outcome (`approved_for_mr`, `enhancement_requested`, `rejected`, `resume_execution`, `reshape_required`, `stopped`) is the aggregate Review Cycle result derived from them. Only `approved_for_mr` completes Ginflow lifecycle.
- **Decision Projection** — bounded, redacted `decision_projection` structured view for future TUI consumers; it is not workflow authority.
- **Notification** — gateway-ready `notification` envelope for material outcomes, with idempotency and delivery state; transport remains adapter-owned.
- **MR Intent** — provider-neutral `merge_request_intent` preview containing exact refs/commits, lineage, review digest, checks, risks, reviewers, labels, draft state, and publication status.
- **Prototype promotion** — explicit production coverage for prototype evidence through Spec, Plan, Ticket, acceptance, and verification; prototype code is non-production by default.

## Authority boundaries

Hermes remains identity, Kanban, assignment, dispatch, lifecycle, and persistence authority. Ginflow core validates pure records and derives projections. Adapters collect Git/check evidence, deliver notifications, and later publish provider-specific merge requests. Target repositories remain authority for product behavior and canonical verification. TUI, direct Hermes database access, gateway transport/subscriptions, and provider publication remain deferred.
