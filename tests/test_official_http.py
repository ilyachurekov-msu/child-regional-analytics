import httpx
import pytest
from app.etl.official_http import OfficialHTTP, SourceUnavailable

URL = "https://rosstat.gov.ru/storage/mediabank/test-fixture.csv"


def test_conditional_download_reuses_verified_original(tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, content=b"original", headers={"ETag": '"v1"'})
        assert request.headers["If-None-Match"] == '"v1"'
        return httpx.Response(304)

    client = OfficialHTTP(tmp_path, transport=httpx.MockTransport(handler), clock=lambda: 10000, sleep=lambda _: None)
    assert client.get(URL) == client.get(URL) == b"original"
    assert len(requests) == 2


@pytest.mark.parametrize("status", [403, 429, 503])
def test_refusal_stops_other_requests_to_same_host(tmp_path, status):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, headers={"Retry-After": "999999"})

    client = OfficialHTTP(tmp_path, transport=httpx.MockTransport(handler), clock=lambda: 10000, sleep=lambda _: None)
    with pytest.raises(SourceUnavailable):
        client.get(URL)
    # Even a new process/client and different file must honor the host cooldown.
    other = OfficialHTTP(tmp_path, transport=httpx.MockTransport(handler), clock=lambda: 20000)
    with pytest.raises(SourceUnavailable, match="no request sent"):
        other.get(URL + "2")
    assert len(requests) == 1


def test_response_bound_and_unofficial_urls_are_rejected(tmp_path):
    client = OfficialHTTP(tmp_path, transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"12345")))
    with pytest.raises(SourceUnavailable, match="size bound"):
        client.get(URL, max_bytes=4)
    with pytest.raises(SourceUnavailable, match="Only HTTPS"):
        client.get("http://rosstat.gov.ru/data")
    with pytest.raises(SourceUnavailable, match="Only HTTPS"):
        client.get("https://rosstat.gov.ru.example.com/data")
