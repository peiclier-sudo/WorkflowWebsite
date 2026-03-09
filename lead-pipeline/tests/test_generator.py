"""Tests for generator.website_gen module."""

from unittest.mock import MagicMock, patch

import pytest

from core.models import Lead
from generator.website_gen import WebsiteGenerator


@pytest.fixture
def sample_lead():
    """Create a sample lead for testing."""
    return Lead(
        name="Boulangerie Du Pain",
        category="boulangerie",
        city="Paris",
        address="12 Rue de la Paix",
        phone="01 23 45 67 89",
        email="contact@dupain.fr",
        description="Artisan boulanger depuis 1990",
        opening_hours="Lun-Sam 7h-19h",
    )


@pytest.fixture
def generator():
    """Create a WebsiteGenerator with a fake API key."""
    with patch("generator.website_gen.OpenAI"):
        gen = WebsiteGenerator(api_key="fake-key")
    return gen


class TestFillTemplate:
    """Tests for _fill_template method."""

    def test_no_placeholders_remain(self, generator, sample_lead):
        content = generator._fallback_content(sample_lead)
        html = generator._fill_template(sample_lead, content)
        assert "{{" not in html
        assert "}}" not in html

    def test_business_name_in_output(self, generator, sample_lead):
        content = generator._fallback_content(sample_lead)
        html = generator._fill_template(sample_lead, content)
        assert "Boulangerie Du Pain" in html

    def test_city_in_output(self, generator, sample_lead):
        content = generator._fallback_content(sample_lead)
        html = generator._fill_template(sample_lead, content)
        assert "Paris" in html

    def test_phone_in_output(self, generator, sample_lead):
        content = generator._fallback_content(sample_lead)
        html = generator._fill_template(sample_lead, content)
        assert "0123456789" in html  # Stripped spaces


class TestFallbackContent:
    """Tests for _fallback_content method."""

    def test_returns_all_required_keys(self, generator, sample_lead):
        content = generator._fallback_content(sample_lead)
        required_keys = [
            "seo_title_suffix", "meta_description", "seo_keywords",
            "hero_title_line1", "hero_title_line2", "hero_description",
            "trust_1", "trust_2", "services_title", "services_subtitle",
            "services", "about_title", "about_text", "years_experience",
            "about_features", "testimonials_title", "testimonials",
            "hours", "form_subjects", "footer_description",
            "price_range", "og_image_keyword",
        ]
        for key in required_keys:
            assert key in content, f"Missing key: {key}"

    def test_services_is_list(self, generator, sample_lead):
        content = generator._fallback_content(sample_lead)
        assert isinstance(content["services"], list)
        assert len(content["services"]) > 0

    def test_hours_has_seven_days(self, generator, sample_lead):
        content = generator._fallback_content(sample_lead)
        assert len(content["hours"]) == 7


class TestGetContentFromDeepSeek:
    """Tests for _get_content_from_deepseek with mocked API."""

    def test_successful_api_call(self, generator, sample_lead):
        import json

        mock_content = generator._fallback_content(sample_lead)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(mock_content)

        generator.client.chat.completions.create = MagicMock(
            return_value=mock_response
        )

        result = generator._get_content_from_deepseek(sample_lead)
        assert "hero_title_line1" in result

    def test_api_failure_uses_fallback(self, generator, sample_lead):
        generator.client.chat.completions.create = MagicMock(
            side_effect=Exception("API Error")
        )

        result = generator._get_content_from_deepseek(sample_lead)
        assert "hero_title_line1" in result
        assert "services" in result

    def test_strips_markdown_fences(self, generator, sample_lead):
        import json

        mock_content = generator._fallback_content(sample_lead)
        wrapped = f"```json\n{json.dumps(mock_content)}\n```"

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = wrapped

        generator.client.chat.completions.create = MagicMock(
            return_value=mock_response
        )

        result = generator._get_content_from_deepseek(sample_lead)
        assert "hero_title_line1" in result
