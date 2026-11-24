from app.contract_version import CONTRACT_VERSION
import json
from pathlib import Path
from app.schemas.contracts import PlatformContract
from app.api.main import app


if __name__ == "__main__":
    contract = PlatformContract.model_json_schema()
    contract.update(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"urn:navigator-childhood:platform:{CONTRACT_VERSION}",
            "x-contract-version": CONTRACT_VERSION,
        }
    )
    contract["properties"]["contract_version"]["const"] = CONTRACT_VERSION
    Path("contracts/platform.schema.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("contracts/openapi.json").write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
