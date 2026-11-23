import json
from pathlib import Path
from app.schemas.contracts import PlatformContract
from app.api.main import app


if __name__ == "__main__":
    contract = PlatformContract.model_json_schema()
    contract.update(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "urn:navigator-childhood:platform:1.0.0",
            "x-contract-version": "1.0.0",
        }
    )
    contract["properties"]["contract_version"]["const"] = "1.0.0"
    Path("contracts/platform.schema.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("contracts/openapi.json").write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
