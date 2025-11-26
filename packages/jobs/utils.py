"""
Utility functions for job processing.
"""

from datetime import datetime


def get_current_processing_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")