from __future__ import annotations

from abc import ABC, abstractmethod

from contracts.extraction import DataExtractionRequest, DataExtractionResponse


class ExtractionClient(ABC):
    @abstractmethod
    def extract(self, request: DataExtractionRequest) -> DataExtractionResponse:
        raise NotImplementedError

