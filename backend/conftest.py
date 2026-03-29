"""
Pytest configuration for AtomsX backend.

This conftest ensures Django is set up before test collection to handle
relative imports in test files.
"""
import os
import sys
import django
from django.conf import settings as django_settings

# Add the project root to sys.path if not already there
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set up Django before any imports happen
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Initialize Django if not already done
if not django_settings.configured:
    django.setup()