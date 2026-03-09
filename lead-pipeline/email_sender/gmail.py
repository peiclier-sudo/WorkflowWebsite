"""Gmail OAuth2 email sender.

Sends personalized cold outreach emails with HTML formatting
using the Gmail API with OAuth2 authentication.
"""

import base64
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from core.models import Lead

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
TOKEN_PATH = "token.json"


class GmailSender:
    """Sends outreach emails via Gmail API with OAuth2.

    Handles the full OAuth2 flow (token refresh, initial auth)
    and provides methods to send personalized HTML emails.

    Attributes:
        credentials_path: Path to the OAuth credentials JSON file.
        service: Authenticated Gmail API service instance.
    """

    def __init__(self, credentials_path: str) -> None:
        """Initialize and authenticate with Gmail API.

        Args:
            credentials_path: Path to the Google OAuth credentials.json file.
        """
        self.credentials_path = credentials_path
        self.service = None
        self._authenticate()

    def _authenticate(self) -> None:
        """Handle the full Gmail OAuth2 authentication flow.

        Loads existing tokens, refreshes if expired, or runs the
        interactive auth flow for first-time setup.
        """
        creds = None
        token_file = Path(TOKEN_PATH)

        if token_file.exists():
            try:
                creds = Credentials.from_authorized_user_file(
                    str(token_file), SCOPES
                )
            except Exception as exc:
                logger.warning("Failed to load token.json: %s", exc)

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("Refreshed Gmail OAuth token.")
            except Exception as exc:
                logger.warning("Token refresh failed: %s", exc)
                creds = None

        if not creds or not creds.valid:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
                logger.info("Completed Gmail OAuth flow.")
            except Exception as exc:
                logger.error("Gmail authentication failed: %s", exc)
                raise

        # Save token for next run
        token_file.write_text(creds.to_json())

        self.service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail API service initialized.")

    def send(
        self,
        lead: Lead,
        site_url: str,
        sender_name: str = "",
        template: str = "default",
    ) -> bool:
        """Send a personalized outreach email to a lead.

        Args:
            lead: The business lead to contact.
            site_url: The live URL of the generated website.
            sender_name: Display name of the sender.
            template: Email template name to use.

        Returns:
            True if the email was sent successfully, False otherwise.
        """
        try:
            subject, html_body, text_body = self._render_template(
                lead, site_url, sender_name, template
            )

            message = MIMEMultipart("alternative")
            message["To"] = lead.email
            message["Subject"] = subject
            message.attach(MIMEText(text_body, "plain"))
            message.attach(MIMEText(html_body, "html"))

            raw = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode("ascii")

            self.service.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()

            logger.info("Email sent to %s (%s).", lead.name, lead.email)
            return True

        except Exception as exc:
            logger.error(
                "Failed to send email to %s (%s): %s",
                lead.name, lead.email, exc,
            )
            return False

    def _render_template(
        self,
        lead: Lead,
        site_url: str,
        sender_name: str,
        template: str,
    ) -> Tuple[str, str, str]:
        """Render the email subject, HTML body, and plain text body.

        Args:
            lead: The business lead.
            site_url: The live URL of the generated website.
            sender_name: Display name of the sender.
            template: Email template name (currently only 'default').

        Returns:
            Tuple of (subject, html_body, text_body).
        """
        subject = (
            f"J'ai cr\u00e9\u00e9 un site web pour {lead.name} "
            f"\u2014 aper\u00e7u gratuit \U0001F381"
        )

        html_body = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;font-family:Arial,Helvetica,sans-serif;background:#f4f4f7;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f7;padding:32px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;">

<!-- Header -->
<tr><td style="background:linear-gradient(135deg,#1976D2,#1565C0);padding:32px 40px;text-align:center;">
<h1 style="color:#ffffff;margin:0;font-size:22px;">Un site web pour {lead.name}</h1>
</td></tr>

