# Notebook Audit

Local notebook: `D:\HSE\??????\NL2BI-AI-assistant\notebooks\example.ipynb`

| # | Cell id | Type | Purpose | Executed | Output | Error |
|---|---|---|---|---|---|---|
| 0 | `b0-title` | markdown | B0 notebook title | no | no | no |
| 1 | `b0-runtime-local-audits` | code | runtime, Google Drive, helper and notebook audit | no | no | no |
| 2 | `b0-assets-blockers-audit` | code | Spider audit, optional download, SQLite read checks | no | no | no |
| 3 | `b0-loaders-subsets` | code | loader validation and smoke subsets | no | no | no |
| 4 | `b0-inference-eval` | code | func_timeout, bitsandbytes, Qwen2.5-Coder-7B-Instruct B0 inference and EX eval | no | no | no |
| 5 | `b1-scaffold-ready` | code | create/check B1 scaffold only after B0 completed | no | no | no |
| 6 | `practice-artifacts-final` | code | update practical artifacts based on actual B0/B1 readiness | no | no | no |

Attention areas:
- Spider audit: `b0-assets-blockers-audit`
- B0 inference: `b0-inference-eval`
- func_timeout: `b0-inference-eval`
- model loading: `b0-inference-eval`
- metrics saving: `b0-inference-eval`
- practice artifacts: `practice-artifacts-final`
