#!/usr/bin/env python3
"""
export_to_web.py — Convertit la sortie du pagesjaunes-scraper vers data.json
pour le site annuaire-pagesjaunes.

Usage:
    # Depuis une base SQLite
    python export_to_web.py --db output/businesses.db --out ../annuaire-pagesjaunes/data.json

    # Depuis un fichier JSON Lines
    python export_to_web.py --jsonl output/businesses.jsonl --out ../annuaire-pagesjaunes/data.json

    # Depuis un CSV
    python export_to_web.py --csv output/businesses.csv --out ../annuaire-pagesjaunes/data.json

    # Avec filtres
    python export_to_web.py --db output/businesses.db --min-rating 3.0 --limit 500 --out data.json
"""

import argparse
import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path

# ── MAPPING DES CATÉGORIES ──────────────────────────────────────────────────
# Mappe les noms de catégories Pages Jaunes vers les clés du site annuaire.
# Ajoutez vos propres correspondances selon les résultats du scraper.

CATEGORY_MAP: dict[str, str] = {
    # Restauration
    "restaurant": "restaurant",
    "restaurants": "restaurant",
    "brasserie": "restaurant",
    "café": "restaurant",
    "cafe": "restaurant",
    "bistro": "restaurant",
    "bistrot": "restaurant",
    "pizzeria": "restaurant",
    "traiteur": "restaurant",
    "fast-food": "restaurant",
    "crêperie": "restaurant",
    "creperie": "restaurant",
    "bar": "restaurant",
    # Plomberie
    "plombier": "plomberie",
    "plomberie": "plomberie",
    "chauffagiste": "plomberie",
    "plomberie chauffage": "plomberie",
    "chauffage": "plomberie",
    "sanitaire": "plomberie",
    # Électricité
    "électricien": "electricite",
    "electricien": "electricite",
    "electricite": "electricite",
    "électricité": "electricite",
    "electricite generale": "electricite",
    "électricité générale": "electricite",
    # Coiffure
    "coiffeur": "coiffeur",
    "coiffure": "coiffeur",
    "salon de coiffure": "coiffeur",
    "coiffeurs": "coiffeur",
    "barbier": "coiffeur",
    "barbiers": "coiffeur",
    # Boulangerie
    "boulangerie": "boulangerie",
    "boulanger": "boulangerie",
    "boulangerie pâtisserie": "boulangerie",
    "boulangerie patisserie": "boulangerie",
    "pâtisserie": "boulangerie",
    "patisserie": "boulangerie",
    # Garage / Auto
    "garage": "garage",
    "auto": "garage",
    "automobile": "garage",
    "carrosserie": "garage",
    "concessionnaire": "garage",
    "mécanique": "garage",
    "mecanique": "garage",
    "pneus": "garage",
    "réparation auto": "garage",
    "reparation auto": "garage",
    # Avocats
    "avocat": "avocat",
    "avocats": "avocat",
    "cabinet d'avocats": "avocat",
    "cabinet avocats": "avocat",
    "avocat au barreau": "avocat",
    "juriste": "avocat",
    # Jardinage
    "jardinier": "jardinier",
    "jardiniers": "jardinier",
    "jardinage": "jardinier",
    "paysagiste": "jardinier",
    "entretien jardins": "jardinier",
    "espaces verts": "jardinier",
    "élagage": "jardinier",
    "elagage": "jardinier",
    # Spa & Beauté
    "spa": "spa",
    "institut de beauté": "spa",
    "institut de beaute": "spa",
    "bien-être": "spa",
    "bien etre": "spa",
    "massage": "spa",
    "esthétique": "spa",
    "esthetique": "spa",
    "soin": "spa",
}

# Description anglaise par défaut selon la catégorie
CAT_EN_SUFFIX: dict[str, str] = {
    "restaurant": "offers a warm dining experience with quality cuisine and seasonal produce.",
    "plomberie": "provides reliable plumbing and heating services for homes and businesses.",
    "electricite": "delivers certified electrical installation and repair services.",
    "coiffeur": "is a modern salon offering cuts, colouring and styling services.",
    "boulangerie": "bakes fresh artisan breads and pastries daily.",
    "garage": "provides complete automotive services including repairs and servicing.",
    "avocat": "is a law firm specialising in civil, business and family law.",
    "jardinier": "offers professional garden maintenance and landscaping services.",
    "spa": "is a relaxing spa offering massages and wellness treatments.",
}

# Jours de la semaine (ISO : lundi = 0)
DAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def normalize_category(raw: str) -> str:
    """Mappe un nom de catégorie brut vers la clé du site."""
    if not raw:
        return "autre"
    lower = raw.lower().strip()
    # Correspondance exacte
    if lower in CATEGORY_MAP:
        return CATEGORY_MAP[lower]
    # Correspondance partielle (la clé est contenue dans la catégorie brute)
    for key, mapped in CATEGORY_MAP.items():
        if key in lower:
            return mapped
    return lower  # fallback : utiliser tel quel


