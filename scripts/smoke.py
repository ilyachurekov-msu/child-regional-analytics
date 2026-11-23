import argparse
import time
import json
from pathlib import Path
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
                official = client.get(
                    "http://localhost:8000/api/v1/regional/values",
                    params={"region_id": "RU-42", "limit": 1000},
                ).json()
                receipt = {
                    "official_observations": official["total"],
                    "regions": ["RU-42"] if official["total"] else [],
                    "years": sorted({r["period_start"][:4] for r in official["items"]}),
                    "latest_loaded_at": max(
                        (r["loaded_at"] for r in official["items"]), default=None
                    ),
                }
                Path("test-results").mkdir(exist_ok=True)
                Path("test-results/official-load-receipt.json").write_text(
                    json.dumps(receipt, indent=2), encoding="utf-8"
                )
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
