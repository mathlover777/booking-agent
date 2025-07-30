# Vibes CDK Project - User Email API Tests

.PHONY: test-get-user-email test-update-user-email test-jwt-authorizer test-email-availability

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