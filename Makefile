.PHONY: install uninstall install-test verify doctor doctor-deps community-update clean lint test lifecycle-test plugin-test trace-test

# === Pre-flight ===
doctor:
	@echo "=== CodeGraph ==="; command -v codegraph && codegraph --version || echo "MISSING"
	@echo "=== Python ==="; python3 --version
	@echo "=== Git ==="; git --version

doctor-deps:
	python3 -m pip install pyyaml

# === Setup ===
## Install Ginflow skill into selected Hermes profiles
install:
	bash scripts/install.sh install $(PROFILES)

## Remove installer-owned Ginflow integrations
uninstall:
	bash scripts/install.sh uninstall

## Verify integrations in existing profiles via ginflow harness
verify:
	python3 skills/ginflow/scripts/validate-harness.py --setup-repo . --json

# === Community assets ===
## Clone/pull community skill repos
community-update:
	./scripts/community-setup.sh --apply

# === Hygiene ===
## Remove generated local files
clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
	rm -rf .codegraph

lint:
	bash -n scripts/*.sh
	@if compgen -G 'scripts/*.py' >/dev/null; then python3 -m py_compile scripts/*.py; fi
	python3 -m py_compile skills/ginflow/scripts/*.py
	@echo "lint ok"

## Run deterministic repository tests
test: lint core-test lifecycle-test plugin-test install-test

core-test:
	python3 skills/ginflow/lib/test_execution_package.py
	python3 skills/ginflow/lib/test_card_creation.py
	python3 skills/ginflow/lib/test_provider_document.py
	python3 skills/ginflow/lib/test_initiative.py
	python3 skills/ginflow/lib/test_execution_batch.py
	python3 skills/ginflow/lib/test_decision.py
	python3 skills/ginflow/lib/test_review_cycle.py
	python3 skills/ginflow/lib/test_followup.py
	python3 skills/ginflow/lib/test_merge_request.py
	python3 skills/ginflow/lib/test_publish.py
	python3 skills/ginflow/lib/test_initiative_workflow.py

# ponytail: keep lib tests as direct scripts until shared repository test runner exists.

## Canonical ginflow flat-flow integration test (single command, per-step PASS/FAIL)
lifecycle-test:
	python3 skills/ginflow/scripts/test-ginflow-lifecycle.py
	python3 skills/ginflow/scripts/test-project-reviewer.py
	python3 skills/ginflow/scripts/test-document-config.py
	python3 skills/ginflow/scripts/test-worktree-context.py

install-test:
	bash scripts/test-install.sh

plugin-test:
	python3 plugins/ginflow-gate/test_ginflow_gate.py
	python3 plugins/ginflow-gate/test_document_baseline.py
	python3 plugins/ginflow-gate/test_blocker_reporting.py
	python3 plugins/ginflow-gate/test_recovery_policy.py
	python3 plugins/ginflow-gate/test_reviewer_injection.py
	python3 plugins/ginflow-gate/test_block_guard.py
	python3 plugins/ginflow-gate/test_publish_hook.py
	@if command -v hermes >/dev/null 2>&1; then python3 plugins/ginflow-gate/test_block_routing.py; else echo "SKIP: block routing (hermes CLI not installed)"; fi
	@if command -v hermes >/dev/null 2>&1; then python3 plugins/ginflow-gate/test_native_review_transition.py; else echo "SKIP: native review transition (hermes CLI not installed)"; fi
	$(MAKE) trace-test

trace-test:
	python3 plugins/ginflow-trace/test_ginflow_trace.py
	@if command -v hermes >/dev/null 2>&1; then python3 plugins/ginflow-trace/test_ginflow_trace_integration.py; else echo "SKIP: trace integration (hermes CLI not installed)"; fi
