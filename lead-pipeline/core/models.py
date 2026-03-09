"""Data models for the lead pipeline.

Defines Lead and PipelineResult dataclasses used throughout the application.
"""

import re
import unicodedata
from dataclasses import dataclass, field, asdict
from typing import Optional


def slugify(text: str, max_length: int = 60) -> str:
    """Convert text to a URL-safe slug.

    Args:
        text: The input string to slugify.
        max_length: Maximum length of the resulting slug.

    Returns:
        A URL-safe, lowercase slug string.
    """
    # Normalize unicode characters (remove accents)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    # Lowercase and replace non-alphanumeric with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    # Strip leading/trailing hyphens
    text = text.strip("-")
    # Truncate to max_length without cutting mid-word
    if len(text) > max_length:
        text = text[:max_length].rsplit("-", 1)[0]
    return text


@dataclass
class Lead:
    """Represents a business lead scraped from Pages Jaunes.

    Attributes:
        name: Business name.
        category: Business category (e.g. 'boulangerie').
        city: City where the business is located.
        address: Street address.
        phone: Phone number.
        email: Email address.
        description: Business description.
        opening_hours: Opening hours as raw text.
        extra_info: Additional metadata.
    """

    name: str
    category: str
    city: str
    address: str = ""
    phone: str = ""
    email: str = ""
    description: str = ""
    opening_hours: str = ""
    extra_info: dict = field(default_factory=dict)

    @property
    def slug(self) -> str:
        """URL-safe identifier built from name and city."""
        return slugify(f"{self.name} {self.city}")


@dataclass
class PipelineResult:
    """Tracks the outcome of processing a single lead through the pipeline.

    Attributes:
        lead: The lead that was processed.
        html_generated: Whether HTML was successfully generated.
        hosted: Whether the site was deployed to Netlify.
        email_sent: Whether the outreach email was sent.
        site_url: The live Netlify URL if deployed.
        preview_path: Local preview file path if in dry-run mode.
        error: Error message if something failed.
    """

    lead: Lead
    html_generated: bool = False
    hosted: bool = False
    email_sent: bool = False
    site_url: Optional[str] = None
    preview_path: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize the result to a JSON-compatible dictionary.

        Returns:
            Dictionary with all fields serialized.
        """
        data = asdict(self)
        return data
