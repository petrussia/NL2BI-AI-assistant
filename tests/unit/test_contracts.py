from contracts.extraction import DataExtractionRequest, DataSourceRequest
from contracts.nl2chart import Nl2ChartRequest


def test_nl2chart_request_defaults():
    request = Nl2ChartRequest(user_query="Покажи продажи")
    assert request.data_source_id == "demo_concert_singer"
    assert request.presentation_preferences.preferred_output == "auto"


def test_extraction_request_contract():
    request = DataExtractionRequest(
        request_id="r1",
        user_query="Покажи продажи",
        data_source=DataSourceRequest(id="demo_concert_singer"),
    )
    assert request.constraints.read_only is True
    assert request.presentation_hint.preferred_output == "auto"
