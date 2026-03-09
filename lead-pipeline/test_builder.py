"""
Quick test — sends ONE fake lead to DeepSeek to verify the builder works.
Run: python test_builder.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from _2_website_builder import builder

# Fake lead with enriched data
fake_lead = {
    "name": "Martin Plomberie",
    "category": "plombier",
    "city": "Toulouse",
    "address": "12 rue des Carmes, 31000 Toulouse",
    "phone": "05 61 23 45 67",
    "description": "Entreprise familiale spécialisée dans la plomberie depuis 3 générations",
    "specialties": "Dépannage urgent, Installation chauffe-eau, Rénovation salle de bain, Détection de fuites",
    "hours": "Lun-Ven 8h-19h, Sam 9h-12h",
    "zone": "Toulouse et agglomération (30km)",
    "year_created": "2003",
    "review_score": "4.7",
    "review_count": "38",
}

print("🧪 Test: sending fake lead to DeepSeek...")
print(f"   Lead: {fake_lead['name']} ({fake_lead['category']}, {fake_lead['city']})")
print()

html = builder.ask_deepseek(fake_lead)

if html:
    print(f"\n✅ SUCCESS! DeepSeek returned {len(html)} characters of HTML")
    print(f"   Sections: {html.lower().count('<section')} <section> tags")
    print(f"   Has <form>: {'Yes' if '<form' in html.lower() else 'No'}")
    print(f"   Has mentions légales: {'Yes' if 'mention' in html.lower() else 'No'}")
    print(f"   Has phone link: {'Yes' if 'tel:' in html.lower() else 'No'}")

    # Save it so you can preview in browser
    os.makedirs("data/sites/_test", exist_ok=True)
    with open("data/sites/_test/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n💾 Saved to: data/sites/_test/index.html")
    print(f"   Open this file in your browser to preview!")
else:
    print("\n❌ FAILED — DeepSeek returned nothing. Check your API key in config.py")
