"""Configuration management for the lead pipeline.

Loads settings from a .env file using python-dotenv and validates
that all required keys are present.
"""

import os
from pathlib import Path
from dotenv import load_dotenv


class Config:
    """Pipeline configuration loaded from environment variables.

    Attributes:
        DEEPSEEK_API_KEY: API key for DeepSeek.
        NETLIFY_TOKEN: Netlify personal access token.
        GMAIL_CREDENTIALS_PATH: Path to Gmail OAuth credentials JSON.
        GMAIL_SENDER_NAME: Display name for outgoing emails.
        DELAY_BETWEEN_LEADS: Seconds to wait between processing leads.
        EMAIL_TEMPLATE: Email template name to use.
    """

    def __init__(self, env_path: str = ".env") -> None:
        """Initialize config by loading from .env file.

        Args:
            env_path: Path to the .env file.
        """
        env_file = Path(env_path)
        if env_file.exists():
            load_dotenv(env_file)

        self.DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
        self.NETLIFY_TOKEN: str = os.getenv("NETLIFY_TOKEN", "")
        self.GMAIL_CREDENTIALS_PATH: str = os.getenv(
            "GMAIL_CREDENTIALS_PATH", "credentials.json"
        )
        self.GMAIL_SENDER_NAME: str = os.getenv("GMAIL_SENDER_NAME", "")
        self.DELAY_BETWEEN_LEADS: float = float(
            os.getenv("DELAY_BETWEEN_LEADS", "3.0")
        )
        self.EMAIL_TEMPLATE: str = os.getenv("EMAIL_TEMPLATE", "default")

    def validate(self) -> None:
        """Validate that all required configuration keys are set.

        Raises:
            ValueError: If any required keys are missing.
        """
        missing = []
        if not self.DEEPSEEK_API_KEY:
            missing.append("DEEPSEEK_API_KEY")
        if not self.NETLIFY_TOKEN:
            missing.append("NETLIFY_TOKEN")
        if not self.GMAIL_SENDER_NAME:
            missing.append("GMAIL_SENDER_NAME")

        if missing:
            raise ValueError(
                f"Missing required configuration keys: {', '.join(missing)}"
            )
