"""
WEBSITE BUILDER — Generates unique, fully-designed websites for each lead.

HOW IT WORKS:
  1. Reads leads from data/leads.csv
  2. For each lead, asks DeepSeek AI to generate a COMPLETE HTML page
     with its own unique design, colors, layout, and CSS
  3. Saves each website as data/sites/{business_name}/index.html

KEY CONCEPT — AI-Generated Design:
  Instead of filling a fixed template, DeepSeek creates the FULL page
  each time: HTML structure, CSS styling, colors, fonts, layout.
  Every business gets a unique-looking website.

  We show DeepSeek a reference example so it understands the quality
  level we expect, but it creates its OWN design each time.

WHY DEEPSEEK (not ChatGPT)?
  DeepSeek is much cheaper (~$0.01 per lead vs $0.10 for GPT-4).
  For generating HTML/CSS, it works great.
"""

import csv
import os
import re
import time

import requests

# Go up one folder to find config.py
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


# ── The master prompt ──
# DeepSeek generates the ENTIRE HTML page with unique styling.
# The reference template shows the quality level we expect.

MASTER_PROMPT = """Tu es un développeur web expert spécialisé dans la création de sites vitrines modernes et professionnels pour les artisans en France.

MISSION: Génère un site web vitrine COMPLET (HTML + CSS intégré) pour ce professionnel.

INFORMATIONS DU PROFESSIONNEL:
- Nom de l'entreprise: {name}
- Métier: {category}
- Ville: {city}
- Adresse: {address}
- Téléphone: {phone}

INSTRUCTIONS DE DESIGN:
1. Crée un design UNIQUE à chaque fois — varie les couleurs, les dispositions, les styles
2. Le CSS doit être intégré dans une balise <style> (pas de fichier externe)
3. Le site doit être responsive (mobile-friendly)
4. Utilise des couleurs professionnelles adaptées au métier
5. Inclus TOUTES ces sections:
   - Hero/header avec le nom, accroche, et bouton d'appel (lien tel:)
   - Section services (3-4 services adaptés au métier)
   - Section à propos (texte professionnel et rassurant)
   - FORMULAIRE DE CONTACT avec champs: Nom, Email, Téléphone, Message, et bouton "Envoyer"
     (utilise un <form> avec action="https://formsubmit.co/{phone}" method="POST" ou action="#" si pas d'email)
     Style le formulaire de façon élégante et intégrée au design
   - Section contact avec téléphone, adresse, zone d'intervention
   - MENTIONS LÉGALES en bas de page (section ou modal):
     Inclure: nom de l'entreprise, adresse, téléphone, mention "Site réalisé à titre informatif",
     "Conformément à la loi Informatique et Libertés du 6 janvier 1978 modifiée,
     vous disposez d'un droit d'accès, de modification et de suppression des données vous concernant."
   - Footer avec copyright et lien vers mentions légales
6. Varie le style entre les sites:
   - Parfois des cards arrondies, parfois des bordures strictes
   - Parfois un gradient, parfois une couleur unie
   - Parfois des ombres douces, parfois un style flat
   - Varie la taille des polices, les espacements, la mise en page
   - Utilise des combinaisons de couleurs différentes à chaque fois
7. Le téléphone doit être cliquable (lien tel:)
8. Ajoute des émojis pertinents pour le métier dans les titres de services
9. Texte en français, ton professionnel mais chaleureux
10. Mentionne la ville dans les textes
11. Le formulaire doit avoir une validation HTML5 (required, type="email", etc.)

IMPORTANT: Réponds UNIQUEMENT avec le code HTML complet. Pas de texte avant, pas de texte après.
Commence directement par <!DOCTYPE html> et termine par </html>.
"""


def load_leads():
    """Reads leads from the CSV file."""
    if not os.path.exists(config.LEADS_CSV):
        print(f"❌ No leads file found at {config.LEADS_CSV}")
        print("   Run 'python main.py scrape' first!")
        return []

    leads = []
    with open(config.LEADS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            leads.append(row)

    return leads


def ask_deepseek(lead):
    """
    Sends the lead info to DeepSeek and gets back a COMPLETE HTML page.

    KEY CONCEPT — Full Page Generation:
      Unlike a template approach, DeepSeek generates the entire HTML+CSS.
      Each site gets a unique design, layout, and color scheme.
      The prompt guides the AI to create professional tradesman sites.

    Returns the full HTML string, or None on error.
    """
    prompt = MASTER_PROMPT.format(
        name=lead["name"],
        category=lead.get("category", "artisan"),
        city=lead.get("city", ""),
        address=lead.get("address", ""),
        phone=lead.get("phone", ""),
    )

    try:
        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 1.0,  # Higher = more creative/varied designs
                "max_tokens": 6000,
            },
            timeout=60,
        )
        response.raise_for_status()

        data = response.json()
        html_content = data["choices"][0]["message"]["content"].strip()

        # DeepSeek sometimes wraps HTML in ```html ... ``` markdown blocks
        html_content = re.sub(r'^```html\s*', '', html_content)
        html_content = re.sub(r'\s*```$', '', html_content)

        # Validate: must start with <!DOCTYPE or <html
        if not html_content.lower().startswith(("<!doctype", "<html")):
            print(f"   ⚠ Response doesn't look like HTML, trying to extract...")
            # Try to extract HTML from the response
            match = re.search(r'(<!DOCTYPE html.*</html>)', html_content, re.DOTALL | re.IGNORECASE)
            if match:
                html_content = match.group(1)
            else:
                print(f"   ❌ Could not extract HTML from response")
                return None

        return html_content

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("   ❌ Invalid DeepSeek API key! Check config.py")
        else:
            print(f"   ❌ DeepSeek API error: {e}")
        return None
    except Exception as e:
        print(f"   ❌ Error calling DeepSeek: {e}")
        return None


