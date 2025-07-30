.PHONY: test-agent-exec-availability test-agent-exec-availability-range test-agent-exec-book test-agent-exec-cancel test-agent-exec-all

# ---------------------------------------------------------------------------
# Agent-executor integration tests
# ---------------------------------------------------------------------------

test-agent-exec-availability: ## Test sharing availability (basic)
	@echo "Testing agent-executor – availability request..."
	cd src && python -c "from booking_agent.test_agent_executor_integration import test_case_1_share_availability as t; t()"

test-agent-exec-availability-range: ## Test sharing availability for another range
	@echo "Testing agent-executor – availability (other range)..."
	cd src && python -c "from booking_agent.test_agent_executor_integration import test_case_2_share_availability_other_range as t; t()"

test-agent-exec-book: ## Test booking an event
	@echo "Testing agent-executor – book event..."
	cd src && python -c "from booking_agent.test_agent_executor_integration import test_case_3_book_event as t; t()"

test-agent-exec-cancel: ## Test cancelling an event
	@echo "Testing agent-executor – cancel event..."
	cd src && python -c "from booking_agent.test_agent_executor_integration import test_case_4_cancel_event as t; t()"

test-agent-exec-all: ## Run all agent-executor tests in sequence
	@echo "Running ALL agent-executor tests..."
	cd src && python -m booking_agent.test_agent_executor_integration 