"""model_registry_v17 — single source of truth for Spider2 generator profiles.

Selects the HuggingFace model id + load kwargs based on a short alias.
Used by Colab-side runners to swap models without rewriting the runner.

Aliases (per Phase 17 plan):
- qwen2_5_coder_7b           — Phase 11–16 baseline (legacy comparator)
- qwen3_14b_sample20         — STAGE B fast baseline
- mistral_small_32_24b_bnb4  — STAGE C strong non-Qwen baseline (4-bit NF4, ~12-14 GB)
- mistral_small_24b_bf16     — STAGE C BF16 variant (~48 GB, A100-80GB only)
- qwen3_coder_30b_bf16       — STAGE D main run (BF16 full precision, A100 80GB)
- qwen3_coder_30b_fp8        — STAGE D fallback if BF16 OOM / unstable
- qwen2_5_coder_32b_awq      — last-resort historical fallback (AWQ)
- qwen2_5_coder_32b_gptq_int4 — last-resort historical fallback (GPTQ)

Each profile returns:
  {
    "alias": str,
    "hf_id": str,
    "load_kwargs": dict — passed to AutoModelForCausalLM.from_pretrained,
    "extra_pip": list[str] — packages required at runtime (autoawq, bitsandbytes, ...),
    "max_new_tokens_default": int,
    "non_thinking_mode": bool — Qwen3 family needs this off for SQL gen,
    "notes": str,
  }

The Colab-side runner reads `_MODEL_ALIAS` global (set by launcher) and
calls `get_profile(alias)` to obtain load kwargs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelProfile:
    alias: str
    hf_id: str
    load_kwargs: dict = field(default_factory=dict)
    extra_pip: list = field(default_factory=list)
    max_new_tokens_default: int = 800
    non_thinking_mode: bool = True   # Qwen3 family: do NOT enable thinking for SQL
    notes: str = ''


REGISTRY: dict[str, ModelProfile] = {
    # ----- Legacy / historical -----
    'qwen2_5_coder_7b': ModelProfile(
        alias='qwen2_5_coder_7b',
        hf_id='Qwen/Qwen2.5-Coder-7B-Instruct',
        load_kwargs={'torch_dtype': 'bfloat16', 'device_map': 'auto',
                       'trust_remote_code': True},
        max_new_tokens_default=800,
        notes='Phase 11-16 baseline. ~14GB BF16. Used as legacy comparator.',
    ),

    # ----- STAGE B: fast baseline -----
    'qwen3_14b_sample20': ModelProfile(
        alias='qwen3_14b_sample20',
        hf_id='Qwen/Qwen3-14B',
        load_kwargs={'torch_dtype': 'bfloat16', 'device_map': 'auto',
                       'trust_remote_code': True},
        max_new_tokens_default=800,
        non_thinking_mode=True,
        notes='Cheap baseline. ~28 GB BF16. Use enable_thinking=False in chat template.',
    ),

    # ----- STAGE C: strong non-Qwen baseline -----
    # NOTE: Original target was Mistral-Small-3.2-24B-Instruct-2506 but that ships
    # as Mistral3Config (multimodal-style) and is NOT registered with
    # AutoModelForCausalLM in transformers 5.0. Swap-in is
    # Mistral-Small-24B-Instruct-2501 — same parameter count, same family, but
    # plain text-only MistralConfig. Same role as a strong non-Qwen baseline.
    'mistral_small_32_24b_bnb4': ModelProfile(
        alias='mistral_small_32_24b_bnb4',
        hf_id='mistralai/Mistral-Small-24B-Instruct-2501',
        load_kwargs={
            'device_map': 'auto', 'trust_remote_code': True,
            'load_in_4bit': True,
            '_bnb_config': {
                'load_in_4bit': True,
                'bnb_4bit_quant_type': 'nf4',
                'bnb_4bit_compute_dtype': 'bfloat16',
                'bnb_4bit_use_double_quant': True,
            },
        },
        extra_pip=['bitsandbytes>=0.43'],
        max_new_tokens_default=800,
        notes=('4-bit NF4 via bitsandbytes. ~12-14 GB VRAM with quant. '
                 'hf_id swapped Mistral-Small-3.2 -> 2501 because 3.2 ships '
                 'as Mistral3Config and AutoModelForCausalLM in transformers 5.0 '
                 'does not register it.'),
    ),
    # Full-precision variant for the A100 80GB run; prefer this when VRAM is free.
    'mistral_small_24b_bf16': ModelProfile(
        alias='mistral_small_24b_bf16',
        hf_id='mistralai/Mistral-Small-24B-Instruct-2501',
        load_kwargs={'torch_dtype': 'bfloat16', 'device_map': 'auto',
                       'trust_remote_code': True},
        max_new_tokens_default=800,
        non_thinking_mode=False,
        notes='BF16 ~48 GB. Pure-text MistralConfig. Strong non-Qwen baseline on A100 80GB.',
    ),

    # ----- STAGE D: main run -----
    'qwen3_coder_30b_bf16': ModelProfile(
        alias='qwen3_coder_30b_bf16',
        hf_id='Qwen/Qwen3-Coder-30B-A3B-Instruct',
        load_kwargs={'torch_dtype': 'bfloat16', 'device_map': 'auto',
                       'trust_remote_code': True},
        max_new_tokens_default=900,
        non_thinking_mode=True,
        notes=('30B MoE with 3B active. BF16 weights ~60 GB; fits A100 80GB '
                 'comfortably. transformers >= 4.51 required.'),
    ),
    'qwen3_coder_30b_fp8': ModelProfile(
        alias='qwen3_coder_30b_fp8',
        hf_id='Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8',
        load_kwargs={'torch_dtype': 'auto', 'device_map': 'auto',
                       'trust_remote_code': True},
        max_new_tokens_default=900,
        non_thinking_mode=True,
        notes=('FP8 official quant. ~30 GB VRAM weights. Fallback when BF16 '
                 'is too tight on prompt budget.'),
    ),

    # ----- Last-resort / historical -----
    'qwen2_5_coder_32b_awq': ModelProfile(
        alias='qwen2_5_coder_32b_awq',
        hf_id='Qwen/Qwen2.5-Coder-32B-Instruct-AWQ',
        load_kwargs={'torch_dtype': 'auto', 'device_map': 'auto',
                       'trust_remote_code': True},
        extra_pip=['autoawq>=0.2.6'],
        max_new_tokens_default=900,
        notes='AWQ INT4 ~18 GB VRAM. Use only if Qwen3 path is unavailable.',
    ),
    'qwen2_5_coder_32b_gptq_int4': ModelProfile(
        alias='qwen2_5_coder_32b_gptq_int4',
        hf_id='Qwen/Qwen2.5-Coder-32B-Instruct-GPTQ-Int4',
        load_kwargs={'torch_dtype': 'auto', 'device_map': 'auto',
                       'trust_remote_code': True},
        extra_pip=['auto-gptq>=0.7'],
        max_new_tokens_default=900,
        notes='GPTQ INT4 ~18 GB VRAM. Last resort.',
    ),
}


def get_profile(alias: str) -> ModelProfile:
    if alias not in REGISTRY:
        raise KeyError(f'unknown model alias {alias!r}; available: {sorted(REGISTRY)}')
    return REGISTRY[alias]


def list_aliases() -> list:
    return sorted(REGISTRY.keys())


def load_model_and_tokenizer(alias: str):
    """Concrete loader. Resolves the dtype/quant config, calls HuggingFace.

    Returns (tokenizer, model, profile). Raises on failure (caller must
    decide whether to fall back to a different alias).
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    prof = get_profile(alias)
    print(f'LOAD {alias}  hf_id={prof.hf_id}', flush=True)

    tok_kwargs = {'trust_remote_code': prof.load_kwargs.get('trust_remote_code', True)}
    tok = AutoTokenizer.from_pretrained(prof.hf_id, **tok_kwargs)

    # Resolve dtype string → torch dtype
    lk = dict(prof.load_kwargs)
    bnb_cfg = lk.pop('_bnb_config', None)
    if isinstance(lk.get('torch_dtype'), str):
        s = lk['torch_dtype']
        if s == 'bfloat16': lk['torch_dtype'] = torch.bfloat16
        elif s == 'float16': lk['torch_dtype'] = torch.float16
        elif s == 'auto': lk['torch_dtype'] = 'auto'

    if bnb_cfg:
        from transformers import BitsAndBytesConfig
        lk.pop('load_in_4bit', None)
        bnb = BitsAndBytesConfig(
            load_in_4bit=bnb_cfg['load_in_4bit'],
            bnb_4bit_quant_type=bnb_cfg['bnb_4bit_quant_type'],
            bnb_4bit_compute_dtype=(torch.bfloat16
                                       if bnb_cfg['bnb_4bit_compute_dtype'] == 'bfloat16'
                                       else torch.float16),
            bnb_4bit_use_double_quant=bnb_cfg['bnb_4bit_use_double_quant'],
        )
        lk['quantization_config'] = bnb

    mdl = AutoModelForCausalLM.from_pretrained(prof.hf_id, **lk)
    mdl.eval()

    # VRAM footprint snapshot
    if torch.cuda.is_available():
        free, total = torch.cuda.mem_get_info()
        print(f'VRAM after load: free={free/1024**3:.1f} GB / total={total/1024**3:.1f} GB', flush=True)

    return tok, mdl, prof


def chat_generate(tok, mdl, prompt: str, *, max_new: int = 800,
                     non_thinking: bool = True) -> str:
    """Single-prompt deterministic generate. Used by all v17 runners."""
    import torch
    msgs = [{'role': 'user', 'content': prompt}]
    extra = {}
    if non_thinking:
        # Qwen3 chat template supports an `enable_thinking` kwarg; fall back
        # silently for tokenizers that don't.
        extra['enable_thinking'] = False
    try:
        enc = tok.apply_chat_template(msgs, return_tensors='pt',
                                            add_generation_prompt=True,
                                            return_dict=True, **extra)
    except TypeError:
        enc = tok.apply_chat_template(msgs, return_tensors='pt',
                                            add_generation_prompt=True,
                                            return_dict=True)
    enc = {k: v.to(mdl.device) for k, v in enc.items()}
    with torch.no_grad():
        out = mdl.generate(**enc, max_new_tokens=max_new,
                              do_sample=False, temperature=0.0,
                              pad_token_id=tok.eos_token_id)
    gen = out[0][enc['input_ids'].shape[1]:]
    return tok.decode(gen, skip_special_tokens=True)
