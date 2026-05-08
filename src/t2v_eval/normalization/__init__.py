"""Visualization specification normalization."""

from t2v_eval.normalization.vega_lite import (
    SpecNormalizationError,
    aggregate_tokens,
    canonical_json,
    encoding_tokens,
    fields_in_normalized,
    is_vega_lite_like,
    mark_type,
    normalize_spec,
)

__all__ = [
    "SpecNormalizationError",
    "aggregate_tokens",
    "canonical_json",
    "encoding_tokens",
    "fields_in_normalized",
    "is_vega_lite_like",
    "mark_type",
    "normalize_spec",
]
