# Vibes CDK Project Makefile
# Supports multi-stage deployment with shared infrastructure

# Default values
STAGE ?= dev
AWS_REGION ?= ap-south-1
# AWS_PROFILE must be set in environment

# CDK commands
CDK = cdk
CDK_DEPLOY = $(CDK) deploy
CDK_DESTROY = $(CDK) destroy
CDK_SYNTH = $(CDK) synth
CDK_DIFF = $(CDK) diff
CDK_BOOTSTRAP = $(CDK) bootstrap

# Stack names
COMMON_STACK = VibesCommonStack
EMAIL_PROCESSOR_STACK = VibesEmailProcessorStack$(STAGE)

.PHONY: help bootstrap deploy-common deploy-processor deploy-all destroy-processor destroy-common destroy-all diff-processor diff-common synth setup-ses clean test-email test-clerk

help: ## Show this help message
	@echo "Vibes CDK Project - Multi-stage deployment"
	@echo ""
	@echo "Usage: make <target> [STAGE=<stage>]"
	@echo "Note: AWS_PROFILE must be set in environment"
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Stages: dev (default), staging, prod"
	@echo "Examples:"
	@echo "  export AWS_PROFILE=myprofile"
	@echo "  make deploy-common"
	@echo "  make deploy-processor STAGE=staging"
	@echo "  make deploy-all STAGE=prod"

bootstrap: ## Bootstrap CDK in the current account/region
	$(CDK_BOOTSTRAP) --profile $(AWS_PROFILE)

clean-layer: ## Remove all files from lambda-layer directories
	rm -rf lambda-layer/common/python/*
	rm -rf lambda-layer/auth/python/*

install-layer-deps: ## Install Python dependencies for Lambda layers (Linux compatible)
	@echo "Installing Lambda layer dependencies..."
	@echo "Installing common dependencies..."
	pip3 install --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all: --upgrade -r layers/requirements-common.txt -t lambda-layer/common/python/
	@echo "Installing auth dependencies..."
	pip3 install --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all: --upgrade -r layers/requirements-auth.txt -t lambda-layer/auth/python/

install-local-deps: ## Install Python dependencies locally for development
	@echo "Installing local Python dependencies..."
	@echo "Installing common dependencies..."
	pip3 install -r layers/requirements-common.txt
	@echo "Installing auth dependencies..."
	pip3 install -r layers/requirements-auth.txt

deploy-common: clean-layer install-layer-deps ## Deploy common stack (shared across stages)
	@echo "Deploying common stack..."
	$(CDK_DEPLOY) $(COMMON_STACK) --profile $(AWS_PROFILE) --require-approval never

deploy-processor: ## Deploy email processor stack
	@echo "Deploying email processor stack for $(STAGE)..."
	$(CDK_DEPLOY) $(EMAIL_PROCESSOR_STACK) --profile $(AWS_PROFILE) --require-approval never --context stage=$(STAGE)

deploy-all: deploy-common deploy-processor ## Deploy both common and email processor stacks

destroy-processor: ## Destroy email processor stack
	@echo "Destroying email processor stack for $(STAGE)..."
	$(CDK_DESTROY) $(EMAIL_PROCESSOR_STACK) --profile $(AWS_PROFILE) --force --context stage=$(STAGE)

destroy-common: ## Destroy common stack (WARNING: affects all stages)
	@echo "WARNING: This will destroy infrastructure shared across all stages!"
	@read -p "Are you sure? Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ]
	$(CDK_DESTROY) $(COMMON_STACK) --profile $(AWS_PROFILE) --force

destroy-all: destroy-processor destroy-common ## Destroy both email processor and common stacks

diff-processor: ## Show differences for email processor stack
	$(CDK_DIFF) $(EMAIL_PROCESSOR_STACK) --profile $(AWS_PROFILE) --context stage=$(STAGE)

diff-common: ## Show differences for common stack
	$(CDK_DIFF) $(COMMON_STACK) --profile $(AWS_PROFILE)

synth: ## Synthesize CloudFormation templates
	$(CDK_SYNTH) --context stage=$(STAGE)

setup-ses: ## Run SES domain setup script (after common stack deployment)
	@echo "Setting up SES domain verification and DKIM records..."
	python vibes/scripts/setup_ses_domain.py

clean: ## Clean up CDK artifacts
	rm -rf cdk.out/
	rm -rf .cdk.staging/

# Development helpers
dev: STAGE=dev ## Deploy dev environment
dev: deploy-all

staging: STAGE=staging ## Deploy staging environment  
staging: deploy-all

prod: STAGE=prod ## Deploy production environment
prod: deploy-all

# Quick test commands
test-dev: STAGE=dev ## Quick dev deployment
test-dev: deploy-stage

test-staging: STAGE=staging ## Quick staging deployment
test-staging: deploy-stage

# Email processing test
test-email: ## Test email processing and auto-reply with default S3 key
	@echo "Testing email processing and auto-reply..."
	cd src && python test_email_processor.py

# Calendar workflow test
test-calendar: ## Test complete calendar workflow (availability, book, delete)
	@echo "Testing complete calendar workflow..."
	cd src && python -m calendar_utils.test_calendar_util



# Booking agent AI tests
test-booking-agent: ## Test booking agent AI integration
	@echo "Testing booking agent AI integration..."
	cd src && python test_booking_agent.py

test-real-email: ## Test booking agent with real S3 email
	@echo "Testing booking agent with real S3 email..."
	cd src && python -c "from test_booking_agent import test_real_s3_email; test_real_s3_email()"

test-calendar-owner-resolver: ## Test calendar owner resolution logic
	@echo "Testing calendar owner resolution logic..."
	cd src && python -m booking_agent.test_calendar_owner_resolver

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

test-calendar-owner-resolver-integration: ## Test calendar owner resolver with real AWS services
	@echo "Testing calendar owner resolver integration tests..."
	cd src && python -m booking_agent.test_calendar_owner_resolver_integration

# User Email API tests

test-get-user-email: ## Test GET /user/email endpoint
	@echo "Testing GET /user/email endpoint..."
	cd src && python -c "from apis.test_user_email_api import test_get_user_email; test_get_user_email()"

test-update-user-email: ## Test PUT /user/email endpoint
	@echo "Testing PUT /user/email endpoint..."
	cd src && python -c "from apis.test_user_email_api import test_update_user_email; test_update_user_email()"

test-jwt-authorizer: ## Test JWT authorizer function
	@echo "Testing JWT authorizer function..."
	cd src && python -c "from apis.test_user_email_api import test_jwt_authorizer; test_jwt_authorizer()"

test-email-availability: ## Test POST /user/email endpoint for email availability check
	@echo "Testing POST /user/email endpoint for email availability check..."
	cd src && python -c "from apis.test_user_email_api import test_check_email_availability; test_check_email_availability()"

