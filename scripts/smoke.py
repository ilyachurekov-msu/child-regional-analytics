import argparse
import time
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-observations", type=int)
    args = parser.parse_args()
    last_error = None
    for _ in range(60):
        try:
            with httpx.Client(timeout=5) as client:
                for path in (
                    "health",
                    "regions",
                    "regional/indicators",
                    "regional/values",
                    "regional/profiles/RU-77",
                    "regional/data-quality",
                    "openapi.json",
                ):
                    response = client.get("http://localhost:8000/api/v1/" + path)
                    response.raise_for_status()
                client.get("http://localhost:8501/_stcore/health").raise_for_status()
                if args.expected_observations is not None:
                    count = client.get(
                        "http://localhost:8000/api/v1/regional/data-quality"
                    ).json()["current_observations"]
                    assert count == args.expected_observations, count
            print("API, PostgreSQL and Streamlit health checks passed")
            return
        except (httpx.HTTPError, AssertionError) as exc:
            last_error = exc
            time.sleep(2)
    raise SystemExit(f"Smoke checks failed: {last_error}")


if __name__ == "__main__":
    main()
