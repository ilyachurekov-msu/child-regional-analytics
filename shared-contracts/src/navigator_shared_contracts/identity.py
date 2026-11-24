"""Canonical media-compatible identities; legacy primary keys stay untouched."""

from uuid import UUID, uuid5
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

NAMESPACE = UUID("72c4db98-6752-5fe0-a56d-af600628f13b")


def canonical_source_uuid(kind, url):
    parts = urlsplit(url.strip())
    if (
        parts.scheme.lower() not in ("http", "https")
        or not parts.hostname
        or parts.username
    ):
        raise ValueError("Public HTTP(S) source required")
    host = parts.hostname.encode("idna").decode().lower()
    port = parts.port
    if port and not (
        (parts.scheme == "https" and port == 443)
        or (parts.scheme == "http" and port == 80)
    ):
        host += f":{port}"
    query = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in ("yclid", "fbclid")
    )
    normalized = urlunsplit(
        (parts.scheme.lower(), host, parts.path or "/", urlencode(query), "")
    )
    return uuid5(NAMESPACE, f"source:{kind.strip().lower()}:{normalized}")
