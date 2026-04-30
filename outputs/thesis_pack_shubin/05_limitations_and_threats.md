# 05 — Limitations and threats to validity (Shubin)

_Generated: 2026-04-30T12:28:47.260219+00:00_

## Limitations
1. **Single benchmark family.** All experiments use Spider (and a multi-DB subset of it). Conclusions about "direct generation dominates layered planning" may not hold on benchmarks with multi-step reasoning, ambiguous schemas, or real domain corpora (BIRD, ScienceBench, in-house enterprise schemas).
2. **Single hardware tier.** All Qwen-Coder-7B / Qwen-Instruct-7B / Llama-3.1-8B / Qwen-Coder-14B runs were on NVIDIA L4 24 GB with 4-bit nf4 bitsandbytes quantisation. Higher-precision (fp16/bf16) runs on H100/A100 may shift absolute EX numbers; relative ordering of baselines is expected to be stable.
3. **Subsets are small.** smoke_10 (n=10), smoke_25 (n=25), multidb_30 (n=30). Confidence intervals are wide; we report exact match counts, not statistical significance.
4. **Plan schema is project-defined,** not a community standard. Generalising the plan→SQL pattern requires aligning the schema with downstream consumers (analytics handoff payload, BI tools). This is documented in `repo/docs/plan_schema_v1.json` and `outputs/docs/io_contracts.md`.
5. **No human evaluation.** EX is a result-set match metric; it cannot distinguish two SQL queries that return the same rows but differ in cost, intent fidelity, or auditability.

## Threats to validity
1. **Construct validity.** EX rewards "correct rows", not "correct SQL". A query that exploits a schema quirk to return correct rows by coincidence is scored equally with a semantically faithful query.
2. **Internal validity.** B0/B1 use a single greedy decode (`do_sample=False`). B4 family uses 3-cand sampling. Same-model deltas may partially reflect decoding strategy differences, not pure pipeline differences.
3. **External validity.** Spider is closed-domain academic benchmark with hand-crafted schemas. Real enterprise BI workloads (joins across 30+ tables, fuzzy entity matching, ambiguous business terms) likely behave differently.
4. **Researcher bias.** All baselines were authored by the same person; prompt engineering for B0/B1 may be more polished than for B2/B3/B4. We mitigated this with consistent schema-text formatting and identical tokenisation pipeline.

## Mitigations applied
- **All predictions are saved per-item** with raw model output; readers can re-run EX with a different metric.
- **All metrics are versioned by run_id** in `outputs/metrics/`.
- **Negative results are documented honestly** in `outputs/logs/final_negative_result_analysis.md` and `outputs/logs/final_scientific_findings.md`.
- **Model blockers are documented as separate artifacts** with reproduction steps, not as silent gaps.
