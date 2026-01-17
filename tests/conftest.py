"""
Root conftest.py for the tests directory.
Registers pytest markers and provides common test configuration.
"""
import pytest

# Register custom markers to avoid warnings
pytest_plugins = []

# Register markers
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    ) 