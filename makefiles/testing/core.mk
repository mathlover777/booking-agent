# Vibes CDK Project - Core Testing Targets

.PHONY: test-email test-calendar test-booking-agent test-real-email

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