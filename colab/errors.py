from __future__ import annotations

from enum import Enum


class ExtractionErrorCode(str, Enum):
    MODEL_NOT_LOADED = "model_not_loaded"
    SCHEMA_NOT_FOUND = "schema_not_found"
    AMBIGUOUS_QUERY = "ambiguous_query"
    SQL_GENERATION_FAILED = "sql_generation_failed"
    SQL_VALIDATION_FAILED = "sql_validation_failed"
    SQL_EXECUTION_FAILED = "sql_execution_failed"
    TIMEOUT = "timeout"
    EMPTY_RESULT = "empty_result"
    ROW_LIMIT_EXCEEDED = "row_limit_exceeded"
    METADATA_INCOMPLETE = "metadata_incomplete"


SAFE_USER_MESSAGES = {
    ExtractionErrorCode.MODEL_NOT_LOADED: "Модель Text-to-SQL ещё не загружена.",
    ExtractionErrorCode.SCHEMA_NOT_FOUND: "Схема для указанного источника данных не найдена.",
    ExtractionErrorCode.AMBIGUOUS_QUERY: "Запрос пользователя нельзя однозначно интерпретировать.",
    ExtractionErrorCode.SQL_GENERATION_FAILED: "Не удалось сгенерировать SQL по запросу.",
    ExtractionErrorCode.SQL_VALIDATION_FAILED: "Сгенерированный SQL не прошёл проверку безопасности.",
    ExtractionErrorCode.SQL_EXECUTION_FAILED: "Ошибка при выполнении SQL на демонстрационной БД.",
    ExtractionErrorCode.TIMEOUT: "Превышено время выполнения запроса.",
    ExtractionErrorCode.EMPTY_RESULT: "Запрос выполнен, но не вернул строк.",
    ExtractionErrorCode.ROW_LIMIT_EXCEEDED: "Достигнут лимит количества строк, результат усечён.",
    ExtractionErrorCode.METADATA_INCOMPLETE: "Не удалось вывести полную метаинформацию по полям.",
}
