"""
CPU-safe Colab service template.

This file is a contract scaffold for Google Colab Pro+. The server runtime in
this repository does not import it or run model dependencies. In Colab, replace
`extract_with_model` with GPU Text-to-SQL inference and keep the HTTP contract.
"""

from __future__ import annotations

from fastapi import FastAPI

from contracts.extraction import DataExtractionRequest, DataExtractionResponse
from services.extraction_client.mock_client import MockExtractionClient
from services.gateway.config import REPO_ROOT


app = FastAPI(title="NL2BI Colab Text-to-SQL Service")
mock = MockExtractionClient(REPO_ROOT / "demo_data")


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "model_loaded": False,
        "gpu_name": None,
        "mode": "contract_template",
    }


@app.post("/extract", response_model=DataExtractionResponse)
def extract(body: DataExtractionRequest) -> DataExtractionResponse:
    return mock.extract(body)


@app.post("/reload_model")
def reload_model() -> dict[str, object]:
    return {"status": "noop", "model_loaded": False}

