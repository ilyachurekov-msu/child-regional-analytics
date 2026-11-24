"""One-off availability diagnostics. No DB writes and no TLS bypass."""
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import urlopen
import hashlib
import json

URLS = [
    'https://rosstat.gov.ru/storage/mediabank/EDN_12-2023.html',
    'https://www.rosstat.gov.ru/storage/mediabank/EDN_12-2024.htm',
    'https://www.rosstat.gov.ru/folder/210/document/47652?print=1',
]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href = dict(attrs).get('href', '')
            if href:
                self.links.append(href)


def probe(url):
    try:
        with urlopen(url, timeout=30) as response:
            raw = response.read(5_000_001)
            if len(raw) > 5_000_000:
                raise ValueError('Index response exceeds bound')
        parser = Links()
        parser.feed(raw.decode('utf-8', errors='replace'))
        return dict(url=url, status='available', sha256=hashlib.sha256(raw).hexdigest(),
                    links=[urljoin(url, link) for link in parser.links if any(x in link.lower() for x in ('.xls', '2023', '2022', '2021', '2020', '2019', 'edn'))][:80])
    except Exception as exc:
        return dict(url=url, status='unavailable', error=type(exc).__name__ + ': ' + str(exc)[:200])


if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=3) as pool:
        print(json.dumps(list(pool.map(probe, URLS)), ensure_ascii=False, indent=2))
