"""Origin checks for local browser-driven automation endpoints."""

import ipaddress
from urllib.parse import urlsplit

ALLOWED_DEV_ORIGINS = frozenset({
    "http://localhost:5173",
    "http://127.0.0.1:5173",
})


def is_loopback_origin(origin: str) -> bool:
    hostname = urlsplit(origin).hostname
    if hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname or "").is_loopback
    except ValueError:
        return False


def is_safe_mutation_request(origin: str | None, request_origin: str, fetch_site: str | None) -> bool:
    """Allow same-origin and known local dev requests, but reject cross-site mutations."""
    normalized_request_origin = (request_origin or "").rstrip("/")
    if not is_loopback_origin(normalized_request_origin):
        return False
    if origin:
        normalized_origin = origin.rstrip("/")
        return normalized_origin == normalized_request_origin or normalized_origin in ALLOWED_DEV_ORIGINS
    return (fetch_site or "").casefold() in {"same-origin", "same-site", "none"}
