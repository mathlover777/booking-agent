# Logging Tests
# Test centralized logging functionality across all modules

.PHONY: test-logging
test-logging:
	@echo "🧪 Testing centralized logging functionality..."
	@source /Users/sourav/doc32/v2/.venv/bin/activate && python test_logging.py

.PHONY: test-logging-verbose
test-logging-verbose:
	@echo "🧪 Testing centralized logging with verbose output..."
	@source /Users/sourav/doc32/v2/.venv/bin/activate && LOG_LEVEL=DEBUG python test_logging.py

.PHONY: test-logging-imports
test-logging-imports:
	@echo "🔍 Testing module imports with logging..."
	@source /Users/sourav/doc32/v2/.venv/bin/activate && python -c "import sys; sys.path.insert(0, 'src'); from common_utils.log_util import get_logger; from common_utils.aws_utils import logger as aws_logger; from common_utils.email_util import logger as email_logger; from calendar_utils.calendar_util import logger as calendar_logger; from booking_agent.agent import logger as agent_logger; from email_processor import logger as processor_logger; print('✅ All modules imported successfully with logging'); print('📊 Logger names:'); print(f'   - aws_utils: {aws_logger.name}'); print(f'   - email_util: {email_logger.name}'); print(f'   - calendar_util: {calendar_logger.name}'); print(f'   - agent: {agent_logger.name}'); print(f'   - processor: {processor_logger.name}')" 