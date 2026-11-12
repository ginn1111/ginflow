---
status: completed
scope: plugins/ginflow-gate, plugins/ginflow-trace, skills/ginflow/lib
owner: ginb
---

# Integration status — plugins and core

Wired = reached from a Hermes hook (`pre_llm_call`, `pre_tool_call`, `post_tool_call`, `kanban_task_blocked`, `kanban_task_completed`), plugin load, or the harness CLI (`validate-harness.py`); the wired cell names the path. Doc = named in `skills/ginflow/SKILL.md` or its references. Tested = named in a test run by `make test`. Public = top-level function without a leading underscore (plus `_routing_context`, the `pre_llm_call` hook). Wired cells follow call-graph reading of hook registrations; Doc and Tested cells are word-grep matches, so generic names (`check`, `has`) can over-report.

Regenerate evidence: `grep -rnw <name> plugins skills/ginflow scripts --include=*.py | grep -v test` for callers; `grep -rnw <name> plugins skills/ginflow scripts --include='test*.py'` for tests; `grep -rnw <name> skills/ginflow --include=*.md` for docs.

## ginflow-gate plugin

| Module | Function | Wired | Doc | Tested |
| --- | --- | --- | --- | --- |
| __init__.py | `register` | [x] plugin load | [ ] | [x] |
| block_routing.py | `guard_block` | [x] pre_tool_call | [ ] | [ ] |
| block_routing.py | `build_message` | [x] kanban_task_blocked | [ ] | [x] |
| block_routing.py | `on_task_blocked` | [x] kanban_task_blocked | [ ] | [ ] |
| block_routing.py | `register` | [x] plugin load | [ ] | [x] |
| blocker_reporting.py | `build_blocker_event` | [x] kanban_task_blocked | [ ] | [x] |
| blocker_reporting.py | `blocker_comment` | [x] kanban_task_blocked | [ ] | [x] |
| feedback.py | `build_feedback_event` | [x] kanban_task_blocked | [ ] | [x] |
| gate.py | `load_card` | [x] pre_tool_call | [ ] | [x] |
| gate.py | `linked_documents_missing_completion` | [x] pre_tool_call | [ ] | [x] |
| gate.py | `validate_completion` | [x] pre_tool_call | [ ] | [x] |
| gate.py | `pre_tool_call` | [x] pre_tool_call | [ ] | [x] |
| gate.py | `post_tool_call` | [x] post_tool_call | [ ] | [x] |
| gate.py | `register` | [x] plugin load | [ ] | [x] |
| publish.py | `active_profile` | [x] pre_tool_call | [ ] | [ ] |
| publish.py | `auth_error` | [x] pre_llm_call | [ ] | [ ] |
| publish.py | `prepare` | [x] pre_tool_call | [ ] | [ ] |
| publish.py | `base_and_body` | [x] pre_tool_call | [x] | [x] |
| publish.py | `publish` | [x] post_tool_call | [x] | [x] | 
| publish.py | `finish` | [x] post_tool_call | [x] | [ ] |
| recovery_policy.py | `evaluate_recovery` | [x] kanban_task_blocked | [ ] | [x] |
| routing.py | `register` | [x] plugin load | [ ] | [x] |
| routing.py | `_routing_context` | [x] pre_llm_call | [ ] | [x] |
| stacking.py | `on_task_completed` | [x] kanban_task_completed | [x] | [x] |
| stacking.py | `stack_child` | [x] kanban_task_completed | [x] | [x] |
| stacking.py | `register` | [x] plugin load | [ ] | [x] |
| skill_lib.py | `load` | [x] import time | [x] | [x] |
| trace_adapter.py | _(no public function)_ | - | - | - |

## ginflow-trace plugin

| Module | Function | Wired | Doc | Tested |
| --- | --- | --- | --- | --- |
| __init__.py | _(no public function)_ | - | - | - |
| decorator.py | `trace` | [x] via gate trace_adapter | [x] | [x] |
| identity.py | `resolve_identity` | [x] via trace | [ ] | [x] |
| sanitize.py | `sanitize` | [x] via trace | [ ] | [x] |
| storage.py | `append_record` | [x] via trace | [ ] | [x] |

## skills/ginflow/lib (core)

