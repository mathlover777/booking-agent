# Vibes CDK Project - Deployment Targets

.PHONY: bootstrap deploy-common deploy-processor deploy-all destroy-processor destroy-common destroy-all diff-processor diff-common synth

bootstrap: ## Bootstrap CDK in the current account/region
	$(CDK_BOOTSTRAP) --profile $(AWS_PROFILE)

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