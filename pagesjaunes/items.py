"""
Scrapy Items — Définition des champs collectés.

Données B2B publiques uniquement (conformes RGPD) :
 - Informations d'établissement affichées publiquement sur Pages Jaunes
 - Aucune donnée personnelle d'individu privé n'est collectée
"""

import scrapy


class BusinessItem(scrapy.Item):
    # ── Identifiant ──────────────────────────────────────────────────────
    source_url = scrapy.Field()       # URL de la fiche Pages Jaunes
    listing_id = scrapy.Field()       # Identifiant unique PJ

    # ── Informations générales ────────────────────────────────────────────
    name = scrapy.Field()             # Raison sociale
    category = scrapy.Field()         # Catégorie principale (ex. "Restaurant")
    subcategories = scrapy.Field()    # Sous-catégories (liste)
    description = scrapy.Field()      # Description de l'établissement

    # ── Localisation ──────────────────────────────────────────────────────
    address_street = scrapy.Field()   # Numéro et rue
    address_city = scrapy.Field()     # Ville
    address_postal_code = scrapy.Field()
    address_department = scrapy.Field()
    address_region = scrapy.Field()
    latitude = scrapy.Field()         # Coordonnées GPS
    longitude = scrapy.Field()

    # ── Contact professionnel public ──────────────────────────────────────
    phone = scrapy.Field()            # Numéro affiché publiquement
    website = scrapy.Field()          # Site web de l'entreprise
    email = scrapy.Field()            # Email professionnel public
    social_facebook = scrapy.Field()
    social_twitter = scrapy.Field()
    social_instagram = scrapy.Field()
    social_linkedin = scrapy.Field()

    # ── Horaires ──────────────────────────────────────────────────────────
    opening_hours = scrapy.Field()    # Dict {jour: [ouverture, fermeture]}
    is_open_now = scrapy.Field()      # Boolean indicatif

    # ── Avis & réputation ─────────────────────────────────────────────────
    rating = scrapy.Field()           # Note moyenne (float)
    reviews_count = scrapy.Field()    # Nombre total d'avis
    rating_distribution = scrapy.Field()  # {1: n, 2: n, 3: n, 4: n, 5: n}

    # ── Métadonnées de collecte ───────────────────────────────────────────
    search_query = scrapy.Field()     # Requête utilisée
    search_location = scrapy.Field()  # Zone géographique recherchée
    scraped_at = scrapy.Field()       # Timestamp ISO 8601
    page_number = scrapy.Field()
