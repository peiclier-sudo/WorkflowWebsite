"""Netlify deployment module.

Handles creating sites and deploying HTML files to Netlify
using their REST API.
"""

import hashlib
import logging
import time
from typing import Tuple

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://api.netlify.com/api/v1"


class NetlifyHosting:
    """Manages Netlify site creation and HTML deployment.

    Attributes:
        token: Netlify personal access token.
        headers: Default request headers with authorization.
    """

    def __init__(self, token: str) -> None:
        """Initialize with a Netlify API token.

        Args:
            token: Netlify personal access token.
        """
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def deploy(self, html: str, subdomain: str) -> str:
        """Deploy an HTML page to Netlify and return the live URL.

        Args:
            html: The complete HTML content to deploy.
            subdomain: Desired subdomain name for the site.

        Returns:
            The live URL of the deployed site.

        Raises:
            requests.HTTPError: If the API request fails.
        """
        site_id, site_url = self._get_or_create_site(subdomain)
        deploy_id = self._deploy_file(site_id, html)
        self._wait_for_deploy(deploy_id)
        logger.info("Site deployed: %s", site_url)
        return site_url

    def _get_or_create_site(self, subdomain: str) -> Tuple[str, str]:
        """Create a new Netlify site or handle name conflicts.

        Args:
            subdomain: Desired subdomain name.

        Returns:
            Tuple of (site_id, site_url).

        Raises:
            requests.HTTPError: If the API request fails unexpectedly.
        """
        try:
            resp = requests.post(
                f"{API_BASE}/sites",
                headers=self.headers,
                json={"name": subdomain},
                timeout=30,
            )
            if resp.status_code == 422:
                # Name taken — append hash suffix
                suffix = hashlib.md5(subdomain.encode()).hexdigest()[:6]
                new_name = f"{subdomain}-{suffix}"
                logger.info(
                    "Subdomain '%s' taken, trying '%s'.", subdomain, new_name
                )
                resp = requests.post(
                    f"{API_BASE}/sites",
                    headers=self.headers,
                    json={"name": new_name},
                    timeout=30,
                )
                resp.raise_for_status()
                subdomain = new_name
            else:
                resp.raise_for_status()

            data = resp.json()
            site_id = data["id"]
            site_url = f"https://{subdomain}.netlify.app"
            logger.info("Site created: %s (id=%s)", site_url, site_id)
            return site_id, site_url

        except requests.RequestException as exc:
            logger.error("Failed to create Netlify site '%s': %s", subdomain, exc)
            raise

    def _deploy_file(self, site_id: str, html: str) -> str:
        """Deploy an HTML file to an existing Netlify site.

        Args:
            site_id: The Netlify site ID.
            html: The HTML content to deploy.

        Returns:
            The deploy ID.

        Raises:
            requests.HTTPError: If the API request fails.
        """
        html_bytes = html.encode("utf-8")
        digest = hashlib.sha1(html_bytes).hexdigest()

        try:
            # Create deploy with file manifest
            resp = requests.post(
                f"{API_BASE}/sites/{site_id}/deploys",
                headers=self.headers,
                json={"files": {"/index.html": digest}},
                timeout=30,
            )
            resp.raise_for_status()
            deploy_data = resp.json()
            deploy_id = deploy_data["id"]

            # Upload file if required
            required = deploy_data.get("required", [])
            if digest in required:
                upload_resp = requests.put(
                    f"{API_BASE}/deploys/{deploy_id}/files/index.html",
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/octet-stream",
                    },
                    data=html_bytes,
                    timeout=60,
                )
                upload_resp.raise_for_status()
                logger.debug("Uploaded index.html to deploy %s.", deploy_id)

            return deploy_id

        except requests.RequestException as exc:
            logger.error("Failed to deploy files to site %s: %s", site_id, exc)
            raise

    def _wait_for_deploy(self, deploy_id: str, max_wait: int = 60) -> None:
        """Wait for a Netlify deploy to reach 'ready' state.

        Args:
            deploy_id: The deploy ID to monitor.
            max_wait: Maximum seconds to wait before giving up.
        """
        elapsed = 0
        interval = 3
        while elapsed < max_wait:
            try:
                resp = requests.get(
                    f"{API_BASE}/deploys/{deploy_id}",
                    headers=self.headers,
                    timeout=15,
                )
                resp.raise_for_status()
                state = resp.json().get("state", "unknown")

                if state == "ready":
                    logger.info("Deploy %s is ready.", deploy_id)
                    return
                if state == "error":
                    logger.error("Deploy %s failed with error state.", deploy_id)
                    return

                logger.debug("Deploy %s state: %s", deploy_id, state)
            except requests.RequestException as exc:
                logger.warning("Error checking deploy status: %s", exc)

            time.sleep(interval)
            elapsed += interval

        logger.warning(
            "Deploy %s did not reach ready state within %ds.", deploy_id, max_wait
        )

    def list_sites(self) -> list:
        """List all Netlify sites for the authenticated account.

        Returns:
            List of site dictionaries.
        """
        try:
            resp = requests.get(
                f"{API_BASE}/sites",
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.error("Failed to list Netlify sites: %s", exc)
            return []

    def delete_site(self, site_id: str) -> None:
        """Delete a Netlify site.

        Args:
            site_id: The site ID to delete.
        """
        try:
            resp = requests.delete(
                f"{API_BASE}/sites/{site_id}",
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
            logger.info("Deleted site %s.", site_id)
        except requests.RequestException as exc:
            logger.error("Failed to delete site %s: %s", site_id, exc)
