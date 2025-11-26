# config.py
import os
from typing import Dict, Any


class Config:
    """Application configuration with environment variable support."""

    def __init__(self):
        self.provider_name = os.getenv("PROVIDER_NAME", "openliga")

        # Rate limiting configuration
        self.rate_limit_requests = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))
        self.rate_limit_window = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

        # Exponential backoff configuration
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.base_delay = float(os.getenv("BASE_DELAY", "1.0"))
        self.max_delay = float(os.getenv("MAX_DELAY", "30.0"))
        self.backoff_multiplier = float(os.getenv("BACKOFF_MULTIPLIER", "2.0"))
        self.jitter_range = float(os.getenv("JITTER_RANGE", "0.1"))

        # Logging configuration
        self.log_level = os.getenv("LOG_LEVEL", "INFO")

        # Server configuration
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "8000"))

    def get_provider_config(self) -> Dict[str, Any]:
        """Get provider-specific configuration."""
        return {
            "rate_limit_requests": self.rate_limit_requests,
            "rate_limit_window": self.rate_limit_window,
            "max_retries": self.max_retries,
            "base_delay": self.base_delay,
            "max_delay": self.max_delay,
            "backoff_multiplier": self.backoff_multiplier,
            "jitter_range": self.jitter_range,
        }


config = Config()
