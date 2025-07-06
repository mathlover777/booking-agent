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

deploy-common: ## Deploy common stack (shared across stages)
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
test-email: ## Test email processing with default S3 key
	@echo "Testing email processing..."
	cd src && python test_email_processor.py

# Clerk utility test
test-clerk: ## Test Clerk OAuth token retrieval
	@echo "Testing Clerk OAuth token retrieval..."
	cd src && python test_clerk_util.py

# Calendar tools tests
test-calendar-bookings: ## Test calendar bookings retrieval
	@echo "Testing calendar bookings retrieval..."
	cd src && python -c "from test_calendar_tools import test_get_bookings; test_get_bookings()"

test-calendar-book: ## Test calendar event booking
	@echo "Testing calendar event booking..."
	cd src && python -c "from test_calendar_tools import test_book_event; test_book_event()"

test-calendar-cancel: ## Test calendar event cancellation
	@echo "Testing calendar event cancellation..."
	cd src && python -c "from test_calendar_tools import test_cancel_event; test_cancel_event()"

# High-level calendar function tests
test-high-level-availability: ## Test high-level get_availability function
	@echo "Testing high-level get_availability function..."
	cd src && python -c "from test_calendar_tools import test_high_level_get_availability; test_high_level_get_availability()"

test-high-level-book: ## Test high-level book_event function
	@echo "Testing high-level book_event function..."
	cd src && python -c "from test_calendar_tools import test_high_level_book_event; test_high_level_book_event()"

test-high-level-cancel: ## Test high-level cancel_event function
	@echo "Testing high-level cancel_event function..."
	cd src && python -c "from test_calendar_tools import test_high_level_cancel_event; test_high_level_cancel_event()"
