# Decision phase

Read-only human review after Integration succeeds or blocks. Decision never completes an Initiative by itself.

Terms: see `GLOSSARY.md` (Initiative, Execution Batch, Integration, Change Group, Decision, Review Cycle, Decision Projection, Notification, MR Intent). Code: `core/ginflow-core/{execution_batch,decision,review_cycle,merge_request}.py`.

## Agent steps

1. Confirm Integration card is terminal. Stop if not.
2. Map every changed path to a Change Group, or to a justified generated/excluded bucket.
3. Reference evidence for every nontrivial claim. Never use raw logs, secrets, personal data, prompts, or transcripts.
4. Append a new `review_cycle` revision. Never edit prior revisions.
5. Build `decision_projection` (bounded, redacted view). It is not workflow authority.
6. Offer human dispositions per Change Group: `accept`, `enhance`, `reject`, `defer`.
7. Record the aggregate outcome derived from them.

## Outcomes

| Outcome | Effect |
| --- | --- |
| `approved_for_mr` | only outcome that completes Ginflow lifecycle; yields provider-neutral `merge_request_intent` |
| `enhancement_requested` | back to Shaping/Execution |
| `rejected` | stop |
| `resume_execution` | new Execution Batch |
| `reshape_required` | back to Shaping |
| `stopped` | halt, no MR |

Publication and merge are separate steps, never implied by `approved_for_mr`.

Material outcomes emit a `notification` envelope. Transport is adapter-owned; do not send messages yourself.
