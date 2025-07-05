# Vibes Email Processing - CDK Makefile
# Following CDK best practices

# Variables
STACK_NAME := VibesStack
CDK_APP := app.py
CDK_OUTPUT_DIR := cdk.out
SRC_DIR := src
REQUIREMENTS_FILE := requirements.txt

# Python and CDK commands
PYTHON := python3
PIP := pip3
CDK := cdk

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

.PHONY: help install deps synth deploy destroy diff logs clean test

# Default target
help: ## Show this help message
	@echo "$(BLUE)Vibes Email Processing - CDK Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-15s$(NC) %s\n", $$1, $$2}'

# Development setup
install: ## Install Python dependencies
	@echo "$(BLUE)Installing Python dependencies...$(NC)"
	$(PIP) install -r $(REQUIREMENTS_FILE)
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

deps: install ## Alias for install

# CDK operations
synth: ## Synthesize CDK app to CloudFormation template
	@echo "$(BLUE)Synthesizing CDK app...$(NC)"
	$(CDK) synth
	@echo "$(GREEN)✓ CDK app synthesized$(NC)"

deploy: ## Deploy the stack to AWS
	@echo "$(BLUE)Deploying $(STACK_NAME) to AWS...$(NC)"
	@echo "$(YELLOW)Note: Make sure you have AWS credentials configured and CDK bootstrapped$(NC)"
	$(CDK) deploy --require-approval never
	@echo "$(GREEN)✓ Stack deployed successfully$(NC)"
	@echo "$(YELLOW)📧 Email Processing Setup:$(NC)"
	@echo "   - Domain: bhaang.com (automatically configured)"
	@echo "   - Email: X@bhaang.com"
	@echo "   - S3 Bucket: booking-agent-vibes"
	@echo "   - Lambda function: EmailProcessor"
	@echo "   - SES domain verification (automatic)"
	@echo "   - MX records (automatic)"
	@echo ""
	@echo "$(GREEN)✅ Everything is automated! Test by sending email to X@bhaang.com$(NC)"

destroy: ## Destroy the stack from AWS
	@echo "$(RED)Destroying $(STACK_NAME) from AWS...$(NC)"
	$(CDK) destroy --force
	@echo "$(GREEN)✓ Stack destroyed$(NC)"

diff: ## Show differences between deployed and local stack
	@echo "$(BLUE)Showing differences...$(NC)"
	$(CDK) diff

# Monitoring and debugging
logs: ## Tail CloudWatch logs for the lambda function
	@echo "$(BLUE)Tailing CloudWatch logs...$(NC)"
	aws logs tail /aws/lambda/$(STACK_NAME)-EmailProcessor --follow

logs-lambda: ## Show recent logs for lambda function
	@echo "$(BLUE)Recent lambda logs...$(NC)"
	aws logs describe-log-streams --log-group-name /aws/lambda/$(STACK_NAME)-EmailProcessor --order-by LastEventTime --descending --max-items 1 --query 'logStreams[0].logStreamName' --output text | xargs -I {} aws logs get-log-events --log-group-name /aws/lambda/$(STACK_NAME)-EmailProcessor --log-stream-name {}

# Testing
test: ## Run tests
	@echo "$(BLUE)Running tests...$(NC)"
	$(PYTHON) -m pytest tests/ -v

test-email: ## Test email processing by sending a test email
	@echo "$(BLUE)Sending test email to X@bhaang.com...$(NC)"
	@echo "Subject: Test Email from Makefile" | mail -s "Test Email" X@bhaang.com
	@echo "$(GREEN)✓ Test email sent$(NC)"

# Development workflow
dev: install synth ## Development workflow: install deps and synthesize
	@echo "$(GREEN)✓ Development environment ready$(NC)"

full-deploy: install synth deploy ## Full deployment workflow
	@echo "$(GREEN)✓ Full deployment completed$(NC)"

first-deploy: install bootstrap full-deploy ## First time deployment (includes bootstrap)
	@echo "$(GREEN)✓ First deployment completed$(NC)"

# Cleanup
clean: ## Clean build artifacts
	@echo "$(BLUE)Cleaning build artifacts...$(NC)"
	rm -rf $(CDK_OUTPUT_DIR)
	rm -rf __pycache__
	rm -rf $(SRC_DIR)/__pycache__
	rm -rf .pytest_cache
	find . -name "*.pyc" -delete
	@echo "$(GREEN)✓ Cleaned$(NC)"

# Validation and linting
validate: ## Validate CDK app
	@echo "$(BLUE)Validating CDK app...$(NC)"
	$(CDK) synth --quiet
	@echo "$(GREEN)✓ CDK app is valid$(NC)"

# Security and compliance
security-check: ## Run security checks
	@echo "$(BLUE)Running security checks...$(NC)"
	bandit -r $(SRC_DIR)/
	@echo "$(GREEN)✓ Security check completed$(NC)"

# Documentation
docs: ## Generate documentation
	@echo "$(BLUE)Generating documentation...$(NC)"
	@echo "$(YELLOW)📧 Email Processing System$(NC)"
	@echo "Architecture:"
	@echo "  1. SES receives emails for X@bhaang.com"
	@echo "  2. S3 stores raw email files in booking-agent-vibes"
	@echo "  3. Lambda processes emails when stored in S3"
	@echo "  4. CloudWatch logs the processed email information"
	@echo ""
	@echo "Key Features:"
	@echo "  - Automatic domain setup (bhaang.com)"
	@echo "  - Email body extraction and parsing"
	@echo "  - Highlighted sender identification"
	@echo "  - All participants listed (TO, CC, BCC)"

# Quick commands
status: ## Show deployment status
	@echo "$(BLUE)Deployment status...$(NC)"
	$(CDK) list

bootstrap: ## Bootstrap CDK environment (run once per AWS account/region)
	@echo "$(BLUE)Bootstrapping CDK environment...$(NC)"
	$(CDK) bootstrap
	@echo "$(GREEN)✓ CDK environment bootstrapped$(NC)" 