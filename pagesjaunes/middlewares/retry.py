"""
Middleware de détection de ban et retry intelligent.
"""

import logging
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message

logger = logging.getLogger(__name__)

# Patterns HTML indiquant un blocage
BAN_PATTERNS = [
    "Access Denied",
    "Robot Check",
    "Please enable JS",
    "captcha",
    "Accès refusé",
    "Votre accès a été",
]


class RetryOnBanMiddleware(RetryMiddleware):
    """
    Étend le RetryMiddleware standard pour détecter les bans soft
    (pages HTML avec message d'erreur, pas juste les codes HTTP).
    """

    def process_response(self, request, response, spider):
        if response.status == 200 and self._is_banned(response):
            logger.warning(
                f"Ban soft détecté sur {request.url} — retry ({response.status})"
            )
            reason = "soft_ban"
            return self._retry(request, reason, spider) or response

        return super().process_response(request, response, spider)

    def _is_banned(self, response) -> bool:
        try:
            text = response.text.lower()
            return any(p.lower() in text for p in BAN_PATTERNS)
        except Exception:
            return False
