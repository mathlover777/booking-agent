# Vibes CDK Project - Email Processor End-to-End Tests

.PHONY: test-email-processor-e2e test-email-processor-e2e-all test-email-processor-case-1-share-availability test-email-processor-case-2-book-event test-email-processor-case-3-domain-filter test-email-processor-case-4-real-email

# ---------------------------------------------------------------------------
# Email processor end-to-end tests
# ---------------------------------------------------------------------------

test-email-processor-e2e: ## Test email processor end-to-end pipeline (all tests)
	@echo "Testing email processor end-to-end pipeline (all tests)..."
	cd src && python test_email_processor_e2e.py

test-email-processor-e2e-all: test-email-processor-case-1-share-availability test-email-processor-case-2-book-event test-email-processor-case-3-domain-filter test-email-processor-case-4-real-email ## Run all email processor tests in sequence

# ---------------------------------------------------------------------------
# Individual test cases for email processor pipeline ------------------------
# ---------------------------------------------------------------------------

test-email-processor-case-1-share-availability: ## Test Case 1: Share availability (full email processor pipeline)
	@echo "Testing Case 1: Share availability (full email processor pipeline)..."
	@echo "This test uses real AWS services (S3, DynamoDB) but mocks SES to prevent email sending."
	@echo "Calendar events may be created during testing."
	cd src && python -c "from test_email_processor_e2e import test_case_1_share_availability_e2e; test_case_1_share_availability_e2e()"

test-email-processor-case-2-book-event: ## Test Case 2: Book event (full email processor pipeline)
	@echo "Testing Case 2: Book event (full email processor pipeline)..."
	@echo "This test uses real AWS services (S3, DynamoDB) but mocks SES to prevent email sending."
	@echo "Calendar events may be created during testing."
	cd src && python -c "from test_email_processor_e2e import test_case_2_book_event_e2e; test_case_2_book_event_e2e()"

test-email-processor-case-3-domain-filter: ## Test Case 3: Domain filtering (email from same domain should be skipped)
	@echo "Testing Case 3: Domain filtering (email from same domain should be skipped)..."
	@echo "This test uses real AWS services (S3, DynamoDB) but mocks SES to prevent email sending."
	@echo "No agent processing or email sending should occur."
	cd src && python -c "from test_email_processor_e2e import test_case_3_domain_filter_e2e; test_case_3_domain_filter_e2e()"

test-email-processor-case-4-real-email: ## Test Case 4: Process real email from sample/real1 (investigate agent email mapping)
	@echo "Testing Case 4: Process real email from sample/real1..."
	@echo "This test processes the actual email that was responded by bookdev@bhaang.com instead of test.dev@bhaang.com"
	@echo "This test uses real AWS services (S3, DynamoDB) but mocks SES to prevent email sending."
	@echo "Will investigate why the wrong agent email was used."
	cd src && python -c "from test_email_processor_e2e import test_case_4_real_email_processing; test_case_4_real_email_processing()" 