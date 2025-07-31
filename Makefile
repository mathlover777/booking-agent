# Vibes CDK Project Makefile
# Modular structure with included makefiles

# Include all modular makefiles
include makefiles/common.mk
include makefiles/deployment.mk
include makefiles/development.mk
include makefiles/utils.mk
include makefiles/testing/core.mk
include makefiles/testing/calendar-tests.mk
include makefiles/testing/api-tests.mk
include makefiles/testing/agent-executor-tests.mk
include makefiles/testing/agent-tests.mk
include makefiles/testing/email-processor-tests.mk

# Default target
.DEFAULT_GOAL := help 