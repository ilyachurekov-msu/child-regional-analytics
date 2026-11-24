"""Bounded, conditional official downloads; no automatic retries or TLS overrides."""
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx


class SourceUnavailable(ValueError):
    pass


class OfficialHTTP:
    def __init__(self, cache=Path("data/archive/http"), *, transport=None, clock=time.time, sleep=time.sleep):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.clock, self.sleep, self.transport = clock, sleep, transport

    def get(self, url, max_bytes=50 * 1024 * 1024):
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        allowed = ("rosstat.gov.ru", "gks.ru", "fedstat.ru")
        if parsed.scheme != "https" or parsed.username or parsed.password or not any(
            host == root or host.endswith("." + root) for root in allowed
        ):
            raise SourceUnavailable("Only HTTPS URLs on known official domains are allowed")
        host_path = self.cache / (hashlib.sha256(host.encode()).hexdigest() + ".host.json")
        host_state = json.loads(host_path.read_text()) if host_path.exists() else {}
        if host_state.get("blocked_until", 0) > self.clock():
            raise SourceUnavailable("Source host is in cooldown; no request sent")
        delay = max(0, host_state.get("requested_at", 0) + 3 - self.clock())
        if delay:
            self.sleep(delay)
        host_state["requested_at"] = self.clock()
        host_path.write_text(json.dumps(host_state))
        key = hashlib.sha256(url.encode()).hexdigest()
        state_path, raw_path = self.cache / (key + ".json"), self.cache / (key + ".bin")
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        headers = {"User-Agent": "ChildRegionalAnalytics/0.2 (+https://github.com/ilyachurekov-msu/child-regional-analytics)"}
        if raw_path.exists() and hashlib.sha256(raw_path.read_bytes()).hexdigest() == state.get("sha256"):
            if state.get("etag"):
                headers["If-None-Match"] = state["etag"]
            if state.get("last_modified"):
                headers["If-Modified-Since"] = state["last_modified"]
        with httpx.Client(timeout=30, transport=self.transport, follow_redirects=False) as client:
            with client.stream("GET", url, headers=headers) as response:
                if response.status_code in (403, 429, 503):
                    retry = response.headers.get("Retry-After", "")
                    seconds = max(86400 if response.status_code != 503 else 3600,
                                  int(retry) if retry.isdigit() else 0)
                    if retry and not retry.isdigit():
                        from email.utils import parsedate_to_datetime
                        try:
                            seconds = max(seconds, parsedate_to_datetime(retry).timestamp() - self.clock())
                        except (ValueError, TypeError, OverflowError):
                            pass
                    host_state["blocked_until"] = self.clock() + seconds
                    host_path.write_text(json.dumps(host_state))
                    raise SourceUnavailable(f"Official host returned HTTP {response.status_code}; cooldown applied")
                if response.status_code == 304:
                    if not raw_path.exists() or not state.get("sha256"):
                        raise SourceUnavailable("304 without a verified cached original")
                    raw = raw_path.read_bytes()
                    if len(raw) > max_bytes or hashlib.sha256(raw).hexdigest() != state["sha256"]:
                        raise SourceUnavailable("Cached original failed integrity check")
                    return raw
                response.raise_for_status()
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > max_bytes:
                        raise SourceUnavailable("Official response exceeds size bound")
                content = bytes(raw)
                # Save bytes first. Metadata never points at an unverified cache object.
                raw_path.write_bytes(content)
                state_path.write_text(json.dumps(dict(
                    url=url, retrieved_at=self.clock(), sha256=hashlib.sha256(content).hexdigest(),
                    etag=response.headers.get("ETag"), last_modified=response.headers.get("Last-Modified"),
                )))
                return content
