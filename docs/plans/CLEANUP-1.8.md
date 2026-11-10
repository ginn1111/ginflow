---
status: draft
scope: GLOSSARY.md, docs/adrs/0001-artifact-first-execution-packages.md, skills/ginflow/SKILL.md; docs/architecture/; docs/specs/GINFLOW-MR-2.md, docs/plans/GINFLOW-MR-2.md
owner: ginb
---

# Plan — CLEANUP-1.8: Architecture docs and Draw.io match the code

Source: umbrella plan for GitHub #1. Line numbers are approximate; locate code by symbol. Earlier tickets are merged into `main` before this card starts and may have changed nearby code — re-read before editing. Ignore any umbrella-plan step about creating cards or closing the umbrella card. RED test first, then change, then `make lint test`.

## Step 1: Remove remaining "v2"/versioned wording in docs

Exact edits:
- `skills/ginflow/SKILL.md:27`: "approve artifact-first Execution Package v2 (spec, plan, Tickets)" → "approve artifact-first Execution Package (spec, plan, Tickets)".
- `GLOSSARY.md:6`: "artifact-first Ginflow v2 contract" → "artifact-first Ginflow contract".
- `docs/adrs/0001-artifact-first-execution-packages.md:5`: "Ginflow v2 uses" → "Ginflow uses".
- `docs/architecture/ginflow-flow.md:19`: "validates versioned pure records" → "validates pure records"; `:29` "retains artifact-first Execution Package v2" → "uses the artifact-first Execution Package"; `:72` `"Shaping<br/>Execution Package v2"` → `"Shaping<br/>Execution Package"`.

Verify: `grep -rnE "\bv[12]\b|workflow version" --include=*.md skills docs/architecture docs/adrs GLOSSARY.md README.md` → only unrelated hits (none expected). Leave `docs/specs/GINFLOW-MR-1.md`/`docs/plans/GINFLOW-MR-1.md` untouched (completed card; editing = artifact drift). Commit `docs(ginflow): drop versioned wording`.

## Step 2: Architecture docs + drawio sync

1. `docs/specs/GINFLOW-MR-2.md:3` (status draft): `core/ginflow-core/publish.py` → `skills/ginflow/lib/publish.py`; same in `docs/plans/GINFLOW-MR-2.md:11`.
2. `.hermes.md:60` (local, untracked — edit, never commit): replace `` `core/ginflow-core/`, `` with `` `skills/ginflow/lib/`, ``.
3. `docs/architecture/ginflow-reference.md`:
   - `ginflow-gate` row: "Hermes integration hooks, routing context, completion validation, feedback/recovery helpers" → "Hooks: `pre_llm_call` routing context; `pre_tool_call` block guard + completion gate + publish prepare; `post_tool_call` publish finish; `kanban_task_blocked` block routing. Feedback/recovery helpers exist but are not wired (see [integration-status](./integration-status.md))".
   - Add row after it: `| ginflow-trace plugin | Opt-in function tracing for gate/routing calls | plugins/ginflow-trace/ | No hooks; loaded through ginflow-gate trace_adapter |`.
   - Add row: `| Core loader | Single lookup of skills/ginflow/lib (repo, then ~/.agents/skills/ginflow/lib) | plugins/ginflow-gate/skill_lib.py | Only place plugins resolve core modules |`.
4. `docs/architecture/ginflow-flow.md`: add before `## Derived flow`:

```markdown
## Runtime hooks (ginflow-gate)

| Hermes hook | Handler | Effect |
| --- | --- | --- |
| `pre_llm_call` | `routing._routing_context` | inject route, mutation_allowed, startup validation |
| `pre_tool_call` | `block_routing._pre_tool_call` | `kanban_block` reason guard (`required_action`) |
| `pre_tool_call` | `gate.pre_tool_call` | completion/review evidence gate; reviewer injection; publish prepare |
| `post_tool_call` | `gate.post_tool_call` | publish finish (push + MR/PR) after reviewer `kanban_complete` |
| `kanban_task_blocked` | `block_routing.on_task_blocked` | transient auto-repair once; critical push to notify target |

Not wired yet: see [integration-status](./integration-status.md).
```
5. `docs/architecture/ginflow-system.drawio`, page **Harness system overview** (second `<diagram>`):
   - Cell `ginflow12-missing-observability`: `value="Observability: ginflow-trace (opt-in)"`, style `fillColor=#d5e8d4;strokeColor=#82b366;` (trace exists now).
   - Insert immediately before that page's closing `</root>`:

```xml
        <mxCell id="ginflow-cleanup-block-routing" parent="1" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;" value="Block routing&lt;br/&gt;kanban_task_blocked + kanban_block guard&lt;br/&gt;&lt;b&gt;Ownership: plugin&lt;/b&gt;" vertex="1">
          <mxGeometry height="60" width="170" x="1430" y="340" as="geometry" />
        </mxCell>
        <mxCell id="ginflow-cleanup-publish" parent="1" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;" value="Auto-publish MR/PR&lt;br/&gt;reviewer kanban_complete&lt;br/&gt;&lt;b&gt;Ownership: plugin&lt;/b&gt;" vertex="1">
          <mxGeometry height="60" width="170" x="1870" y="340" as="geometry" />
        </mxCell>
        <mxCell id="ginflow-cleanup-lib" parent="1" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;" value="skills/ginflow/lib&lt;br/&gt;single core home (skill_lib.load)" vertex="1">
          <mxGeometry height="60" width="200" x="2250" y="340" as="geometry" />
        </mxCell>
        <mxCell id="ginflow-cleanup-unwired" parent="1" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;" value="Not wired: initiative · execution_package · execution_batch · card_creation · decision · review_cycle · merge_request · followup · recovery_policy · feedback (see integration-status.md)" vertex="1">
          <mxGeometry height="60" width="420" x="2140" y="440" as="geometry" />
        </mxCell>
        <mxCell id="ginflow-cleanup-e1" edge="1" parent="1" source="3OxK573chlKwpl4-sLJv-36" target="ginflow-cleanup-block-routing" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="ginflow-cleanup-e2" edge="1" parent="1" source="3OxK573chlKwpl4-sLJv-47" target="ginflow-cleanup-publish" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="ginflow-cleanup-e3" edge="1" parent="1" source="3OxK573chlKwpl4-sLJv-49" target="ginflow-cleanup-lib" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
```
   (`-36` = "Ginflow gate", `-47` = "Mark complete task", `-49` = "Core".)
   - Verify XML + unique ids:
```bash
python3 - <<'PY'
import xml.etree.ElementTree as E, collections
t = E.parse("docs/architecture/ginflow-system.drawio")
for d in t.getroot().iter("diagram"):
    ids = [c.get("id") for c in d.iter("mxCell")]
    dup = [i for i, n in collections.Counter(ids).items() if n > 1]
    assert not dup, (d.get("name"), dup)
print("drawio ok")
PY
```
   Expect `drawio ok`. Optionally open in draw.io desktop to nudge overlaps.

Commit `docs(architecture): sync hooks, trace, core loader, unwired modules`.