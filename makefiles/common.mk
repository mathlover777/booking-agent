# Vibes CDK Project - Common Variables and Utilities

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

# Help target
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