def inject_google_analytics(html):
    """
    Injects Google Analytics tracking code into the <head> of the HTML.

    We do this AFTER generation (not in the prompt) because:
      - The GA ID comes from config, not from DeepSeek
      - We want the exact correct snippet, not AI-generated JS
      - If no GA ID is configured, we simply skip it
    """
    ga_id = getattr(config, "GOOGLE_ANALYTICS_ID", "")
    if not ga_id:
        return html

    ga_snippet = f"""
    <!-- Google Analytics -->
    <script async src="https://www.googletagmanager.com/gtag/js?id={ga_id}"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', '{ga_id}');
    </script>"""

    # Insert right after <head>
    if "<head>" in html:
        html = html.replace("<head>", f"<head>{ga_snippet}", 1)
    elif "<HEAD>" in html:
        html = html.replace("<HEAD>", f"<HEAD>{ga_snippet}", 1)

    return html


def slugify(name):
    """
    Converts a business name into a safe folder name.

    Example: "Jean-Pierre's Plomberie" → "jean-pierres-plomberie"
    """
    slug = name.lower().strip()
    slug = re.sub(r"[''`]", "", slug)
    slug = re.sub(r"[^a-z0-9àâäéèêëïîôùûüÿçæœ-]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "site"


def run():
    """
    Main function — generates a unique website for each lead.

    FLOW:
      1. Load leads from CSV
      2. For each lead, ask DeepSeek to generate a full HTML page
      3. Save each page as data/sites/{slug}/index.html
    """
    print("=" * 50)
    print("🏗️  WEBSITE BUILDER")
    print("=" * 50)

    # Check API key
    if not config.DEEPSEEK_API_KEY:
        print("\n❌ DeepSeek API key not set!")
        print("   1. Go to: https://platform.deepseek.com")
        print("   2. Create an account and get an API key")
        print("   3. Add it to config.py: DEEPSEEK_API_KEY = 'your-key-here'")
        return []

    # Load leads
    leads = load_leads()
    if not leads:
        return []

    print(f"\n📋 Found {len(leads)} leads in {config.LEADS_CSV}")

    # Create output directory
    os.makedirs(config.SITES_DIR, exist_ok=True)

    built_sites = []

    for i, lead in enumerate(leads, 1):
        name = lead["name"]
        print(f"\n[{i}/{len(leads)}] {name}")

        # Ask DeepSeek to generate the full website
        print(f"   🤖 Generating unique website design...")
        html = ask_deepseek(lead)

        if not html:
            print(f"   ⏭️  Skipping (AI error)")
            continue

        # Inject Google Analytics tracking (if configured)
        html = inject_google_analytics(html)

        # Quick stats on what was generated
        css_count = html.lower().count("style")
        section_count = html.lower().count("<section")
        print(f"   ✅ Generated ({len(html)} chars, {section_count} sections)")

        # Save to data/sites/{slug}/index.html
        slug = slugify(name)
        site_dir = os.path.join(config.SITES_DIR, slug)
        os.makedirs(site_dir, exist_ok=True)

        output_path = os.path.join(site_dir, "index.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"   💾 Saved: {os.path.join('data', 'sites', slug, 'index.html')}")

        lead["site_folder"] = slug
        lead["site_path"] = output_path
        built_sites.append(lead)

        # Small delay between API calls to be respectful
        if i < len(leads):
            time.sleep(1)

    # Summary
    print(f"\n{'=' * 50}")
    print(f"✅ Built {len(built_sites)}/{len(leads)} websites")
    print(f"📁 Sites saved in: {config.SITES_DIR}")
    if built_sites:
        print(f"\n💡 Open any index.html in your browser to preview!")

    return built_sites


if __name__ == "__main__":
    run()
