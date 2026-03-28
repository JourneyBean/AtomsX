"""
Core utilities and helpers.
"""

# Avoid importing models at module level to prevent AppRegistryNotReady error
# Use: from apps.core.models import create_audit_log