| Module | Function | Wired | Doc | Tested |
| --- | --- | --- | --- | --- |
| harness_core.py | `check` | [x] harness CLI / gate / routing | [x] | [x] |
| harness_core.py | `has` | [x] harness CLI / gate / routing | [x] | [x] |
| harness_core.py | `parse_card_body` | [x] harness CLI / gate / routing | [ ] | [x] |
| harness_core.py | `normalize_card` | [x] harness CLI / gate / routing | [ ] | [x] |
| harness_core.py | `kanban_argv` | [x] harness CLI / gate / routing | [ ] | [ ] |
| harness_core.py | `kanban_run` | [x] harness CLI / gate / routing | [ ] | [ ] |
| harness_core.py | `kanban_json` | [x] harness CLI / gate / routing | [ ] | [ ] |
| harness_core.py | `load_kanban_card` | [x] harness CLI / gate / routing | [ ] | [ ] |
| harness_core.py | `linked_artifacts` | [x] harness CLI / gate / routing | [ ] | [ ] |
| harness_core.py | `startup_gate` | [x] harness CLI / gate / routing | [ ] | [x] |
| harness_core.py | `artifact_gate` | [x] harness CLI / gate / routing | [ ] | [x] |
| project_config.py | `config_path` | [x] harness CLI / gate / routing | [ ] | [x] |
| project_config.py | `config_exists` | [x] harness CLI / gate / routing | [ ] | [x] |
| project_config.py | `load_config` | [x] harness CLI / gate / routing | [ ] | [x] |
| project_config.py | `context_error` | [x] harness CLI / gate / routing | [ ] | [x] |
| project_config.py | `notify_error` | [x] harness CLI / gate / routing | [ ] | [ ] |
| project_config.py | `configured_notify_target` | [x] harness CLI / gate / routing | [ ] | [ ] |
| project_config.py | `configured_context` | [x] harness CLI / gate / routing | [ ] | [ ] |
| project_config.py | `worker_error` | [x] ginflow init | [ ] | [x] |
| project_config.py | `configured_worker` | [x] ginflow init | [x] | [ ] |
| project_config.py | `resolve_worker_dispatch` | [x] ginflow init | [x] | [ ] |
| project_config.py | `configured_reviewer` | [x] harness CLI / gate / routing | [ ] | [x] |
| project_config.py | `publish_error` | [x] harness CLI / gate / routing | [ ] | [ ] |
| project_config.py | `configured_publish` | [x] harness CLI / gate / routing | [ ] | [ ] |
| project_config.py | `reviewer_error` | [x] harness CLI / gate / routing | [ ] | [x] |
| project_config.py | `installed_profiles` | [x] harness CLI / gate / routing | [ ] | [ ] |
| project_config.py | `hermes_default_reviewer` | [x] ginflow init | [x] | [ ] |
| project_config.py | `seed_default_reviewer` | [x] ginflow init | [x] | [ ] |
| project_config.py | `active_board` | [x] harness CLI / gate / routing | [ ] | [ ] |
| project_config.py | `resolve_board` | [x] harness CLI / gate / routing | [ ] | [x] |
| project_config.py | `persist_context` | [x] ginflow init | [ ] | [x] |
| project_config.py | `persist_worker_defaults` | [x] ginflow init | [x] | [ ] |
| project_config.py | `persist_reviewer` | [x] ginflow init | [x] | [ ] |
| project_config.py | `initialize_context` | [x] ginflow init | [x] | [ ] |
| publish.py | `build_push_argv` | [x] gate publish | [ ] | [x] |
| publish.py | `build_create_argv` | [x] gate publish | [ ] | [x] |
| publish.py | `build_existing_argv` | [x] gate publish | [ ] | [x] |
| publish.py | `build_auth_argv` | [x] gate publish | [ ] | [x] |
| publish.py | `parse_existing_url` | [x] gate publish | [ ] | [x] |
| publish.py | `parse_created_url` | [x] gate publish | [ ] | [x] |
| routing.py | `workspace` | [x] harness CLI / gate / routing | [x] | [x] |
| routing.py | `route` | [x] harness CLI / gate / routing | [x] | [x] |

## Summary

- Wired: routing context, block guard, block routing with recovery policy and feedback (`blocker_reporting`, `recovery_policy`, `feedback`), completion gate, publish, trace, core harness/routing/publish primitives, config readers (board, context, reviewer, publish, notify).
- Wired via `ginflow init` (`skills/ginflow/scripts/ginflow.py`, tested by `test-ginflow-init.py`): `initialize_context`, `persist_context`, `persist_worker_defaults`, `persist_reviewer`, `configured_worker`, `worker_error`, `resolve_worker_dispatch`, `hermes_default_reviewer`, `seed_default_reviewer`.
- Wired via `ginflow pr sync` (`skills/ginflow/scripts/ginflow.py`, tested by `test-ginflow-pr-sync.py`): PR feedback becomes a follow-up card (PRFB-1). `publish.publish` also comments `[ginflow] updated <sha> by <KEY>` on an existing PR (tested by `test_publish_hook.py`). PRFB-2: merged PRs retarget child PR bases and fast-forward local main; `ginflow init` step `sync` installs the `ginflow-pr-sync:<board>` cron job (tested by `test-ginflow-pr-sync.py`, `test-ginflow-init.py`).
- Every plugin test file runs under `make test` (`test_native_review_transition.py`, `test_block_routing.py` and the trace integration test skip when the `hermes` CLI is missing).