def parse_time_str(t: str) -> tuple[int, int] | None:
    """Parse 'HHhMM', 'HH:MM' ou 'HHMM' et retourne (heure, minute)."""
    t = t.strip().replace("h", ":").replace("H", ":")
    try:
        if ":" in t:
            parts = t.split(":")
            return int(parts[0]), int(parts[1]) if len(parts) > 1 and parts[1] else 0
        if len(t) == 4:
            return int(t[:2]), int(t[2:])
        if len(t) <= 2:
            return int(t), 0
    except ValueError:
        pass
    return None


def format_opening_hours(opening_hours) -> tuple[str, bool]:
    """
    Convertit opening_hours (dict ou str JSON) en (texte_horaires, est_ouvert).

    Le scraper stocke opening_hours comme un dict structuré par jour :
    {"lundi": "09:00-18:00", "mardi": "09:00-18:00", ...}
    ou comme une string JSON de ce dict.
    """
    if not opening_hours:
        return "Horaires non disponibles", False

    # Désérialiser si nécessaire
    if isinstance(opening_hours, str):
        try:
            opening_hours = json.loads(opening_hours)
        except (json.JSONDecodeError, TypeError):
            return str(opening_hours)[:60], False

    if not isinstance(opening_hours, dict):
        return "Horaires non disponibles", False

    now = datetime.now()
    today_key = DAYS_FR[now.weekday()]

    today_val = opening_hours.get(today_key) or opening_hours.get(today_key.capitalize())
    if not today_val or str(today_val).lower() in ("fermé", "ferme", "closed", ""):
        return "Fermé aujourd'hui", False

    hours_str = str(today_val).strip()

    # Essayer de déterminer si l'établissement est ouvert maintenant
    is_open = False
    try:
        sep = "–" if "–" in hours_str else "-"
        parts = hours_str.split(sep)
        if len(parts) == 2:
            open_t = parse_time_str(parts[0])
            close_t = parse_time_str(parts[1])
            if open_t and close_t:
                open_minutes = open_t[0] * 60 + open_t[1]
                close_minutes = close_t[0] * 60 + close_t[1]
                now_minutes = now.hour * 60 + now.minute
                is_open = open_minutes <= now_minutes < close_minutes
                close_hhmm = f"{close_t[0]}h{close_t[1]:02d}" if close_t[1] else f"{close_t[0]}h"
                open_hhmm = f"{open_t[0]}h{open_t[1]:02d}" if open_t[1] else f"{open_t[0]}h"
                if is_open:
                    return f"Ouvert jusqu'à {close_hhmm}", True
                else:
                    return f"Ouvre à {open_hhmm}", False
    except Exception:
        pass

    return hours_str[:60], is_open


def format_address(item: dict) -> str:
    """Reconstruit une adresse lisible depuis les champs séparés."""
    parts = []
    if item.get("address_street"):
        parts.append(str(item["address_street"]).strip())
    postal = str(item.get("address_postal_code") or "").strip()
    city = str(item.get("address_city") or "").strip()
    if postal and city:
        parts.append(f"{postal} {city}")
    elif city:
        parts.append(city)
    elif postal:
        parts.append(postal)
    return " ".join(parts) if parts else ""


def build_english_desc(name: str, category: str, desc_fr: str) -> str:
    """Génère une description anglaise basique (sans API de traduction)."""
    suffix = CAT_EN_SUFFIX.get(category, "is a professional service provider.")
    return f"{name} {suffix}"


def convert_item(item: dict, index: int) -> dict:
    """Convertit un enregistrement du scraper vers le format attendu par le site."""
    cat = normalize_category(item.get("category") or "")

    # Horaires
    hours_str, is_open = format_opening_hours(item.get("opening_hours"))

    # Si le scraper a déjà calculé is_open_now, on le préfère
    raw_open = item.get("is_open_now")
    if raw_open is not None:
        is_open = bool(raw_open) if not isinstance(raw_open, str) else raw_open.lower() in ("true", "1", "yes")

    desc_fr = (item.get("description") or "").strip()
    name = (item.get("name") or "Professionnel").strip()

    # Note : rating_distribution est préservé pour usage futur
    try:
        rating = round(float(item.get("rating") or 0), 1)
    except (TypeError, ValueError):
        rating = 0.0

    try:
        reviews = int(item.get("reviews_count") or 0)
    except (TypeError, ValueError):
        reviews = 0

    return {
        "id": index + 1,
        "listing_id": str(item.get("listing_id") or ""),
        "name": name,
        "cat": cat,
        "city": str(item.get("address_city") or item.get("search_location") or "").strip(),
        "rating": rating,
        "reviews": reviews,
        "phone": str(item.get("phone") or "").strip(),
        "addr": format_address(item),
        "hours": hours_str,
        "open": is_open,
        "desc_fr": desc_fr,
        "desc_en": build_english_desc(name, cat, desc_fr),
        # Champs enrichis (disponibles dans le modal et pour usage futur)
        "website": str(item.get("website") or "").strip(),
        "email": str(item.get("email") or "").strip(),
        "lat": item.get("latitude"),
        "lng": item.get("longitude"),
        "subcategories": item.get("subcategories") or [],
        "social": {
            "facebook": str(item.get("social_facebook") or ""),
            "twitter": str(item.get("social_twitter") or ""),
            "instagram": str(item.get("social_instagram") or ""),
            "linkedin": str(item.get("social_linkedin") or ""),
        },
        "scraped_at": str(item.get("scraped_at") or ""),
        "source_url": str(item.get("source_url") or ""),
    }


