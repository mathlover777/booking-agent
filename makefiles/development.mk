# Vibes CDK Project - Development Environment Shortcuts

.PHONY: dev staging prod test-dev test-staging

# Environment shortcuts
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