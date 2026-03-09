"""
WEBSITE BUILDER — Generates personalized websites for each lead.

HOW IT WORKS:
  1. Reads leads from data/leads.csv
  2. For each lead, asks DeepSeek AI to generate website content:
     - Tagline, services list, about text, color scheme
  3. Fills in the HTML template with that content
  4. Saves each website as data/sites/{business_name}/index.html

KEY CONCEPT — One Template, Many Sites:
  We use ONE HTML template (template.html) for every lead.
  DeepSeek only generates the TEXT CONTENT (services, tagline, etc.).
  This keeps websites consistent and professional while being personalized.

WHY DEEPSEEK (not ChatGPT)?
  DeepSeek is much cheaper (~$0.001 per lead vs $0.02 for GPT-4).
  For generating short text content, it works just as well.
"""

import csv
import json
import os
import re

import requests

# Go up one folder to find config.py
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


# ── The prompt that tells DeepSeek what to generate ──
# This is the "master prompt" — it defines exactly what content
# DeepSeek must produce for each lead's website.

MASTER_PROMPT = """Tu es un rédacteur web expert pour les artisans et professionnels du bâtiment en France.

Je te donne les informations d'un professionnel. Génère le contenu pour son site web vitrine.

Informations du professionnel:
- Nom: {name}
- Métier/Catégorie: {category}
- Ville: {city}
- Adresse: {address}
- Téléphone: {phone}

Réponds UNIQUEMENT avec un JSON valide (pas de texte avant/après) avec cette structure exacte:
{{
  "tagline": "Une phrase d'accroche courte et professionnelle (max 10 mots)",
  "primary_color": "code hex couleur principale (adaptée au métier, ex: bleu pour plombier, orange pour electricien)",
  "primary_dark": "version plus foncée de la couleur principale",
  "accent_color": "couleur d'accent contrastante pour les boutons",
  "services": [
    {{"title": "Nom du service 1", "description": "Description courte du service (1-2 phrases)"}},
    {{"title": "Nom du service 2", "description": "Description courte"}},
    {{"title": "Nom du service 3", "description": "Description courte"}}
  ],
  "about_paragraphs": [
    "Premier paragraphe de présentation (2-3 phrases, professionnel et rassurant)",
    "Deuxième paragraphe sur l'expérience et la zone d'intervention"
  ]
}}

IMPORTANT:
- Adapte les services au métier spécifique (plombier → dépannage, installation, etc.)
- Utilise un ton professionnel mais chaleureux
- Mentionne la ville dans les textes
- Les couleurs doivent être professionnelles et adaptées au métier
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
    Sends the lead info to DeepSeek and gets back website content.

    KEY CONCEPT — API Call:
      We send a POST request to DeepSeek's API with our prompt.
      DeepSeek returns JSON with the website content.
      This is the same concept as ChatGPT's API, just cheaper.
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
                "temperature": 0.7,
            },
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()

        # DeepSeek sometimes wraps JSON in ```json ... ``` markdown
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'\s*```$', '', content)

        return json.loads(content)

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("   ❌ Invalid DeepSeek API key! Check config.py")
        else:
            print(f"   ❌ DeepSeek API error: {e}")
        return None
    except json.JSONDecodeError:
        print(f"   ❌ DeepSeek returned invalid JSON")
        print(f"      Raw response: {content[:200]}")
        return None
    except Exception as e:
        print(f"   ❌ Error calling DeepSeek: {e}")
        return None


def build_services_html(services):
    """
    Converts the services list from DeepSeek into HTML cards.

    Input:  [{"title": "Dépannage", "description": "Intervention rapide..."}]
    Output: <div class="service-card"><h3>Dépannage</h3><p>Intervention...</p></div>
    """
    html = ""
    for svc in services:
        title = svc.get("title", "Service")
        desc = svc.get("description", "")
        html += f'            <div class="service-card">\n'
        html += f'                <h3>{title}</h3>\n'
        html += f'                <p>{desc}</p>\n'
        html += f'            </div>\n'
    return html


def build_about_html(paragraphs):
    """Converts about paragraphs into HTML <p> tags."""
    return "\n".join(f"            <p>{p}</p>" for p in paragraphs)


def fill_template(template_str, lead, ai_content):
    """
    Replaces all {{PLACEHOLDER}} markers in the template with real content.

    This is the core of the system: ONE template + personalized text = unique site.
    """
    phone_raw = lead.get("phone", "").replace(" ", "")
    phone_display = lead.get("phone", "Non renseigné")

    replacements = {
        "{{BUSINESS_NAME}}": lead["name"],
        "{{TAGLINE}}": ai_content.get("tagline", "Votre artisan de confiance"),
        "{{PRIMARY_COLOR}}": ai_content.get("primary_color", "#2563eb"),
        "{{PRIMARY_DARK}}": ai_content.get("primary_dark", "#1e40af"),
        "{{ACCENT_COLOR}}": ai_content.get("accent_color", "#f59e0b"),
        "{{PHONE}}": phone_raw,
        "{{PHONE_DISPLAY}}": phone_display,
        "{{ADDRESS}}": lead.get("address", ""),
        "{{CITY}}": lead.get("city", ""),
        "{{SERVICES_HTML}}": build_services_html(ai_content.get("services", [])),
        "{{ABOUT_HTML}}": build_about_html(ai_content.get("about_paragraphs", [])),
    }

    html = template_str
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

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
    Main function — generates a website for each lead.

    FLOW:
      1. Load leads from CSV
      2. Load HTML template
      3. For each lead:
         a. Ask DeepSeek to generate content
         b. Fill template with content
         c. Save as HTML file
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

    # Load template
    template_path = os.path.join(os.path.dirname(__file__), "template.html")
    with open(template_path, "r", encoding="utf-8") as f:
        template_str = f.read()

    # Create output directory
    os.makedirs(config.SITES_DIR, exist_ok=True)

    built_sites = []

    for i, lead in enumerate(leads, 1):
        name = lead["name"]
        print(f"\n[{i}/{len(leads)}] {name}")

        # Ask DeepSeek to generate content
        print(f"   🤖 Asking DeepSeek for content...")
        ai_content = ask_deepseek(lead)

        if not ai_content:
            print(f"   ⏭️  Skipping (AI error)")
            continue

        print(f"   ✅ Got: \"{ai_content.get('tagline', '?')}\"")

        # Fill template
        html = fill_template(template_str, lead, ai_content)

        # Save to data/sites/{slug}/index.html
        slug = slugify(name)
        site_dir = os.path.join(config.SITES_DIR, slug)
        os.makedirs(site_dir, exist_ok=True)

        output_path = os.path.join(site_dir, "index.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"   💾 Saved to: {site_dir}/index.html")

        lead["site_folder"] = slug
        lead["site_path"] = output_path
        built_sites.append(lead)

    # Summary
    print(f"\n{'=' * 50}")
    print(f"✅ Built {len(built_sites)}/{len(leads)} websites")
    print(f"📁 Sites saved in: {config.SITES_DIR}")

    return built_sites


if __name__ == "__main__":
    run()
