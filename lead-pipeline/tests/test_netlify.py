"""Tests for hosting.netlify module."""

from unittest.mock import MagicMock, patch

import pytest

from hosting.netlify import NetlifyHosting


@pytest.fixture
def netlify():
    """Create a NetlifyHosting instance with a fake token."""
    return NetlifyHosting(token="fake-token")


class TestGetOrCreateSite:
    """Tests for _get_or_create_site method."""

    @patch("hosting.netlify.requests.post")
    def test_create_site_success(self, mock_post, netlify):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "site-123",
            "name": "my-site",
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        site_id, site_url = netlify._get_or_create_site("my-site")

        assert site_id == "site-123"
        assert site_url == "https://my-site.netlify.app"
        mock_post.assert_called_once()

    @patch("hosting.netlify.requests.post")
    def test_create_site_422_retry(self, mock_post, netlify):
        # First call returns 422, second succeeds
        first_response = MagicMock()
        first_response.status_code = 422

        second_response = MagicMock()
        second_response.status_code = 200
        second_response.json.return_value = {
            "id": "site-456",
            "name": "my-site-abc123",
        }
        second_response.raise_for_status = MagicMock()

        mock_post.side_effect = [first_response, second_response]

        site_id, site_url = netlify._get_or_create_site("my-site")

        assert site_id == "site-456"
        assert "my-site-" in site_url
        assert mock_post.call_count == 2


class TestDeploy:
    """Tests for deploy method end-to-end with mocked requests."""

    @patch("hosting.netlify.requests.get")
    @patch("hosting.netlify.requests.put")
    @patch("hosting.netlify.requests.post")
    def test_deploy_full_flow(self, mock_post, mock_put, mock_get, netlify):
        # Mock site creation
        create_resp = MagicMock()
        create_resp.status_code = 200
        create_resp.json.return_value = {"id": "site-789", "name": "test-site"}
        create_resp.raise_for_status = MagicMock()

        # Mock deploy creation
        deploy_resp = MagicMock()
        deploy_resp.status_code = 200
        deploy_resp.json.return_value = {
            "id": "deploy-001",
            "required": ["abc123"],  # Will trigger upload
        }
        deploy_resp.raise_for_status = MagicMock()

        mock_post.side_effect = [create_resp, deploy_resp]

        # Mock file upload
        upload_resp = MagicMock()
        upload_resp.raise_for_status = MagicMock()
        mock_put.return_value = upload_resp

        # Mock deploy status check
        status_resp = MagicMock()
        status_resp.json.return_value = {"state": "ready"}
        status_resp.raise_for_status = MagicMock()
        mock_get.return_value = status_resp

        html = "<html><body>Hello</body></html>"
        url = netlify.deploy(html, "test-site")

        assert "test-site" in url
        assert "netlify.app" in url
