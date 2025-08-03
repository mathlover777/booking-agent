# Vibes CDK Project - Core Testing Targets

.PHONY: test-email test-calendar test-agent test-agent-calendar-failures test-pytest test

# Run all tests using pytest (only tests in /tests directory)
test-pytest: ## Run all tests using pytest (only tests in /tests directory)
	@echo "Running all tests with pytest..."
	source /Users/sourav/doc32/v2/.venv/bin/activate && pytest tests/ -v

# Simple alias for pytest
test: test-pytest ## Run all tests (alias for test-pytest)

# Email processing test
test-email: ## Test email processing and auto-reply with default S3 key
	@echo "Testing email processing and auto-reply..."
	cd src && python test_email_processor.py

# Calendar workflow test
test-calendar: ## Test complete calendar workflow (availability, book, delete)
	@echo "Testing complete calendar workflow..."
	cd src && python -m calendar_utils.test_calendar_util

# Agent integration tests (replaces old booking agent tests)
test-agent: ## Test agent integration (all tests)
	@echo "Testing agent integration (all tests)..."
	cd src && python -m booking_agent.test_agent_integration

test-agent-calendar-failures: ## Test calendar owner resolution failures (deterministic)
	@echo "Testing calendar owner resolution failures..."
	cd src && python -c "from booking_agent.test_agent_integration import test_all_calendar_owner_failures; test_all_calendar_owner_failures()" 