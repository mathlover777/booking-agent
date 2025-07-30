# Vibes CDK Project - Agent Integration Tests

.PHONY: test-agent-integration test-agent-integration-calendar-failures test-agent-integration-end-to-end test-agent-integration-all test-agent-case-1-no-agents test-agent-case-2-agent-not-registered test-agent-case-3-owner-not-in-conversation test-agent-case-4-missing-user-email test-agent-case-5-availability test-agent-case-6-book-event test-agent-case-7-cancel-event test-agent-case-8-llm-disambiguation

# ---------------------------------------------------------------------------
# Agent integration tests
# ---------------------------------------------------------------------------

test-agent-integration: ## Test agent integration (all tests)
	@echo "Testing agent integration (all tests)..."
	cd src && python -m booking_agent.test_agent_integration

test-agent-integration-calendar-failures: ## Test all calendar owner resolution failure cases (deterministic)
	@echo "Testing calendar owner resolution failure cases..."
	cd src && python -c "from booking_agent.test_agent_integration import test_all_calendar_owner_failures; test_all_calendar_owner_failures()"

test-agent-integration-end-to-end: ## Test all end-to-end success flows (requires Google Calendar)
	@echo "Testing end-to-end success flows..."
	cd src && python -c "from booking_agent.test_agent_integration import test_all_end_to_end_success; test_all_end_to_end_success()"

test-agent-integration-all: test-agent-integration-calendar-failures test-agent-integration-end-to-end ## Run all agent tests in sequence

# ---------------------------------------------------------------------------
# Individual test cases for calendar owner resolution failures ---------------
# ---------------------------------------------------------------------------

test-agent-case-1-no-agents: ## Test Case 1: No booking agents found
	@echo "Testing Case 1: No booking agents found..."
	cd src && python -c "from booking_agent.test_agent_integration import test_case_1_no_booking_agents_found; test_case_1_no_booking_agents_found()"

test-agent-case-2-agent-not-registered: ## Test Case 2: Booking agent not registered
	@echo "Testing Case 2: Booking agent not registered..."
	cd src && python -c "from booking_agent.test_agent_integration import test_case_2_booking_agent_not_registered; test_case_2_booking_agent_not_registered()"

test-agent-case-3-owner-not-in-conversation: ## Test Case 3: Calendar owner not in conversation
	@echo "Testing Case 3: Calendar owner not in conversation..."
	cd src && python -c "from booking_agent.test_agent_integration import test_case_3_calendar_owner_not_in_conversation; test_case_3_calendar_owner_not_in_conversation()"

test-agent-case-4-missing-user-email: ## Test Case 4: Missing user_email field
	@echo "Testing Case 4: Missing user_email field..."
	cd src && python -c "from booking_agent.test_agent_integration import test_case_4_missing_user_email_field; test_case_4_missing_user_email_field()"

# ---------------------------------------------------------------------------
# Individual test cases for end-to-end success flows ------------------------
# ---------------------------------------------------------------------------

test-agent-case-5-availability: ## Test Case 5: Share availability (end-to-end)
	@echo "Testing Case 5: Share availability (end-to-end)..."
	cd src && python -c "from booking_agent.test_agent_integration import test_case_5_share_availability; test_case_5_share_availability()"

test-agent-case-6-book-event: ## Test Case 6: Book event (end-to-end)
	@echo "Testing Case 6: Book event (end-to-end)..."
	cd src && python -c "from booking_agent.test_agent_integration import test_case_6_book_event; test_case_6_book_event()"

test-agent-case-7-cancel-event: ## Test Case 7: Cancel event (end-to-end)
	@echo "Testing Case 7: Cancel event (end-to-end)..."
	cd src && python -c "from booking_agent.test_agent_integration import test_case_7_cancel_event; test_case_7_cancel_event()"

test-agent-case-8-llm-disambiguation: ## Test Case 8: Multiple agents, LLM disambiguation
	@echo "Testing Case 8: Multiple agents, LLM disambiguation..."
	cd src && python -c "from booking_agent.test_agent_integration import test_case_8_multiple_agents_llm_disambiguation; test_case_8_multiple_agents_llm_disambiguation()" 