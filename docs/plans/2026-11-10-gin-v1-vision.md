---
User story:
  - Receive a task
  - Brainstorming with AI agent
  - Writing plan -> to spec -> to tickets
  - Run gin workflow
    - Follow ginflow skill and ginflow-gate to build the doc and runtime artifacts
    - Execute
    - Review phase 1 by the reviewer agent profile
    - Pass -> create a pull request
  - Human read the pull request, the evidences:
      - If the pr is fine -> merge to the feat branch
      - If not, make comments and go to feedback loop
---

Will call is it gin@v1

- Infras:
  1. Deps:
  - Use hermes kanban runtime
  - Use hermes profile (one orchestration and one worker)
  - Build the hermes plugins to inject the ginflow context, ginflow-gating
    - In the plugins, add some skills that related to the workflow
      - retro: after implement a task, what is the knowledge we gain? (use notion as backlog and notebookLM as the resources)
      - cleanup: after implement a task, whether the worktree be merge back to the feat branch and cleanup it, update the label or close the issues
  2. Skills:
  - nlm-skill for notion
  - mattcopock skillset for breakdown the problems into small, make the problem for clearly between me an coding agents
  - supperpowers for brainstorming
  3. MCP:
  - gemini-notebook-lm for resources recording
  - codegraph for coding task
  4. Workflow guide
  - Define the ginflow-skill that guide the agent work with 4 phases, worktree integration
  - Write the rules in the gating that allow the kanban card is move to next stage
  - Write the guide that allow the agent create the mr

---

- In the startup workflow, let's check the dispatch_reviewer of the kanban setup of hermes (make sure the review phase 1 is run)
- Optional: guide the agent to install the mattcopock skills

---

- Notify:
  - Kanban complete/fail via the gateway (telegram/slack follow the project config)
  - Kanban recovery and report (telegram/slack follow the project config)

---

- Update ginflow skill.md guide the agent make the kanban card id consistency!

---
