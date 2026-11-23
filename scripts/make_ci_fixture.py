"""Synthetic isolated CI observations. Never an official import or release asset."""

import csv
from pathlib import Path


if __name__ == "__main__":
    path = Path("data/ci-fixture.csv")
    path.parent.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "indicator_code",
                "region",
                "period_start",
                "period_end",
                "value",
                "published_at",
            ]
        )
        for region in ("RU-77", "RU-78"):
            for year in (2022, 2023):
                for index, code in enumerate(
                    ("births", "deaths", "natural_change", "marriages", "divorces")
                ):
                    writer.writerow(
                        [
                            code,
                            region,
                            f"{year}-01-01",
                            f"{year}-12-31",
                            100 + index + year - 2022,
                            "2024-07-12T00:00:00Z",
                        ]
                    )
