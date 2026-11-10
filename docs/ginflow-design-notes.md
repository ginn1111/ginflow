# Ginflow design notes (maintainers)

Not agent instructions. Moved out of `skills/ginflow/SKILL.md`.

- No public `kanban_claim` tool exists for plugin interception. Atomic workspace-collision enforcement needs Hermes core; dispatcher claim stays the mechanical authority.
- Deferred: TUI, direct Hermes DB access, gateway transport/subscriptions, provider-specific publication. Notification transport is adapter-owned.
- Legacy `feature_list.json`, `progress.md`, `init.sh`, mandatory handoff files are not equivalents of Ginflow state.
- Plugin candidate-skill mapping is deterministic advisory guidance. The plugin never calls `skill_view`, inspects skill contents, creates cards/artifacts, or mutates Kanban.
- Kanban task creation from a persistent TUI/gateway session auto-subscribes when `kanban.auto_subscribe_on_create` is on; `subscribed: true` confirms. Dispatcher delivers terminal events. No `/background` watcher.
