# Vibes CDK Project - Utility Targets

.PHONY: clean-layer install-layer-deps install-local-deps clean setup-ses

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

clean: ## Clean up CDK artifacts
	rm -rf cdk.out/
	rm -rf .cdk.staging/

setup-ses: ## Run SES domain setup script (after common stack deployment)
	@echo "Setting up SES domain verification and DKIM records..."
	python vibes/scripts/setup_ses_domain.py 