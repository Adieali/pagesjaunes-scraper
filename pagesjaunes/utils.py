"""
Utilitaires partagés.
"""

import re
from urllib.parse import urlparse


# Ressources non essentielles à bloquer pour accélérer le crawl
BLOCK_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}
BLOCK_URL_PATTERNS = [
    "google-analytics",
    "doubleclick",
    "googlesyndication",
    "facebook.net",
    "twitter.com/widgets",
    "hotjar",
    "intercom",
]


def abort_non_essential(request):
    """
    Callback Playwright : bloque les ressources inutiles (images, CSS, analytics).
    Retourne True pour bloquer la requête, False pour la laisser passer.
    """
    if request.resource_type in BLOCK_RESOURCE_TYPES:
        return True
    url = request.url.lower()
    return any(pattern in url for pattern in BLOCK_URL_PATTERNS)


def extract_domain(url: str) -> str:
    """Extrait le domaine depuis une URL."""
    try:
        return urlparse(url).netloc
    except Exception:
        return ""


def normalize_french_phone(phone: str) -> str:
    """Normalise un numéro de téléphone français."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("33") and len(digits) == 11:
        digits = "0" + digits[2:]
    if len(digits) == 10 and digits.startswith("0"):
        return " ".join([digits[i:i+2] for i in range(0, 10, 2)])
    return phone
