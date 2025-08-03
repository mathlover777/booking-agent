"""
Integration test configuration - no mocking, allows real service calls.
"""
import os
import sys
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# Load environment variables for integration tests
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
load_dotenv(os.path.join(project_root, ".env.base"), override=True)
load_dotenv(os.path.join(project_root, ".env.dev"), override=True)

# Set default environment variables for integration tests
os.environ.setdefault("USER_EMAILS_TABLE_NAME", "vibes-user-emails-dev") 