# ── LOADERS ─────────────────────────────────────────────────────────────────

def load_from_sqlite(db_path: str) -> list[dict]:
    """Charge tous les enregistrements depuis la base SQLite du scraper."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Le scraper utilise la table 'businesses' (vérifiez avec: sqlite3 <db> .tables)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    table = "businesses" if "businesses" in tables else tables[0] if tables else None
    if not table:
        raise RuntimeError(f"Aucune table trouvée dans {db_path}")
    cursor = conn.execute(f"SELECT * FROM {table}")  # noqa: S608
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    print(f"✓ {len(rows)} enregistrements chargés depuis SQLite ({table})")
    return rows


def load_from_jsonl(jsonl_path: str) -> list[dict]:
    """Charge tous les enregistrements depuis un fichier JSON Lines."""
    rows = []
    with open(jsonl_path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  Avertissement : ligne {lineno} ignorée ({e})")
    print(f"✓ {len(rows)} enregistrements chargés depuis JSONL")
    return rows


def load_from_csv(csv_path: str) -> list[dict]:
    """Charge tous les enregistrements depuis un fichier CSV."""
    rows = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    print(f"✓ {len(rows)} enregistrements chargés depuis CSV")
    return rows


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exporte les données du pagesjaunes-scraper vers data.json pour le site annuaire.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--db", metavar="FICHIER.db", help="Base SQLite du scraper")
    src.add_argument("--jsonl", metavar="FICHIER.jsonl", help="Fichier JSON Lines")
    src.add_argument("--csv", metavar="FICHIER.csv", help="Fichier CSV")

    parser.add_argument(
        "--out", default="data.json", metavar="CHEMIN",
        help="Chemin de sortie pour data.json (défaut : data.json)",
    )
    parser.add_argument(
        "--min-rating", type=float, default=0.0, metavar="NOTE",
        help="Note minimale pour inclure un professionnel (défaut : 0)",
    )
    parser.add_argument(
        "--limit", type=int, default=None, metavar="N",
        help="Nombre maximum de professionnels à exporter",
    )
    parser.add_argument(
        "--city", metavar="VILLE",
        help="Filtrer par ville (ex: Paris)",
    )
    parser.add_argument(
        "--category", metavar="CAT",
        help="Filtrer par catégorie (ex: restaurant)",
    )

    args = parser.parse_args()

    # Chargement
    if args.db:
        raw_items = load_from_sqlite(args.db)
    elif args.jsonl:
        raw_items = load_from_jsonl(args.jsonl)
    else:
        raw_items = load_from_csv(args.csv)

    # Conversion et filtres
    converted = []
    skipped = 0
    for item in raw_items:
        try:
            rating = float(item.get("rating") or 0)
            if rating < args.min_rating:
                skipped += 1
                continue

            city = str(item.get("address_city") or item.get("search_location") or "").strip()
            if args.city and city.lower() != args.city.lower():
                skipped += 1
                continue

            converted_item = convert_item(item, len(converted))

            if args.category and converted_item["cat"] != args.category.lower():
                skipped += 1
                continue

            converted.append(converted_item)
        except Exception as e:
            print(f"  Avertissement : enregistrement ignoré ({e})")
            skipped += 1

    if args.limit:
        converted = converted[: args.limit]

    if skipped:
        print(f"  {skipped} enregistrement(s) ignoré(s) selon les filtres")

    # Écriture
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(converted, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(converted)} professionnels exportés → {out_path}")

    # Résumé
    cats: dict[str, int] = {}
    cities: set[str] = set()
    for b in converted:
        cats[b["cat"]] = cats.get(b["cat"], 0) + 1
        if b["city"]:
            cities.add(b["city"])

    print(f"\nCatégories ({len(cats)}) :")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat:20s} {count}")
    print(f"\nVilles ({len(cities)}) : {', '.join(sorted(cities))}")


if __name__ == "__main__":
    main()