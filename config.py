"""
Project-wide configuration.
Phase 1: Only timezone and session defaults.
"""

TIMEZONE = "IST"  # Indian Standard Time — hardcoded per requirements
SESSION_TIMEOUT_MINUTES = 30
SECURE_BOOKING_URL = "https://secure.yourdomain.com/complete"

# Google Workspace / MCP Integration
GOOGLE_SPREADSHEET_ID = "1D6jshX6KhWzWbaNDq2nh_LpOiTJ6faX_FhXlHj9ramM"
GOOGLE_CALENDAR_ID = "primary"  # Connects to the main calendar of the authenticated user
