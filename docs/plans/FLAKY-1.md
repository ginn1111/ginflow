---
status: approved
card: FLAKY-1
scope: see spec
owner: ginb
---

# Plan — FLAKY-1

Content rules: `references/artifact-content-guide.md` in `ginflow`. Commit per step.

## Step 1: reproduce and find the writer (B1)
- Loop `python3 plugins/ginflow-gate/test_ginflow_gate.py` until it fails (run 2–3 suites in parallel to provoke it). On failure, list what is in the leftover `cache/` dir and which processes hold files under the temp home (`ps`, `/proc/*/cwd`, `/proc/*/fd`).
- Record findings as a card comment.

## Step 2: reliable cleanup (B2–B4)
- Stop/await the writer if it is ours to control; otherwise wrap temp-home removal in a bounded retry. Apply to all three tests. Keep body failures primary (B3).
- Verify: 5 consecutive passes of `python3 plugins/ginflow-gate/test_ginflow_gate.py` and `make trace-test`; `ls $TMPDIR | grep -c 'ginflow-.*-home-'` → 0 afterwards.

## Step 3: verify and hand off
- `make lint test; echo exit=$?` → 0. Spec + plan `status: completed`; commit; `kanban_request_review` with verification and `artifact_baseline`.
