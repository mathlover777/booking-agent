# Vibes CDK Project - Main Testing Targets

.PHONY: unit-test int-test test-single

# Run unit tests using pytest (only tests in /tests/unit directory)
unit-test: ## Run unit tests using pytest (only tests in /tests/unit directory)
	@echo "Running unit tests with pytest..."
	source /Users/sourav/doc32/v2/.venv/bin/activate && pytest tests/unit/ -v

# Run integration tests using pytest (only tests in /tests/integration directory)
int-test: ## Run integration tests using pytest (only tests in /tests/integration directory)
	@echo "Running integration tests with pytest..."
	source /Users/sourav/doc32/v2/.venv/bin/activate && pytest tests/integration/ -v

# Run a single test by name (usage: make test-single TEST=test_share_availability [LOGS=1])
test-single: ## Run a single test by name (usage: make test-single TEST=test_share_availability [LOGS=1])
	@if [ -z "$(TEST)" ]; then \
		echo "Error: TEST parameter is required. Usage: make test-single TEST=test_share_availability"; \
		exit 1; \
	fi
	@echo "Running test: $(TEST)"
	@if [ "$(LOGS)" = "1" ]; then \
		echo "📋 Logs enabled - showing detailed output"; \
		source /Users/sourav/doc32/v2/.venv/bin/activate && pytest $(TEST) -v -s --log-cli-level=INFO; \
	else \
		source /Users/sourav/doc32/v2/.venv/bin/activate && pytest $(TEST) -v; \
	fi 