"""
Spider principal — Pages Jaunes Pro Scraper

Collecte les fiches d'établissements professionnels publiques :
  - Informations générales (nom, catégorie, description)
  - Coordonnées de contact public (téléphone, site web, email, réseaux sociaux)
  - Localisation (adresse complète, coordonnées GPS)
  - Horaires d'ouverture
  - Avis et notes agrégées

⚠️  Conformité RGPD :
  - Seules les données professionnelles publiées volontairement sont collectées
  - Aucune donnée personnelle d'individu privé n'est traitée
  - Rate limiting respectueux (DOWNLOAD_DELAY = 2s min)
  - Robots.txt consulté (configurable)
"""

import json
import re
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode, urljoin

import scrapy
from scrapy_playwright.page import PageMethod

from pagesjaunes.items import BusinessItem

logger = logging.getLogger(__name__)

BASE_URL = "https://www.pagesjaunes.fr"
SEARCH_URL = f"{BASE_URL}/annuaire/chercherlespros"


class PagesJaunesSpider(scrapy.Spider):
    name = "pagesjaunes"
    allowed_domains = ["pagesjaunes.fr"]

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 45000,
    }

    def __init__(
        self,
        what: str = "restaurant",
        where: str = "Paris",
        max_pages: int = 5,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.what = what
        self.where = where
        self.max_pages = int(max_pages)
        self.scraped_urls: set[str] = set()
        logger.info(
            f"Spider initialisé — what='{what}' where='{where}' max_pages={max_pages}"
        )

    def start_requests(self):
        url = self._build_search_url(page=1)
        logger.info(f"Démarrage du crawl : {url}")
        yield scrapy.Request(
            url,
            callback=self.parse_search,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", "ul.bi-list", timeout=20000),
                ],
                "page_number": 1,
                "dont_filter": True,
            },
            errback=self.handle_error,
        )

    def _build_search_url(self, page: int = 1) -> str:
        params = {
            "quoiqui": self.what,
            "ou": self.where,
        }
        if page > 1:
            params["page"] = page
        return f"{SEARCH_URL}?{urlencode(params)}"

    async def parse_search(self, response):
        """Parse une page de résultats de recherche."""
        page = response.meta.get("playwright_page")
        page_number = response.meta.get("page_number", 1)

        if page:
            await page.close()

        # Extraction des liens vers les fiches détail
        listing_links = response.css(
            "ul.bi-list li.bi-item a.bi-denomination::attr(href)"
        ).getall()

        # Fallback sélecteurs alternatifs
        if not listing_links:
            listing_links = response.css(
                "[data-pj-id] a[href*='/pros/']::attr(href)"
            ).getall()

        if not listing_links:
            listing_links = response.css(
                "a.denomination-v2::attr(href)"
            ).getall()

        logger.info(
            f"Page {page_number}: {len(listing_links)} fiches trouvées"
        )

        for href in listing_links:
            detail_url = urljoin(BASE_URL, href)
            if detail_url not in self.scraped_urls:
                self.scraped_urls.add(detail_url)
                yield scrapy.Request(
                    detail_url,
                    callback=self.parse_detail,
                    meta={
                        "playwright": True,
                        "playwright_include_page": True,
                        "playwright_page_methods": [
                            PageMethod(
                                "wait_for_selector",
                                ".denomination-header, h1",
                                timeout=20000,
                            ),
                        ],
                        "page_number": page_number,
                        "dont_filter": True,
                    },
                    errback=self.handle_error,
                )

        # Pagination — page suivante
        if page_number < self.max_pages:
            next_page = page_number + 1
            has_next = response.css(
                "a[aria-label='Page suivante'], .pagination-next:not(.disabled)"
            )
            if has_next:
                next_url = self._build_search_url(page=next_page)
                logger.info(f"Passage à la page {next_page}: {next_url}")
                yield scrapy.Request(
                    next_url,
                    callback=self.parse_search,
                    meta={
                        "playwright": True,
                        "playwright_include_page": True,
                        "playwright_page_methods": [
                            PageMethod(
                                "wait_for_selector", "ul.bi-list", timeout=20000
                            ),
                        ],
                        "page_number": next_page,
                        "dont_filter": True,
                    },
                    errback=self.handle_error,
                )
            else:
                logger.info(f"Dernière page atteinte ({page_number}).")

    async def parse_detail(self, response):
        """Parse une fiche établissement complète."""
        page = response.meta.get("playwright_page")
        if page:
            await page.close()

        item = BusinessItem()
        item["source_url"] = response.url
        item["page_number"] = response.meta.get("page_number", 1)
        item["search_query"] = self.what
        item["search_location"] = self.where
        item["scraped_at"] = datetime.now(timezone.utc).isoformat()

        # ── Identifiant ───────────────────────────────────────────────────
        listing_id = re.search(r"/pros/([^?#/]+)", response.url)
        item["listing_id"] = listing_id.group(1) if listing_id else None

        # ── Nom et catégories ─────────────────────────────────────────────
        item["name"] = self._clean(
            response.css(
                "h1.denomination-header::text, "
                ".denomination-v2::text, "
                "h1[data-pj-id]::text"
            ).get("")
        )

        item["category"] = self._clean(
            response.css(
                ".rubrique-denomination::text, "
                ".main-activity::text, "
                "[data-rubrique]::text"
            ).get("")
        )

        subcats = response.css(
            ".activite::text, .secondary-activity::text"
        ).getall()
        item["subcategories"] = [self._clean(s) for s in subcats if self._clean(s)]

        # ── Description ───────────────────────────────────────────────────
        item["description"] = self._clean(
            response.css(
                ".description-content p::text, "
                ".presentation-text::text"
            ).get("")
        )

        # ── Adresse ───────────────────────────────────────────────────────
        address_parts = response.css(
            ".address-container span::text, "
            "[itemprop='streetAddress']::text, "
            ".adresse-v2 span::text"
        ).getall()

        full_address = " ".join(
            [self._clean(p) for p in address_parts if self._clean(p)]
        )

        item["address_street"] = self._extract_street(full_address)
        item["address_postal_code"] = self._extract_postal_code(full_address)
        item["address_city"] = self._clean(
            response.css(
                "[itemprop='addressLocality']::text, "
                ".city-name::text"
            ).get("")
        )
        item["address_department"] = None
        item["address_region"] = None

        # ── Coordonnées GPS ───────────────────────────────────────────────
        lat, lng = self._extract_gps(response)
        item["latitude"] = lat
        item["longitude"] = lng

        # ── Contact professionnel public ──────────────────────────────────
        item["phone"] = self._clean(
            response.css(
                "[data-phone]::attr(data-phone), "
                "[itemprop='telephone']::text, "
                ".number-section span::text"
            ).get("")
        )

        item["website"] = self._clean(
            response.css(
                "a[data-website]::attr(href), "
                "a[itemprop='url']::attr(href), "
                ".website-link::attr(href)"
            ).get("")
        )

        item["email"] = self._clean(
            response.css(
                "a[href^='mailto:']::attr(href)"
            ).get("").replace("mailto:", "")
        )

        # Réseaux sociaux
        social_links = response.css("a[href*='facebook.com']::attr(href), "
                                     "a[href*='twitter.com']::attr(href), "
                                     "a[href*='instagram.com']::attr(href), "
                                     "a[href*='linkedin.com']::attr(href)").getall()
        item["social_facebook"] = next(
            (l for l in social_links if "facebook.com" in l), None
        )
        item["social_twitter"] = next(
            (l for l in social_links if "twitter.com" in l), None
        )
        item["social_instagram"] = next(
            (l for l in social_links if "instagram.com" in l), None
        )
        item["social_linkedin"] = next(
            (l for l in social_links if "linkedin.com" in l), None
        )

        # ── Horaires d'ouverture ──────────────────────────────────────────
        item["opening_hours"] = self._extract_hours(response)
        item["is_open_now"] = bool(
            response.css(".open-status.is-open, .ouvert::text").get()
        )

        # ── Avis & réputation ─────────────────────────────────────────────
        rating_text = response.css(
            "[itemprop='ratingValue']::attr(content), "
            ".note-globale::text, "
            ".rating-value::text"
        ).get("")
        try:
            item["rating"] = float(self._clean(rating_text).replace(",", "."))
        except (ValueError, AttributeError):
            item["rating"] = None

        reviews_text = response.css(
            "[itemprop='reviewCount']::attr(content), "
            ".avis-count::text, "
            ".reviews-count::text"
        ).get("")
        try:
            item["reviews_count"] = int(
                re.sub(r"\D", "", self._clean(reviews_text))
            )
        except (ValueError, AttributeError):
            item["reviews_count"] = None

        item["rating_distribution"] = self._extract_rating_distribution(response)

        yield item

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _clean(text: str) -> str:
        if not text:
            return ""
        return " ".join(text.split()).strip()

    @staticmethod
    def _extract_street(full_address: str) -> str:
        """Extrait la rue d'une adresse complète."""
        match = re.match(r"^(.*?)\d{5}", full_address)
        return match.group(1).strip() if match else full_address

    @staticmethod
    def _extract_postal_code(full_address: str) -> str | None:
        match = re.search(r"\b(\d{5})\b", full_address)
        return match.group(1) if match else None

    def _extract_gps(self, response) -> tuple[float | None, float | None]:
        """Extrait lat/lng depuis les données JSON-LD ou attributs data."""
        # Tentative JSON-LD
        for script in response.css("script[type='application/ld+json']::text").getall():
            try:
                data = json.loads(script)
                if isinstance(data, list):
                    data = data[0]
                geo = data.get("geo", {})
                lat = geo.get("latitude") or data.get("latitude")
                lng = geo.get("longitude") or data.get("longitude")
                if lat and lng:
                    return float(lat), float(lng)
            except (json.JSONDecodeError, KeyError, TypeError):
                continue

        # Tentative attributs data-*
        lat = response.css("[data-lat]::attr(data-lat)").get()
        lng = response.css("[data-lng]::attr(data-lng)").get()
        if lat and lng:
            try:
                return float(lat), float(lng)
            except ValueError:
                pass

        # Tentative URL Google Maps embarquée
        maps_url = response.css("iframe[src*='maps']::attr(src)").get("")
        ll_match = re.search(r"ll=(-?\d+\.\d+),(-?\d+\.\d+)", maps_url)
        if ll_match:
            return float(ll_match.group(1)), float(ll_match.group(2))

        return None, None

    def _extract_hours(self, response) -> dict:
        """Extrait les horaires sous forme de dict {jour: [ouvertures]}."""
        hours = {}
        rows = response.css(".horaires-item, .opening-hours tr, [itemprop='openingHours']")
        for row in rows:
            day = self._clean(row.css(".day::text, td:first-child::text").get(""))
            times = row.css(".hours::text, td:last-child::text").getall()
            if day:
                hours[day] = [self._clean(t) for t in times if self._clean(t)]

        # Fallback : attribut openingHours du JSON-LD
        if not hours:
            for script in response.css(
                "script[type='application/ld+json']::text"
            ).getall():
                try:
                    data = json.loads(script)
                    if isinstance(data, list):
                        data = data[0]
                    oh = data.get("openingHours", [])
                    for entry in oh:
                        parts = entry.split(" ", 1)
                        if len(parts) == 2:
                            hours[parts[0]] = [parts[1]]
                except (json.JSONDecodeError, AttributeError):
                    continue

        return hours

    def _extract_rating_distribution(self, response) -> dict:
        """Extrait la distribution des notes (étoiles 1 à 5)."""
        dist = {}
        for i in range(1, 6):
            count = response.css(
                f".rating-bar[data-rating='{i}'] .count::text, "
                f".stars-{i} .count::text"
            ).get()
            if count:
                try:
                    dist[i] = int(re.sub(r"\D", "", count))
                except ValueError:
                    pass
        return dist

    def handle_error(self, failure):
        logger.error(f"Erreur sur {failure.request.url}: {failure.value}")
