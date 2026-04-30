# 06 — Personal contribution of Shubin Denis Alexeevich

_Generated: 2026-04-30T12:28:47.260219+00:00_

## In-scope (Shubin)
- **Architecture of the NL→SQL extraction subsystem:** B0..B4 baselines, plan schema, retrieval, validation, repair, analytics handoff payload contract.
- **Implementation:** all 13+ modules under `repo/src/evaluation/` (baselines.py, baselines_b2.py, baselines_b2_v1.py, **baselines_b2_v2.py**, baselines_b3.py, baselines_b3_v1.py, **baselines_b3_v2.py**, baselines_b4.py, baselines_b4_final.py, **baselines_b4_v2.py**, postprocess.py, query_analysis.py, retrieval.py).
- **Plan schemas:** `repo/docs/plan_schema.json`, `repo/docs/plan_schema_v1.json`.
- **Experimental evaluation:** all 25+ baseline runs across smoke_10, smoke_25, multidb_30 and 4 models, with full predictions/metrics/error-cases artefacts.
- **Honest negative-result analysis:** `outputs/logs/final_negative_result_analysis.md`, `outputs/logs/final_scientific_findings.md`, `outputs/logs/multidb30_scientific_readout.md`.
- **Documentation:** all bundled docs under `outputs/docs/` (architecture_document.md, functional_specification.md, io_contracts.md, use_cases_and_scenarios.md, testing_methodology.md, operations_manual.md, installation_and_runtime.md).
- **Tooling:** the bridge architecture (`tools/exec_remote.py` + Colab Flask + cloudflared tunnel + `tools/remote_scripts/` ladder).
- **Mandatory model block:** Qwen-Coder-7B / Qwen-Instruct-7B / Llama-3.1-8B-Instruct evaluations + Llama unblock + DeepSeek environmental blocker artifact.

## Out-of-scope (NOT Shubin — belongs to Petukhov, do not claim)
- **Analytics visualisation subsystem** (BI dashboards, charts, end-user UI) — owned by Petukhov; the only interface is the analytics handoff payload contract documented in `outputs/docs/io_contracts.md`.
- **Practice-package narrative** for the partner organisation — owned by Petukhov.
- Any claims about "the system as a whole" should be split into "extraction (Shubin)" and "presentation (Petukhov)".

## Boundary contract between Shubin and Petukhov
The boundary is a single JSON+CSV payload (the AnalyticsPayload v1) emitted by `repo/src/evaluation/postprocess.py`. The schema is in `outputs/docs/io_contracts.md`. Shubin is responsible for emitting it; Petukhov is responsible for consuming it. Any change to the schema requires both sides to agree.
