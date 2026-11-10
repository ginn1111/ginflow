---
status: draft
scope: docs/architecture/integration-status.md, docs/architecture/README.md; Makefile
owner: ginb
---

# Plan — CLEANUP-1.9: Integration-status report

Source: umbrella plan for GitHub #1. Line numbers are approximate; locate code by symbol. Earlier tickets are merged into `main` before this card starts and may have changed nearby code — re-read before editing. Ignore any umbrella-plan step about creating cards or closing the umbrella card. RED test first, then change, then `make lint test`.

## Step 1: Run orphan test + integration report

1. `python3 plugins/ginflow-gate/test_feedback.py; echo exit=$?` → if 0, add `\tpython3 plugins/ginflow-gate/test_feedback.py` to `Makefile` `plugin-test` after `test_recovery_policy.py` (only test file not in `make test`). If non-zero, record as open item in the report instead.
2. Create `docs/architecture/integration-status.md` with exactly this content (adjust rows removed in Task 11):

```markdown
---
status: completed
scope: plugins/ginflow-gate, plugins/ginflow-trace, skills/ginflow/lib
owner: cindy
---

# Integration status — plugins and core

Wired = reached from a Hermes hook (`pre_llm_call`, `pre_tool_call`, `post_tool_call`, `kanban_task_blocked`) or the harness CLI (`validate-harness.py`). Doc = named in `skills/ginflow/SKILL.md` or its references. Tested = covered by `make test`.

Regenerate evidence: `grep -rnw <name> plugins skills/ginflow/scripts --include=*.py | grep -v test_`.

## ginflow-gate plugin

| Module | Function | Wired | Doc | Tested |
| --- | --- | --- | --- | --- |
| routing.py | `_routing_context` | [x] pre_llm_call | [x] | [x] |
| block_routing.py | `guard_block` | [x] pre_tool_call | [x] trace-routing.md | [x] |
| block_routing.py | `on_task_blocked` | [x] kanban_task_blocked | [x] trace-routing.md | [x] (needs hermes CLI) |
| gate.py | `pre_tool_call`, `validate_completion` | [x] pre_tool_call | [x] completion.md | [x] |
| gate.py | `post_tool_call` | [x] post_tool_call | [x] decision.md | [x] |
| publish.py | `prepare`, `finish`, `auth_error` | [x] via gate/routing | [x] decision.md, project-context.md | [x] |
| skill_lib.py | `load` | [x] import time | [ ] | [x] test-install.sh |
| trace_adapter.py | `trace` | [x] decorator | [ ] | [x] |
| blocker_reporting.py | `build_blocker_event`, `blocker_comment` | [ ] | [ ] | [x] |
| recovery_policy.py | `evaluate_recovery` | [ ] | [ ] | [x] |
| feedback.py | `build_feedback_event` | [ ] | [ ] | [x] |

## ginflow-trace plugin

| Module | Function | Wired | Doc | Tested |
| --- | --- | --- | --- | --- |
| decorator.py | `trace` | [x] via gate trace_adapter | [x] project-context.md | [x] |
| storage.py / identity.py / sanitize.py | internals | [x] via `trace` | [ ] | [x] |

## skills/ginflow/lib (core)

| Module | Function | Wired | Doc | Tested |
| --- | --- | --- | --- | --- |
| harness_core.py | `parse_card_body`, `normalize_card`, `kanban_run`, `kanban_json`, `load_kanban_card`, `startup_gate`, `artifact_gate` | [x] | [x] SKILL.md | [x] |
| harness_core.py | `check`, `has`, `linked_artifacts` | [x] harness CLI | [x] completion.md | [x] |
| routing.py | `route`, `workspace` | [x] | [x] | [x] |
| publish.py | `build_*_argv`, `parse_*_url` | [x] | [x] | [x] |
| project_config.py | `config_path`, `config_exists`, `load_config`, `context_error`, `resolve_board`, `configured_reviewer`, `reviewer_error`, `installed_profiles`, `configured_publish`, `publish_error`, `configured_notify_target` | [x] | [x] project-context.md | [x] |
| project_config.py | `initialize_context`, `persist_context` | [ ] agent-procedural | [x] project-context.md | [~] persist_context only |
| project_config.py | `configured_worker`, `worker_error`, `resolve_worker_dispatch`, `persist_worker_defaults` | [ ] | [x] project-context.md | [~] worker_error only |
| project_config.py | `documents_error`, `resolve_documents`, `require_ready`, `set_documents` | [ ] | [ ] | [x] |
| project_config.py | `hermes_default_reviewer`, `seed_default_reviewer` | [ ] | [ ] | [ ] |
| provider_document.py | `content_hash` | [x] gate | [ ] | [x] |
| provider_document.py | `build_provider_document`, `write_local_document` | [ ] | [ ] | [x] |
| initiative.py | `validate_initiative`, `approve_discovery`, `transition` | [ ] | [ ] | [x] |
| execution_package.py | `shape_package`, `approve_package`, `validate_package` | [ ] | [ ] | [x] |
| card_creation.py | `create_execution_cards` | [ ] | [ ] | [x] |
| execution_batch.py | `authorize_batch`, `create_batch`, `canonical_digest` | [ ] | [x] SKILL.md, decision.md | [x] |
| decision.py | `decision_ready`, `decision_blocked`, `build_projection`, `build_notification` | [ ] | [x] decision.md | [x] |
| review_cycle.py | `validate_review`, `append_revision` | [ ] | [x] decision.md | [x] |
| review_cycle.py | `append_review_revision` | [ ] | [x] decision.md | [ ] |
| merge_request.py | `build_mr_intent` | [ ] | [x] decision.md | [x] |
| followup.py | `route_followup` | [ ] | [ ] | [x] |

## Summary

- Wired: routing, block routing, completion gate, publish, trace, core harness/config/routing/publish primitives.
- Not wired (library + tests only): Initiative lifecycle chain (initiative → execution_package → execution_batch/card_creation → decision/review_cycle → merge_request/followup), provider document builder, blocker/recovery/feedback helpers, worker defaults, documents config, reviewer seeding.
- Untested and unwired: `hermes_default_reviewer`, `seed_default_reviewer`, `append_review_revision`.
```
3. Link it from `docs/architecture/README.md` "Implementation boundaries": `- [Integration status](./integration-status.md) — which plugin/core functions are reached from Hermes hooks.`
4. `make lint test; echo exit=$?` → 0. Commit `docs(architecture): add plugin/core integration status report`.