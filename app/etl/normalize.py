import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, urlunsplit


def normalize_region(value):
    return re.sub(r"[\W_]+", " ", str(value).lower().replace("ё", "е")).strip()


def source_identifier(url):
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("Источник должен иметь публичный URL HTTP(S)")
    host = parts.hostname.lower().removeprefix("www.")
    port = parts.port
    if port and port not in (80, 443):
        host += f":{port}"
    # Query retained: it may select a distinct official dataset.
    return urlunsplit(("https", host, parts.path.rstrip("/"), parts.query, ""))


def number(raw):
    if raw is None or str(raw).strip().lower() in (
        "",
        "…",
        "...",
        "—",
        "-",
        "н/д",
        "nan",
        "null",
    ):
        return None
    try:
        value = Decimal(
            str(raw).replace("\u00a0", "").replace(" ", "").replace(",", ".")
        )
    except InvalidOperation:
        raise ValueError(f"Некорректное число: {raw!r}") from None
    if not value.is_finite():
        raise ValueError("Число должно быть конечным")
    if abs(value) >= Decimal("1e18") or value.as_tuple().exponent < -6:
        raise ValueError("Число выходит за точность NUMERIC(24,6)")
    return value
