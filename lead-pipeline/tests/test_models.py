"""Tests for core.models module."""

import pytest

from core.models import Lead, PipelineResult, slugify


class TestSlugify:
    """Tests for the slugify utility function."""

    def test_basic_text(self):
        assert slugify("Hello World") == "hello-world"

    def test_french_accents(self):
        assert slugify("Boulangerie Pâtisserie") == "boulangerie-patisserie"

    def test_special_characters(self):
        assert slugify("Café & Crêpes!") == "cafe-crepes"

    def test_long_string_truncated(self):
        long_text = "a-very-long-business-name-that-exceeds-the-maximum-allowed-character-limit-for-slugs"
        result = slugify(long_text, max_length=60)
        assert len(result) <= 60

    def test_leading_trailing_hyphens_removed(self):
        assert slugify("---hello---") == "hello"

    def test_multiple_spaces(self):
        assert slugify("hello    world") == "hello-world"

    def test_empty_string(self):
        assert slugify("") == ""

    def test_unicode_normalization(self):
        assert slugify("résumé") == "resume"


class TestLead:
    """Tests for the Lead dataclass."""

    def test_slug_property(self):
        lead = Lead(name="Boulangerie Du Coin", category="boulangerie", city="Paris")
        assert lead.slug == "boulangerie-du-coin-paris"

    def test_slug_with_accents(self):
        lead = Lead(name="Pâtisserie Étoilée", category="pâtisserie", city="Montréal")
        assert "patisserie" in lead.slug
        assert "montreal" in lead.slug

    def test_default_fields(self):
        lead = Lead(name="Test", category="test", city="City")
        assert lead.address == ""
        assert lead.phone == ""
        assert lead.email == ""
        assert lead.extra_info == {}


class TestPipelineResult:
    """Tests for the PipelineResult dataclass."""

    def test_to_dict_keys(self):
        lead = Lead(name="Test Biz", category="plombier", city="Lyon")
        result = PipelineResult(lead=lead)
        data = result.to_dict()

        assert "lead" in data
        assert "html_generated" in data
        assert "hosted" in data
        assert "email_sent" in data
        assert "site_url" in data
        assert "preview_path" in data
        assert "error" in data

    def test_to_dict_values(self):
        lead = Lead(name="Test Biz", category="plombier", city="Lyon")
        result = PipelineResult(
            lead=lead,
            html_generated=True,
            hosted=True,
            site_url="https://test.netlify.app",
        )
        data = result.to_dict()

        assert data["html_generated"] is True
        assert data["hosted"] is True
        assert data["email_sent"] is False
        assert data["site_url"] == "https://test.netlify.app"
        assert data["error"] is None

    def test_to_dict_lead_nested(self):
        lead = Lead(name="My Shop", category="fleuriste", city="Nice", email="a@b.com")
        result = PipelineResult(lead=lead)
        data = result.to_dict()

        assert data["lead"]["name"] == "My Shop"
        assert data["lead"]["email"] == "a@b.com"
