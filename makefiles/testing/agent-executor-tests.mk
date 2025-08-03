.PHONY: test-agent-exec-all test-agent-exec-single

# ---------------------------------------------------------------------------
# Agent-executor integration tests (using pytest)
# ---------------------------------------------------------------------------

test-agent-exec-all: ## Run all agent-executor integration tests (usage: make test-agent-exec-all [LOGS=1])
	@echo "Running ALL agent-executor integration tests..."
	@if [ "$(LOGS)" = "1" ]; then \
		echo "📋 Logs enabled - showing detailed output"; \
		pytest tests/integration/test_agent_executor.py -v -s --log-cli-level=INFO -m integration; \
	else \
		pytest tests/integration/test_agent_executor.py -v -m integration; \
	fi

test-agent-exec-single: ## Run a single agent-executor test by function name (usage: make test-agent-exec-single TEST=test_share_availability [LOGS=1])
	@if [ -z "$(TEST)" ]; then \
		echo "Error: TEST parameter is required. Usage: make test-agent-exec-single TEST=test_share_availability"; \
		exit 1; \
	fi
	@echo "Running agent-executor test: $(TEST)"
	@if [ "$(LOGS)" = "1" ]; then \
		echo "📋 Logs enabled - showing detailed output"; \
		pytest tests/integration/test_agent_executor.py::$(TEST) -v -s --log-cli-level=INFO; \
	else \
		pytest tests/integration/test_agent_executor.py::$(TEST) -v; \
	fi 