<!-- Body -->
<tr><td style="padding:40px;">
<p style="font-size:16px;color:#333;line-height:1.6;margin:0 0 16px;">
Bonjour,
</p>
<p style="font-size:16px;color:#333;line-height:1.6;margin:0 0 16px;">
En parcourant <strong>Pages Jaunes</strong>, j'ai d\u00e9couvert <strong>{lead.name}</strong>
\u00e0 {lead.city}. J'ai remarqu\u00e9 que vous n'aviez pas encore de site internet
\u2014 alors j'en ai cr\u00e9\u00e9 un sp\u00e9cialement pour vous, <strong>gratuitement</strong>.
</p>

<!-- CTA Button -->
<table width="100%" cellpadding="0" cellspacing="0" style="margin:32px 0;">
<tr><td align="center">
<a href="{site_url}" target="_blank"
   style="display:inline-block;background:#1976D2;color:#ffffff;padding:16px 48px;
   font-size:18px;font-weight:bold;text-decoration:none;border-radius:50px;
   box-shadow:0 4px 12px rgba(25,118,210,0.3);">
\U0001F310 Voir votre site web
</a>
</td></tr>
</table>

<p style="font-size:16px;color:#333;line-height:1.6;margin:0 0 16px;">
Ce site est <strong>pr\u00eat \u00e0 \u00eatre mis en ligne</strong> imm\u00e9diatement.
Il est rapide, optimis\u00e9 pour mobile et r\u00e9f\u00e9renc\u00e9 sur Google.
Si vous souhaitez l'adopter, je peux le d\u00e9ployer sur votre propre nom de domaine
\u00e0 un tarif tr\u00e8s abordable.
</p>

<p style="font-size:16px;color:#333;line-height:1.6;margin:0 0 8px;">
N'h\u00e9sitez pas \u00e0 r\u00e9pondre \u00e0 cet email si vous avez des questions.
</p>

<p style="font-size:16px;color:#333;line-height:1.6;margin:24px 0 0;">
Cordialement,<br>
<strong>{sender_name or "[Votre pr\u00e9nom]"}</strong><br>
<span style="color:#666;font-size:14px;">[Votre t\u00e9l\u00e9phone]</span>
</p>
</td></tr>

<!-- Footer -->
<tr><td style="background:#f8f9fa;padding:24px 40px;text-align:center;border-top:1px solid #eee;">
<p style="font-size:12px;color:#999;margin:0;line-height:1.5;">
Cet email vous a \u00e9t\u00e9 envoy\u00e9 dans le cadre d'une d\u00e9marche B2B l\u00e9gitime.<br>
<a href="mailto:?subject=D\u00e9sinscription" style="color:#999;text-decoration:underline;">
Se d\u00e9sinscrire</a> &bull;
Conform\u00e9ment au RGPD, vous pouvez exercer vos droits en r\u00e9pondant \u00e0 cet email.
</p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""

        text_body = (
            f"Bonjour,\n\n"
            f"En parcourant Pages Jaunes, j'ai d\u00e9couvert {lead.name} \u00e0 {lead.city}. "
            f"J'ai remarqu\u00e9 que vous n'aviez pas encore de site internet, "
            f"alors j'en ai cr\u00e9\u00e9 un sp\u00e9cialement pour vous, gratuitement.\n\n"
            f"Voir votre site : {site_url}\n\n"
            f"Ce site est pr\u00eat \u00e0 \u00eatre mis en ligne imm\u00e9diatement. "
            f"Il est rapide, optimis\u00e9 pour mobile et r\u00e9f\u00e9renc\u00e9 sur Google.\n\n"
            f"N'h\u00e9sitez pas \u00e0 r\u00e9pondre \u00e0 cet email si vous avez des questions.\n\n"
            f"Cordialement,\n"
            f"{sender_name or '[Votre pr\u00e9nom]'}\n"
            f"[Votre t\u00e9l\u00e9phone]\n\n"
            f"---\n"
            f"Pour se d\u00e9sinscrire, r\u00e9pondez avec 'D\u00e9sinscription'."
        )

        return subject, html_body, text_body
