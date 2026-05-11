from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any

from colab.config import ColabServerConfig
from colab.prompt import build_chat_messages
from colab.schema_loader import DatabaseSchema


@dataclass
class ModelState:
    loaded: bool
    model_id: str | None
    mock: bool
    quantization: str | None
    load_error: str | None = None
    load_latency_ms: int | None = None


class TextToSqlModel:
    """Wraps Qwen2.5-Coder (or any HF chat-style LLM) for SQL generation.

    In mock mode (or when HF stack is unavailable) returns a deterministic
    SQL stub based on simple keyword heuristics over the schema, so the
    HTTP contract can be tested without a real GPU.
    """

    def __init__(self, config: ColabServerConfig) -> None:
        self.config = config
        self._lock = threading.Lock()
        self._tokenizer: Any | None = None
        self._model: Any | None = None
        self.state = ModelState(
            loaded=False,
            model_id=None,
            mock=config.mock_model,
            quantization=None,
        )

    def is_ready(self) -> bool:
        if self.state.mock:
            return True
        return self.state.loaded and self._model is not None

    def load(self) -> ModelState:
        if self.state.mock:
            self.state = ModelState(
                loaded=True,
                model_id=self.config.model_id,
                mock=True,
                quantization="mock",
            )
            return self.state
        with self._lock:
            if self.state.loaded:
                return self.state
            started = time.monotonic()
            try:
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer
            except Exception as exc:
                self.state = ModelState(
                    loaded=False,
                    model_id=self.config.model_id,
                    mock=False,
                    quantization=None,
                    load_error=f"transformers stack unavailable: {type(exc).__name__}",
                )
                return self.state

            quantization = self.config.quantization
            quant_config = None
            if quantization == "4bit":
                try:
                    from transformers import BitsAndBytesConfig
                    quant_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=torch.float16,
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_quant_type="nf4",
                    )
                except Exception:
                    quant_config = None
                    quantization = "fp16"

            try:
                tokenizer = AutoTokenizer.from_pretrained(
                    self.config.model_id,
                    trust_remote_code=True,
                )
                kwargs: dict[str, Any] = {
                    "trust_remote_code": True,
                    "device_map": "auto",
                }
                if quant_config is not None:
                    kwargs["quantization_config"] = quant_config
                else:
                    kwargs["torch_dtype"] = torch.float16
                model = AutoModelForCausalLM.from_pretrained(
                    self.config.model_id,
                    **kwargs,
                )
                model.eval()
            except Exception as exc:
                self.state = ModelState(
                    loaded=False,
                    model_id=self.config.model_id,
                    mock=False,
                    quantization=quantization,
                    load_error=f"{type(exc).__name__}: {str(exc)[:200]}",
                )
                return self.state

            self._tokenizer = tokenizer
            self._model = model
            elapsed = int((time.monotonic() - started) * 1000)
            self.state = ModelState(
                loaded=True,
                model_id=self.config.model_id,
                mock=False,
                quantization=quantization,
                load_latency_ms=elapsed,
            )
            return self.state

    def generate_sql(
        self,
        user_query: str,
        schema: DatabaseSchema,
        locale: str | None = None,
    ) -> str:
        if self.state.mock or self._model is None or self._tokenizer is None:
            return _mock_sql(user_query, schema)
        try:
            import torch
        except Exception:
            return _mock_sql(user_query, schema)

        messages = build_chat_messages(user_query, schema, locale)
        try:
            text = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        except Exception:
            text = (
                f"{messages[0]['content']}\n\n{messages[1]['content']}\n\nSQL:\n"
            )
        inputs = self._tokenizer(text, return_tensors="pt")
        device = next(self._model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            output = self._model.generate(
                **inputs,
                max_new_tokens=self.config.max_new_tokens,
                do_sample=False,
                temperature=0.0,
                top_p=1.0,
                pad_token_id=self._tokenizer.eos_token_id,
            )
        generated_ids = output[0][inputs["input_ids"].shape[1]:]
        return self._tokenizer.decode(generated_ids, skip_special_tokens=True)


def _mock_sql(user_query: str, schema: DatabaseSchema) -> str:
    """Heuristic SQL for mock mode. Picks first table and a couple of columns."""
    if not schema.tables:
        return "SELECT 1 AS dummy"
    table = schema.tables[0]
    cols = [c.name for c in table.columns]
    q = user_query.lower()
    time_col = next(
        (c.name for c in table.columns if any(k in c.name.lower() for k in ("date", "month", "year", "time"))),
        None,
    )
    measure_col = next(
        (
            c.name
            for c in table.columns
            if c.sql_type
            and any(t in c.sql_type.lower() for t in ("int", "real", "numeric", "decimal", "float", "double"))
            and not (c.primary_key or c.name.lower().endswith("_id") or c.name.lower() == "id")
        ),
        None,
    )
    if any(k in q for k in ("динамик", "тренд", "по месяц", "trend", "over time")) and time_col and measure_col:
        return (
            f'SELECT {time_col} AS {time_col}, SUM({measure_col}) AS {measure_col} '
            f'FROM "{table.name}" GROUP BY {time_col} ORDER BY {time_col}'
        )
    if any(k in q for k in ("топ", "top", "наибольш", "лучш")) and measure_col:
        dim_col = next(
            (c.name for c in table.columns if c.name != measure_col and not c.primary_key),
            cols[0],
        )
        return (
            f'SELECT {dim_col}, SUM({measure_col}) AS {measure_col} '
            f'FROM "{table.name}" GROUP BY {dim_col} ORDER BY {measure_col} DESC LIMIT 10'
        )
    select_cols = ", ".join(cols[:5]) if cols else "*"
    return f'SELECT {select_cols} FROM "{table.name}" LIMIT 50'
