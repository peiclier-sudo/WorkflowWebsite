"""Website generator using DeepSeek API.

Generates personalized HTML landing pages for business leads by combining
AI-generated content with a master HTML template.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote

from openai import OpenAI

from core.models import Lead

logger = logging.getLogger(__name__)

# --- Sector mappings ---

SCHEMA_TYPES: Dict[str, str] = {
    "boulangerie": "Bakery",
    "restaurant": "Restaurant",
    "plombier": "Plumber",
    "electricien": "Electrician",
    "coiffeur": "HairSalon",
    "garage": "AutoRepair",
    "dentiste": "Dentist",
    "médecin": "Physician",
    "pharmacie": "Pharmacy",
    "fleuriste": "Florist",
    "pâtisserie": "Bakery",
    "pizzeria": "Restaurant",
    "avocat": "Attorney",
    "comptable": "AccountingService",
    "default": "LocalBusiness",
}

SECTOR_PALETTES: Dict[str, Dict[str, str]] = {
    "boulangerie": {
        "primary": "#C8813D", "primary_dark": "#A66A2E", "accent": "#FFF3E0",
        "bg": "#FFFDF9", "surface": "#FFFFFF", "text": "#2D1B0E",
        "text_muted": "#7A6352", "border": "#F0E6D8", "hero_bg": "linear-gradient(135deg, #FFF8F0, #FFF3E0)",
    },
    "restaurant": {
        "primary": "#C62828", "primary_dark": "#8E0000", "accent": "#FFEBEE",
        "bg": "#FFFAFA", "surface": "#FFFFFF", "text": "#1A1A1A",
        "text_muted": "#666666", "border": "#F0E0E0", "hero_bg": "linear-gradient(135deg, #FFF5F5, #FFEBEE)",
    },
    "plombier": {
        "primary": "#1565C0", "primary_dark": "#0D47A1", "accent": "#E3F2FD",
        "bg": "#F8FBFF", "surface": "#FFFFFF", "text": "#1A1A2E",
        "text_muted": "#5A6578", "border": "#E0E8F0", "hero_bg": "linear-gradient(135deg, #F0F7FF, #E3F2FD)",
    },
    "electricien": {
        "primary": "#F9A825", "primary_dark": "#F57F17", "accent": "#FFF8E1",
        "bg": "#FFFDF5", "surface": "#FFFFFF", "text": "#1A1A1A",
        "text_muted": "#666666", "border": "#F0EAD6", "hero_bg": "linear-gradient(135deg, #FFFDE7, #FFF8E1)",
    },
    "coiffeur": {
        "primary": "#AD1457", "primary_dark": "#880E4F", "accent": "#FCE4EC",
        "bg": "#FFFAFB", "surface": "#FFFFFF", "text": "#1A1A1A",
        "text_muted": "#777777", "border": "#F0E0E8", "hero_bg": "linear-gradient(135deg, #FFF0F5, #FCE4EC)",
    },
    "garage": {
        "primary": "#37474F", "primary_dark": "#263238", "accent": "#ECEFF1",
        "bg": "#FAFBFC", "surface": "#FFFFFF", "text": "#1A1A1A",
        "text_muted": "#607D8B", "border": "#E0E4E8", "hero_bg": "linear-gradient(135deg, #F5F7FA, #ECEFF1)",
    },
    "dentiste": {
        "primary": "#00ACC1", "primary_dark": "#00838F", "accent": "#E0F7FA",
        "bg": "#F8FDFE", "surface": "#FFFFFF", "text": "#1A1A2E",
        "text_muted": "#5A7A8A", "border": "#D8EEF2", "hero_bg": "linear-gradient(135deg, #F0FAFE, #E0F7FA)",
    },
    "médecin": {
        "primary": "#2E7D32", "primary_dark": "#1B5E20", "accent": "#E8F5E9",
        "bg": "#F8FDF8", "surface": "#FFFFFF", "text": "#1A1A1A",
        "text_muted": "#5A7A5E", "border": "#D8F0DA", "hero_bg": "linear-gradient(135deg, #F0FAF0, #E8F5E9)",
    },
    "pharmacie": {
        "primary": "#00897B", "primary_dark": "#00695C", "accent": "#E0F2F1",
        "bg": "#F8FDFB", "surface": "#FFFFFF", "text": "#1A1A1A",
        "text_muted": "#5A7A75", "border": "#D0E8E5", "hero_bg": "linear-gradient(135deg, #F0FBF8, #E0F2F1)",
    },
    "fleuriste": {
        "primary": "#7B1FA2", "primary_dark": "#4A0072", "accent": "#F3E5F5",
        "bg": "#FDFAFF", "surface": "#FFFFFF", "text": "#1A1A1A",
        "text_muted": "#7A6688", "border": "#E8D8F0", "hero_bg": "linear-gradient(135deg, #FAF0FF, #F3E5F5)",
    },
    "pâtisserie": {
        "primary": "#D84315", "primary_dark": "#BF360C", "accent": "#FBE9E7",
        "bg": "#FFFAF8", "surface": "#FFFFFF", "text": "#2D1B0E",
        "text_muted": "#7A6352", "border": "#F0E2D8", "hero_bg": "linear-gradient(135deg, #FFF5F0, #FBE9E7)",
    },
    "pizzeria": {
        "primary": "#E65100", "primary_dark": "#BF360C", "accent": "#FFF3E0",
        "bg": "#FFFCF5", "surface": "#FFFFFF", "text": "#1A1A1A",
        "text_muted": "#7A6A52", "border": "#F0E6D0", "hero_bg": "linear-gradient(135deg, #FFF8ED, #FFF3E0)",
    },
    "avocat": {
        "primary": "#1A237E", "primary_dark": "#0D1257", "accent": "#E8EAF6",
        "bg": "#F8F9FF", "surface": "#FFFFFF", "text": "#1A1A2E",
        "text_muted": "#5A5E7A", "border": "#D8DCF0", "hero_bg": "linear-gradient(135deg, #F0F2FF, #E8EAF6)",
    },
    "comptable": {
        "primary": "#004D40", "primary_dark": "#00332B", "accent": "#E0F2F1",
        "bg": "#F8FCFB", "surface": "#FFFFFF", "text": "#1A1A1A",
        "text_muted": "#5A7A70", "border": "#D0E8E0", "hero_bg": "linear-gradient(135deg, #F0FAF8, #E0F2F1)",
    },
    "default": {
        "primary": "#1976D2", "primary_dark": "#0D47A1", "accent": "#E3F2FD",
        "bg": "#F8FBFF", "surface": "#FFFFFF", "text": "#1A1A1A",
        "text_muted": "#666666", "border": "#E0E8F0", "hero_bg": "linear-gradient(135deg, #F0F7FF, #E3F2FD)",
    },
}

SECTOR_FONTS: Dict[str, Dict[str, str]] = {
    "boulangerie": {"display": "'Playfair Display', serif", "body": "'Lato', sans-serif", "url": "https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Lato:wght@300;400;600;700&display=swap"},
    "restaurant": {"display": "'Playfair Display', serif", "body": "'Source Sans 3', sans-serif", "url": "https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Source+Sans+3:wght@300;400;600;700&display=swap"},
    "plombier": {"display": "'Montserrat', sans-serif", "body": "'Open Sans', sans-serif", "url": "https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&family=Open+Sans:wght@300;400;600;700&display=swap"},
    "electricien": {"display": "'Montserrat', sans-serif", "body": "'Roboto', sans-serif", "url": "https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&family=Roboto:wght@300;400;500;700&display=swap"},
    "coiffeur": {"display": "'Cormorant Garamond', serif", "body": "'Nunito', sans-serif", "url": "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700&family=Nunito:wght@300;400;600;700&display=swap"},
    "garage": {"display": "'Oswald', sans-serif", "body": "'Roboto', sans-serif", "url": "https://fonts.googleapis.com/css2?family=Oswald:wght@400;600;700&family=Roboto:wght@300;400;500;700&display=swap"},
    "dentiste": {"display": "'Raleway', sans-serif", "body": "'Open Sans', sans-serif", "url": "https://fonts.googleapis.com/css2?family=Raleway:wght@400;600;700&family=Open+Sans:wght@300;400;600;700&display=swap"},
    "médecin": {"display": "'Raleway', sans-serif", "body": "'Nunito', sans-serif", "url": "https://fonts.googleapis.com/css2?family=Raleway:wght@400;600;700&family=Nunito:wght@300;400;600;700&display=swap"},
    "pharmacie": {"display": "'Poppins', sans-serif", "body": "'Nunito', sans-serif", "url": "https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&family=Nunito:wght@300;400;600;700&display=swap"},
    "fleuriste": {"display": "'Cormorant Garamond', serif", "body": "'Lato', sans-serif", "url": "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700&family=Lato:wght@300;400;600;700&display=swap"},
    "pâtisserie": {"display": "'Playfair Display', serif", "body": "'Lato', sans-serif", "url": "https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Lato:wght@300;400;600;700&display=swap"},
    "pizzeria": {"display": "'Fredoka', sans-serif", "body": "'Nunito', sans-serif", "url": "https://fonts.googleapis.com/css2?family=Fredoka:wght@400;600;700&family=Nunito:wght@300;400;600;700&display=swap"},
    "avocat": {"display": "'Cormorant Garamond', serif", "body": "'Source Sans 3', sans-serif", "url": "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700&family=Source+Sans+3:wght@300;400;600;700&display=swap"},
    "comptable": {"display": "'Montserrat', sans-serif", "body": "'Source Sans 3', sans-serif", "url": "https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&family=Source+Sans+3:wght@300;400;600;700&display=swap"},
    "default": {"display": "'Inter', sans-serif", "body": "'Inter', sans-serif", "url": "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap"},
}

SECTOR_EMOJIS: Dict[str, str] = {
    "boulangerie": "\U0001F956",
    "restaurant": "\U0001F37D\uFE0F",
    "plombier": "\U0001F527",
    "electricien": "\u26A1",
    "coiffeur": "\u2702\uFE0F",
    "garage": "\U0001F697",
    "dentiste": "\U0001F9B7",
    "médecin": "\U0001FA7A",
    "pharmacie": "\U0001F48A",
    "fleuriste": "\U0001F490",
    "pâtisserie": "\U0001F370",
    "pizzeria": "\U0001F355",
    "avocat": "\u2696\uFE0F",
    "comptable": "\U0001F4CA",
    "default": "\U0001F3E2",
}


def _get_mapping(mapping: dict, category: str) -> Any:
    """Get value from a sector mapping dict with fallback to default.

    Args:
        mapping: The sector mapping dictionary.
        category: The business category key.

    Returns:
        The mapped value or the default.
    """
    cat = category.lower().strip()
    return mapping.get(cat, mapping["default"])


class WebsiteGenerator:
    """Generates personalized HTML landing pages using DeepSeek API.

    Uses the DeepSeek chat model to produce marketing content that is
    injected into a master HTML template.

    Attributes:
        client: OpenAI-compatible client configured for DeepSeek.
        template: The master HTML template string.
    """

    def __init__(self, api_key: str) -> None:
        """Initialize the generator with DeepSeek API key.

        Args:
            api_key: DeepSeek API key.
        """
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
        template_path = Path(__file__).parent / "template.html"
        self.template = template_path.read_text(encoding="utf-8")

    def generate(self, lead: Lead) -> str:
        """Generate a complete HTML page for a lead.

        Args:
            lead: The business lead to generate a page for.

        Returns:
            Complete HTML string ready to deploy.
        """
        content = self._get_content_from_deepseek(lead)
        return self._fill_template(lead, content)

    def _get_content_from_deepseek(self, lead: Lead) -> Dict[str, Any]:
        """Call DeepSeek API to generate marketing content for a lead.

        Args:
            lead: The business lead.

        Returns:
            Dictionary of generated content fields.
        """
        prompt = (
            f"Tu es un expert en marketing digital pour les PME fran\u00e7aises. "
            f"G\u00e9n\u00e8re du contenu marketing pour le site web de cette entreprise:\n\n"
            f"Nom: {lead.name}\n"
            f"Cat\u00e9gorie: {lead.category}\n"
            f"Ville: {lead.city}\n"
            f"Adresse: {lead.address}\n"
            f"T\u00e9l\u00e9phone: {lead.phone}\n"
            f"Description: {lead.description}\n"
            f"Horaires: {lead.opening_hours}\n\n"
            f"R\u00e9ponds UNIQUEMENT avec un objet JSON valide (pas de markdown, pas de ```). "
            f"Le JSON doit contenir exactement ces cl\u00e9s:\n"
            f'{{"seo_title_suffix": "...", "meta_description": "140-160 chars avec ville et secteur", '
            f'"seo_keywords": "kw1, kw2, kw3", '
            f'"hero_title_line1": "...", "hero_title_line2": "tagline accrocheuse", '
            f'"hero_description": "1-2 phrases de pitch", '
            f'"trust_1": "signal de confiance court", "trust_2": "signal de confiance court", '
            f'"services_title": "...", "services_subtitle": "...", '
            f'"services": [{{"icon": "emoji", "title": "...", "description": "2-3 phrases"}}], '
            f'"about_title": "...", "about_text": "2-3 phrases", '
            f'"years_experience": "12", '
            f'"about_features": [{{"icon": "emoji", "title": "...", "text": "court"}}], '
            f'"testimonials_title": "...", '
            f'"testimonials": [{{"stars": 5, "text": "...", "author": "Pr\u00e9nom N., Ville"}}], '
            f'"hours": [{{"day": "Lundi", "hours": "09h00 \u2013 18h00"}}], '
            f'"form_subjects": ["Devis", "Rendez-vous", "Renseignements", "Autre"], '
            f'"footer_description": "...", '
            f'"price_range": "\u20ac\u20ac", '
            f'"og_image_keyword": "english keyword for unsplash"}}'
        )

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=3000,
            )
            raw = response.choices[0].message.content.strip()

            # Strip markdown fences if present
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

            return json.loads(raw)
        except Exception as exc:
            logger.warning(
                "DeepSeek API call failed for '%s': %s. Using fallback content.",
                lead.name, exc,
            )
            return self._fallback_content(lead)

    def _fallback_content(self, lead: Lead) -> Dict[str, Any]:
        """Generate fallback content when the API call fails.

        Args:
            lead: The business lead.

        Returns:
            Dictionary with all required content fields.
        """
        cat = lead.category.capitalize()
        return {
            "seo_title_suffix": f"{cat} \u00e0 {lead.city}",
            "meta_description": (
                f"{lead.name}, votre {lead.category} de confiance \u00e0 {lead.city}. "
                f"D\u00e9couvrez nos services et contactez-nous d\u00e8s aujourd'hui."
            ),
            "seo_keywords": f"{lead.category}, {lead.city}, {lead.name}, professionnel",
            "hero_title_line1": f"Bienvenue chez {lead.name}",
            "hero_title_line2": f"Votre {lead.category} de confiance",
            "hero_description": (
                f"D\u00e9couvrez {lead.name}, votre {lead.category} "
                f"au c\u0153ur de {lead.city}. Qualit\u00e9, savoir-faire et proximit\u00e9."
            ),
            "trust_1": "Service professionnel",
            "trust_2": "Satisfaction garantie",
            "services_title": "Nos Services",
            "services_subtitle": f"D\u00e9couvrez ce que {lead.name} peut faire pour vous.",
            "services": [
                {"icon": "\u2B50", "title": "Service Premium", "description": "Un service de qualit\u00e9 adapt\u00e9 \u00e0 vos besoins."},
                {"icon": "\U0001F91D", "title": "Conseil Personnalis\u00e9", "description": "Un accompagnement sur mesure pour chaque client."},
                {"icon": "\u23F0", "title": "R\u00e9activit\u00e9", "description": "Une prise en charge rapide de vos demandes."},
            ],
            "about_title": f"\u00c0 propos de {lead.name}",
            "about_text": (
                f"{lead.name} est un(e) {lead.category} reconnu(e) \u00e0 {lead.city}. "
                f"Notre engagement : vous offrir le meilleur service."
            ),
            "years_experience": "10+",
            "about_features": [
                {"icon": "\u2705", "title": "Expertise", "text": "Des ann\u00e9es d'exp\u00e9rience"},
                {"icon": "\U0001F4CD", "title": "Proximit\u00e9", "text": f"Au c\u0153ur de {lead.city}"},
                {"icon": "\U0001F4AF", "title": "Qualit\u00e9", "text": "Satisfaction client"},
            ],
            "testimonials_title": "Ce que disent nos clients",
            "testimonials": [
                {"stars": 5, "text": "Excellent service, je recommande vivement !", "author": f"Marie L., {lead.city}"},
                {"stars": 5, "text": "Professionnels et \u00e0 l'\u00e9coute. Tr\u00e8s satisfait.", "author": f"Pierre D., {lead.city}"},
                {"stars": 4, "text": "Tr\u00e8s bon rapport qualit\u00e9-prix.", "author": f"Sophie M., {lead.city}"},
            ],
            "hours": [
                {"day": "Lundi", "hours": "09h00 \u2013 18h00"},
                {"day": "Mardi", "hours": "09h00 \u2013 18h00"},
                {"day": "Mercredi", "hours": "09h00 \u2013 18h00"},
                {"day": "Jeudi", "hours": "09h00 \u2013 18h00"},
                {"day": "Vendredi", "hours": "09h00 \u2013 18h00"},
                {"day": "Samedi", "hours": "09h00 \u2013 12h00"},
                {"day": "Dimanche", "hours": "Ferm\u00e9"},
            ],
            "form_subjects": ["Devis", "Rendez-vous", "Renseignements", "Autre"],
            "footer_description": (
                f"{lead.name} \u2014 votre {lead.category} de confiance \u00e0 {lead.city}."
            ),
            "price_range": "\u20ac\u20ac",
            "og_image_keyword": lead.category,
        }

    def _fill_template(self, lead: Lead, content: Dict[str, Any]) -> str:
        """Fill the HTML template with lead data and generated content.

        Args:
            lead: The business lead.
            content: Dictionary of AI-generated content.

        Returns:
            Complete HTML string with all placeholders replaced.
        """
        palette = _get_mapping(SECTOR_PALETTES, lead.category)
        fonts = _get_mapping(SECTOR_FONTS, lead.category)
        emoji = _get_mapping(SECTOR_EMOJIS, lead.category)
        schema = _get_mapping(SCHEMA_TYPES, lead.category)

        # Build HTML blocks
        services_html = self._build_services_html(content.get("services", []))
        features_html = self._build_features_html(content.get("about_features", []))
        testimonials_html = self._build_testimonials_html(content.get("testimonials", []))
        hours_html = self._build_hours_html(content.get("hours", []))
        subjects_html = self._build_subjects_html(content.get("form_subjects", []))
        hours_schema = self._build_hours_schema(content.get("hours", []))

        phone_display = lead.phone if lead.phone else "Nous appeler"
        phone_raw = lead.phone.replace(" ", "").replace(".", "") if lead.phone else ""
        og_keyword = content.get("og_image_keyword", lead.category)
        site_url = f"https://{lead.slug}.netlify.app"

        from datetime import datetime
        current_year = str(datetime.now().year)

        replacements = {
            "{{BUSINESS_NAME}}": lead.name,
            "{{CATEGORY_LABEL}}": lead.category.capitalize(),
            "{{CITY}}": lead.city,
            "{{PHONE}}": phone_raw,
            "{{PHONE_DISPLAY}}": phone_display,
            "{{EMAIL}}": lead.email,
            "{{ADDRESS_STREET}}": lead.address,
            "{{ADDRESS_ENCODED}}": quote(f"{lead.address}, {lead.city}, France"),
            "{{SITE_URL}}": site_url,
            "{{CURRENT_YEAR}}": current_year,
            "{{EMOJI_ICON}}": emoji,
            "{{SCHEMA_TYPE}}": schema,
            "{{PRICE_RANGE}}": content.get("price_range", "\u20ac\u20ac"),
            "{{FORMSPREE_ENDPOINT}}": "xpzvqlgk",
            "{{SEO_TITLE_SUFFIX}}": content.get("seo_title_suffix", ""),
            "{{META_DESCRIPTION}}": content.get("meta_description", ""),
            "{{SEO_KEYWORDS}}": content.get("seo_keywords", ""),
            "{{OG_IMAGE_URL}}": f"https://source.unsplash.com/1200x630/?{quote(og_keyword)}",
            "{{ABOUT_IMAGE_URL}}": f"https://source.unsplash.com/600x450/?{quote(og_keyword)}",
            "{{GOOGLE_FONTS_URL}}": fonts["url"],
            "{{FONT_DISPLAY}}": fonts["display"],
            "{{FONT_BODY}}": fonts["body"],
            "{{COLOR_PRIMARY}}": palette["primary"],
            "{{COLOR_PRIMARY_DARK}}": palette["primary_dark"],
            "{{COLOR_ACCENT}}": palette["accent"],
            "{{COLOR_BG}}": palette["bg"],
            "{{COLOR_SURFACE}}": palette["surface"],
            "{{COLOR_TEXT}}": palette["text"],
            "{{COLOR_TEXT_MUTED}}": palette["text_muted"],
            "{{COLOR_BORDER}}": palette["border"],
            "{{HERO_BACKGROUND}}": palette["hero_bg"],
            "{{HERO_TEXT_COLOR}}": palette["text"],
            "{{HERO_DESC_COLOR}}": palette["text_muted"],
            "{{HERO_DECO_BG}}": palette["primary"],
            "{{HERO_TITLE_LINE1}}": content.get("hero_title_line1", ""),
            "{{HERO_TITLE_LINE2}}": content.get("hero_title_line2", ""),
            "{{HERO_DESCRIPTION}}": content.get("hero_description", ""),
            "{{TRUST_1}}": content.get("trust_1", ""),
            "{{TRUST_2}}": content.get("trust_2", ""),
            "{{SERVICES_TITLE}}": content.get("services_title", ""),
            "{{SERVICES_SUBTITLE}}": content.get("services_subtitle", ""),
            "{{SERVICES_CARDS_HTML}}": services_html,
            "{{ABOUT_TITLE}}": content.get("about_title", ""),
            "{{ABOUT_TEXT}}": content.get("about_text", ""),
            "{{YEARS_EXPERIENCE}}": str(content.get("years_experience", "10+")),
            "{{ABOUT_FEATURES_HTML}}": features_html,
            "{{TESTIMONIALS_TITLE}}": content.get("testimonials_title", ""),
            "{{TESTIMONIALS_HTML}}": testimonials_html,
            "{{HOURS_TABLE_HTML}}": hours_html,
            "{{FORM_SUBJECTS_OPTIONS}}": subjects_html,
            "{{FOOTER_DESCRIPTION}}": content.get("footer_description", ""),
            "{{OPENING_HOURS_SCHEMA}}": hours_schema,
        }

        html = self.template
        for placeholder, value in replacements.items():
            html = html.replace(placeholder, value)

        return html

    def _build_services_html(self, services: list) -> str:
        """Build HTML for service cards.

        Args:
            services: List of service dicts with icon, title, description.

        Returns:
            HTML string for all service cards.
        """
        cards = []
        for svc in services:
            cards.append(
                f'<div class="service-card reveal">'
                f'<div class="service-icon">{svc.get("icon", "\u2B50")}</div>'
                f'<h3>{svc.get("title", "")}</h3>'
                f'<p>{svc.get("description", "")}</p>'
                f'</div>'
            )
        return "\n".join(cards)

    def _build_features_html(self, features: list) -> str:
        """Build HTML for about section feature list items.

        Args:
            features: List of feature dicts with icon, title, text.

        Returns:
            HTML string for feature list items.
        """
        items = []
        for feat in features:
            items.append(
                f'<li class="feature-item">'
                f'<span class="feature-icon">{feat.get("icon", "\u2705")}</span>'
                f'<div><h4>{feat.get("title", "")}</h4>'
                f'<p>{feat.get("text", "")}</p></div>'
                f'</li>'
            )
        return "\n".join(items)

    def _build_testimonials_html(self, testimonials: list) -> str:
        """Build HTML for testimonial cards.

        Args:
            testimonials: List of testimonial dicts with stars, text, author.

        Returns:
            HTML string for testimonial cards.
        """
        cards = []
        for t in testimonials:
            stars_count = t.get("stars", 5)
            stars = "\u2605" * stars_count + "\u2606" * (5 - stars_count)
            cards.append(
                f'<div class="testimonial-card reveal">'
                f'<div class="stars">{stars}</div>'
                f'<p>\u201c{t.get("text", "")}\u201d</p>'
                f'<div class="testimonial-author">{t.get("author", "")}</div>'
                f'</div>'
            )
        return "\n".join(cards)

    def _build_hours_html(self, hours: list) -> str:
        """Build HTML table rows for opening hours.

        Args:
            hours: List of dicts with day and hours keys.

        Returns:
            HTML string for table rows.
        """
        rows = []
        for h in hours:
            rows.append(
                f'<tr><th>{h.get("day", "")}</th>'
                f'<td>{h.get("hours", "")}</td></tr>'
            )
        return "\n".join(rows)

    def _build_subjects_html(self, subjects: list) -> str:
        """Build HTML option elements for form subject dropdown.

        Args:
            subjects: List of subject strings.

        Returns:
            HTML string for option elements.
        """
        options = []
        for s in subjects:
            options.append(f'<option value="{s}">{s}</option>')
        return "\n".join(options)

    def _build_hours_schema(self, hours: list) -> str:
        """Build JSON-LD openingHoursSpecification from hours list.

        Args:
            hours: List of dicts with day and hours keys.

        Returns:
            JSON string for schema.org openingHoursSpecification array items.
        """
        day_map = {
            "Lundi": "Monday", "Mardi": "Tuesday", "Mercredi": "Wednesday",
            "Jeudi": "Thursday", "Vendredi": "Friday", "Samedi": "Saturday",
            "Dimanche": "Sunday",
        }
        specs = []
        for h in hours:
            day_en = day_map.get(h.get("day", ""), "Monday")
            hours_str = h.get("hours", "")
            if "ferm" in hours_str.lower():
                continue
            # Parse hours like "09h00 – 18h00"
            match = re.search(r"(\d{2})h(\d{2})\s*[\u2013\-]\s*(\d{2})h(\d{2})", hours_str)
            if match:
                opens = f"{match.group(1)}:{match.group(2)}"
                closes = f"{match.group(3)}:{match.group(4)}"
                specs.append(
                    f'{{"@type":"OpeningHoursSpecification",'
                    f'"dayOfWeek":"{day_en}",'
                    f'"opens":"{opens}","closes":"{closes}"}}'
                )
        return ",".join(specs)
