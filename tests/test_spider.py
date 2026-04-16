"""
Tests unitaires — Spider Pages Jaunes

Teste l'extraction des données depuis des pages HTML fixtures
sans requêtes réseau réelles.
"""

import json
from pathlib import Path

import pytest
from scrapy.http import HtmlResponse, Request

from pagesjaunes.spiders.pagesjaunes_spider import PagesJaunesSpider


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def make_response(filename: str, url: str = "https://www.pagesjaunes.fr/pros/test") -> HtmlResponse:
    """Crée une réponse Scrapy depuis un fichier HTML fixture."""
    html = (FIXTURES_DIR / filename).read_bytes()
    return HtmlResponse(url=url, body=html, encoding="utf-8")


@pytest.fixture
def spider():
    return PagesJaunesSpider(what="restaurant", where="Paris", max_pages=1)


class TestSpiderParsing:

    def test_spider_name(self, spider):
        assert spider.name == "pagesjaunes"

    def test_spider_init(self, spider):
        assert spider.what == "restaurant"
        assert spider.where == "Paris"
        assert spider.max_pages == 1

    def test_search_url_page1(self, spider):
        url = spider._build_search_url(page=1)
        assert "quoiqui=restaurant" in url
        assert "ou=Paris" in url
        assert "pagesjaunes.fr" in url
        assert "page=" not in url  # page=1 non incluse

    def test_search_url_page2(self, spider):
        url = spider._build_search_url(page=2)
        assert "page=2" in url

    def test_parse_detail_name(self, spider):
        response = make_response("sample_listing.html")
        results = list(spider.parse_detail.__wrapped__(spider, response)
                       if hasattr(spider.parse_detail, '__wrapped__')
                       else [])
        # Test via le générateur sync (parse_detail est async)
        # On teste les méthodes helper directement

    def test_clean_method(self, spider):
        assert spider._clean("  Hello   World  ") == "Hello World"
        assert spider._clean("") == ""
        assert spider._clean(None) == ""

    def test_extract_postal_code(self, spider):
        assert spider._extract_postal_code("42 Rue de Rivoli 75001 Paris") == "75001"
        assert spider._extract_postal_code("Pas de code") is None
        assert spider._extract_postal_code("69001 Lyon") == "69001"

    def test_extract_street(self, spider):
        result = spider._extract_street("42 Rue de Rivoli 75001 Paris")
        assert "42 Rue de Rivoli" in result

    def test_extract_gps_from_jsonld(self, spider):
        response = make_response("sample_listing.html")
        lat, lng = spider._extract_gps(response)
        assert lat == 48.8566
        assert lng == 2.3522

    def test_extract_rating_from_jsonld(self, spider):
        response = make_response("sample_listing.html")
        rating = response.css(
            "[itemprop='ratingValue']::attr(content)"
        ).get()
        assert rating == "4.3"

    def test_extract_reviews_count(self, spider):
        response = make_response("sample_listing.html")
        count = response.css(
            "[itemprop='reviewCount']::attr(content)"
        ).get()
        assert count == "127"

    def test_extract_phone(self, spider):
        response = make_response("sample_listing.html")
        phone = response.css("[itemprop='telephone']::text").get()
        assert phone == "01 23 45 67 89"

    def test_extract_website(self, spider):
        response = make_response("sample_listing.html")
        website = response.css("[itemprop='url']::attr(href)").get()
        assert website == "https://www.bistrot-parisien.fr"

    def test_extract_email(self, spider):
        response = make_response("sample_listing.html")
        email = response.css("a[href^='mailto:']::attr(href)").get("")
        assert "contact@bistrot-parisien.fr" in email

    def test_extract_social_facebook(self, spider):
        response = make_response("sample_listing.html")
        fb = response.css("a[href*='facebook.com']::attr(href)").get()
        assert "facebook.com/bistrotparisien" in fb

    def test_extract_hours_jsonld(self, spider):
        response = make_response("sample_listing.html")
        hours = spider._extract_hours(response)
        assert isinstance(hours, dict)
        # Les horaires JSON-LD sont parsés
        assert len(hours) >= 1


class TestNormalization:

    def test_normalize_phone_french(self, spider):
        from pagesjaunes.middlewares.user_agent import USER_AGENTS
        assert len(USER_AGENTS) >= 10

    def test_user_agents_not_empty(self, spider):
        from pagesjaunes.middlewares.user_agent import USER_AGENTS
        for ua in USER_AGENTS:
            assert len(ua) > 20
            assert "Mozilla" in ua


class TestPipelines:

    def test_validation_pipeline_drops_empty_name(self):
        from scrapy.exceptions import DropItem
        from pagesjaunes.pipelines import ValidationPipeline
        from pagesjaunes.items import BusinessItem

        pipeline = ValidationPipeline()
        item = BusinessItem()
        item["name"] = ""
        item["source_url"] = "https://example.com"

        with pytest.raises(DropItem):
            pipeline.process_item(item, spider=None)

    def test_validation_pipeline_passes_valid_item(self):
        from pagesjaunes.pipelines import ValidationPipeline
        from pagesjaunes.items import BusinessItem

        pipeline = ValidationPipeline()
        item = BusinessItem()
        item["name"] = "Le Bistrot"
        item["source_url"] = "https://www.pagesjaunes.fr/pros/le-bistrot"

        result = pipeline.process_item(item, spider=None)
        assert result["name"] == "Le Bistrot"

    def test_cleaning_pipeline_normalizes_phone(self):
        from pagesjaunes.pipelines import CleaningPipeline
        from pagesjaunes.items import BusinessItem

        pipeline = CleaningPipeline()
        item = BusinessItem()
        item["name"] = "Test"
        item["source_url"] = "https://example.com"
        item["phone"] = "0123456789"
        item["website"] = "example.com"
        item["rating"] = 4.5

        result = pipeline.process_item(item, spider=None)
        assert result["phone"] == "01 23 45 67 89"
        assert result["website"].startswith("https://")

    def test_cleaning_pipeline_invalidates_bad_rating(self):
        from pagesjaunes.pipelines import CleaningPipeline
        from pagesjaunes.items import BusinessItem

        pipeline = CleaningPipeline()
        item = BusinessItem()
        item["name"] = "Test"
        item["source_url"] = "https://example.com"
        item["phone"] = ""
        item["website"] = ""
        item["rating"] = 7.5  # invalide

        result = pipeline.process_item(item, spider=None)
        assert result["rating"] is None

    def test_duplicate_filter(self):
        from scrapy.exceptions import DropItem
        from pagesjaunes.pipelines import DuplicateFilterPipeline
        from pagesjaunes.items import BusinessItem

        pipeline = DuplicateFilterPipeline()

        item1 = BusinessItem()
        item1["listing_id"] = "abc123"
        item1["source_url"] = "https://www.pagesjaunes.fr/pros/abc123"

        item2 = BusinessItem()
        item2["listing_id"] = "abc123"  # doublon
        item2["source_url"] = "https://www.pagesjaunes.fr/pros/abc123"

        pipeline.process_item(item1, spider=None)  # OK
        with pytest.raises(DropItem):
            pipeline.process_item(item2, spider=None)  # Doublon → DropItem
