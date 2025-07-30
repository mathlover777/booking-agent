# Vibes CDK Project - Calendar Owner Resolver Tests

.PHONY: test-calendar-owner-resolver test-calendar-owner-resolver-integration test-case-1-single-agent test-case-2-agent-not-found test-case-3-agent-typo test-case-4-llm-disambiguation test-case-5-missing-user-email test-case-6-typo-with-valid test-case-7-two-agents-one-typo test-case-8-case-insensitive test-case-9-display-name test-case-10-all-typos test-all-cases

test-calendar-owner-resolver: ## Test calendar owner resolution logic
	@echo "Testing calendar owner resolution logic..."
	cd src && python -m booking_agent.test_calendar_owner_resolver

test-calendar-owner-resolver-integration: ## Test calendar owner resolver with real AWS services
	@echo "Testing calendar owner resolver integration tests..."
	cd src && python -m booking_agent.test_calendar_owner_resolver_integration

# Real integration tests with synthetic data
test-case-1-single-agent: ## Test Case 1: Single agent, user in thread
	@echo "Testing Case 1: Single agent, user in thread..."
	cd src && python -c "from booking_agent.test_calendar_owner_resolver_integration import test_case_1_single_agent_user_in_thread; test_case_1_single_agent_user_in_thread()"

test-case-2-agent-not-found: ## Test Case 2: Agent not found in DynamoDB
	@echo "Testing Case 2: Agent not found in DynamoDB..."
	cd src && python -c "from booking_agent.test_calendar_owner_resolver_integration import test_case_2_agent_not_found_in_dynamodb; test_case_2_agent_not_found_in_dynamodb()"

test-case-3-agent-typo: ## Test Case 3: Agent typo - wrong person
	@echo "Testing Case 3: Agent typo - wrong person..."
	cd src && python -c "from booking_agent.test_calendar_owner_resolver_integration import test_case_3_agent_typo_wrong_person; test_case_3_agent_typo_wrong_person()"

test-case-4-llm-disambiguation: ## Test Case 4: Two agents, LLM disambiguation
	@echo "Testing Case 4: Two agents, LLM disambiguation..."
	cd src && python -c "from booking_agent.test_calendar_owner_resolver_integration import test_case_4_two_agents_llm_disambiguation; test_case_4_two_agents_llm_disambiguation()"

test-case-5-missing-user-email: ## Test Case 5: Missing user_email field
	@echo "Testing Case 5: Missing user_email field..."
	cd src && python -c "from booking_agent.test_calendar_owner_resolver_integration import test_case_5_missing_user_email_field; test_case_5_missing_user_email_field()"

test-case-6-typo-with-valid: ## Test Case 6: Typo agent + valid agent = SUCCESS
	@echo "Testing Case 6: Typo with valid agent..."
	cd src && python -c "from booking_agent.test_calendar_owner_resolver_integration import test_case_6_typo_with_valid_agent; test_case_6_typo_with_valid_agent()"

test-case-7-two-agents-one-typo: ## Test Case 7: Two agents, one typo = SUCCESS
	@echo "Testing Case 7: Two agents, one typo..."
	cd src && python -c "from booking_agent.test_calendar_owner_resolver_integration import test_case_7_two_agents_one_typo; test_case_7_two_agents_one_typo()"

test-case-8-case-insensitive: ## Test Case 8: Case insensitive email matching
	@echo "Testing Case 8: Case insensitive email matching..."
	cd src && python -c "from booking_agent.test_calendar_owner_resolver_integration import test_case_8_case_insensitive_email_matching; test_case_8_case_insensitive_email_matching()"

test-case-9-display-name: ## Test Case 9: Email with display name format
	@echo "Testing Case 9: Email with display name..."
	cd src && python -c "from booking_agent.test_calendar_owner_resolver_integration import test_case_9_email_with_display_name; test_case_9_email_with_display_name()"

test-case-10-all-typos: ## Test Case 10: All agents are typos = FAILURE
	@echo "Testing Case 10: All agents are typos..."
	cd src && python -c "from booking_agent.test_calendar_owner_resolver_integration import test_case_10_all_agents_typos; test_case_10_all_agents_typos()"

test-all-cases: test-case-1-single-agent test-case-2-agent-not-found test-case-3-agent-typo test-case-4-llm-disambiguation test-case-5-missing-user-email test-case-6-typo-with-valid test-case-7-two-agents-one-typo test-case-8-case-insensitive test-case-9-display-name test-case-10-all-typos ## Test all integration cases 