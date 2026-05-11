from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import ValidationError

from contracts.common import ErrorItem
from contracts.extraction import DataExtractionRequest, DataExtractionResponse, DataSourceInfo
from services.extraction_client.base import ExtractionClient


class ColabExtractionClient(ExtractionClient):
    def __init__(
        self,
        service_url: str,
        timeout_seconds: float = 60,
        auth_token: str | None = None,
        http_client: httpx.Client | None = None,
    ):
        self.service_url = service_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.auth_token = auth_token.strip() if auth_token and auth_token.strip() else None
        self.http_client = http_client

    def _headers(self) -> dict[str, str]:
        if not self.auth_token:
            return {}
        return {"Authorization": f"Bearer {self.auth_token}"}

    def _failed(
        self,
        request: DataExtractionRequest,
        *,
        code: str,
        message: str,
        retryable: bool,
        details: dict[str, Any] | None = None,
    ) -> DataExtractionResponse:
        return DataExtractionResponse(
            request_id=request.request_id,
            status="failed",
            user_query=request.user_query,
            data_source=DataSourceInfo(
                id=request.data_source.id,
                dialect=request.data_source.dialect,
                schema_version=request.data_source.schema_version,
            ),
            errors=[
                ErrorItem(
                    code=code,
                    message=message,
                    source="colab",
                    retryable=retryable,
                    details=details or {},
                )
            ],
        )

    def extract(self, request: DataExtractionRequest) -> DataExtractionResponse:
        if not self.service_url:
            return self._failed(
                request,
                code="colab_unavailable",
                message="Colab service URL не настроен.",
                retryable=True,
            )

        payload = request.model_dump(mode="json")
        timeout = httpx.Timeout(self.timeout_seconds, connect=min(10.0, self.timeout_seconds))
        headers = self._headers()
        try:
            if self.http_client is None:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(f"{self.service_url}/extract", json=payload, headers=headers)
            else:
                response = self.http_client.post(f"{self.service_url}/extract", json=payload, headers=headers)
        except httpx.TimeoutException:
            return self._failed(
                request,
                code="extraction_timeout",
                message="Colab extraction service не ответил вовремя.",
                retryable=True,
            )
        except httpx.ConnectError:
            return self._failed(
                request,
                code="colab_unavailable",
                message="Colab extraction service недоступен.",
                retryable=True,
            )
        except httpx.RequestError:
            return self._failed(
                request,
                code="colab_unavailable",
                message="Не удалось выполнить HTTP-запрос к Colab extraction service.",
                retryable=True,
            )

        if response.status_code >= 500:
            return self._failed(
                request,
                code="colab_service_error",
                message="Colab extraction service вернул серверную ошибку.",
                retryable=True,
                details={"status_code": response.status_code},
            )
        if response.status_code >= 400:
            return self._failed(
                request,
                code="colab_request_error",
                message="Colab extraction service отклонил запрос.",
                retryable=False,
                details={"status_code": response.status_code},
            )

        try:
            data = response.json()
        except json.JSONDecodeError:
            return self._failed(
                request,
                code="invalid_extraction_response",
                message="Colab extraction service вернул невалидный JSON.",
                retryable=True,
            )

        try:
            parsed = DataExtractionResponse.model_validate(data)
        except ValidationError as exc:
            return self._failed(
                request,
                code="invalid_extraction_response",
                message="Colab extraction response не соответствует контракту.",
                retryable=True,
                details={"errors": exc.errors(include_url=False)[:5]},
            )

        if parsed.request_id != request.request_id:
            parsed = parsed.model_copy(update={"request_id": request.request_id})
        return parsed

    def list_models(self) -> tuple[bool, dict[str, Any]]:
        """GET /models on the Colab service. Returns (ok, payload)."""
        if not self.service_url:
            return False, {"colab_error_code": "colab_unavailable"}
        timeout = httpx.Timeout(min(5.0, self.timeout_seconds), connect=min(3.0, self.timeout_seconds))
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(f"{self.service_url}/models", headers=self._headers())
            if response.status_code >= 400:
                return False, {"colab_error_code": "colab_service_error", "status_code": response.status_code}
            payload = response.json()
            if not isinstance(payload, dict):
                return False, {"colab_error_code": "invalid_extraction_response"}
            return True, payload
        except httpx.TimeoutException:
            return False, {"colab_error_code": "extraction_timeout"}
        except httpx.RequestError:
            return False, {"colab_error_code": "colab_unavailable"}
        except json.JSONDecodeError:
            return False, {"colab_error_code": "invalid_extraction_response"}

    def load_model(self, model_id: str | None, *, target: str = "emitter") -> tuple[bool, dict[str, Any]]:
        """POST /reload_model with an optional model_id override. Slow (~minutes)."""
        if not self.service_url:
            return False, {"colab_error_code": "colab_unavailable"}
        # Long timeout — switching a 7B/14B model from cold HF cache can take
        # 1-3 minutes on L4. We don't bake in retries; the caller's UI shows a
        # spinner and surfaces failure verbatim.
        timeout = httpx.Timeout(self.timeout_seconds * 6, connect=min(10.0, self.timeout_seconds))
        body = {"target": target}
        if model_id:
            body["model_id"] = model_id
        try:
            if self.http_client is None:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(
                        f"{self.service_url}/reload_model",
                        json=body,
                        headers={**self._headers(), "Content-Type": "application/json"},
                    )
            else:
                response = self.http_client.post(
                    f"{self.service_url}/reload_model",
                    json=body,
                    headers={**self._headers(), "Content-Type": "application/json"},
                )
            if response.status_code >= 500:
                return False, {"colab_error_code": "colab_service_error", "status_code": response.status_code}
            if response.status_code >= 400:
                return False, {"colab_error_code": "colab_request_error", "status_code": response.status_code}
            payload = response.json()
            if not isinstance(payload, dict):
                return False, {"colab_error_code": "invalid_extraction_response"}
            return True, payload
        except httpx.TimeoutException:
            return False, {"colab_error_code": "extraction_timeout"}
        except httpx.RequestError:
            return False, {"colab_error_code": "colab_unavailable"}
        except json.JSONDecodeError:
            return False, {"colab_error_code": "invalid_extraction_response"}

    def health(self) -> tuple[bool, dict[str, Any]]:
        if not self.service_url:
            return False, {"colab_error_code": "colab_unavailable"}
        timeout = httpx.Timeout(min(5.0, self.timeout_seconds), connect=min(3.0, self.timeout_seconds))
        headers = self._headers()
        try:
            if self.http_client is None:
                with httpx.Client(timeout=timeout) as client:
                    response = client.get(f"{self.service_url}/health", headers=headers)
            else:
                response = self.http_client.get(f"{self.service_url}/health", headers=headers)
            if response.status_code >= 400:
                return False, {
                    "colab_error_code": "colab_service_error",
                    "status_code": response.status_code,
                }
            payload = response.json()
            if not isinstance(payload, dict):
                return False, {"colab_error_code": "invalid_extraction_response"}
            return True, payload
        except httpx.TimeoutException:
            return False, {"colab_error_code": "extraction_timeout"}
        except httpx.RequestError:
            return False, {"colab_error_code": "colab_unavailable"}
        except json.JSONDecodeError:
            return False, {"colab_error_code": "invalid_extraction_response"}
