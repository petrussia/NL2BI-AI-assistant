# Acknowledgments

This dossier is the product of a year-long research effort. The work would not have been possible without the contributions of several individuals, institutions, open-source communities, and computing infrastructure providers. This appendix records those contributions in the conventional thesis form.

## Academic supervision

The thesis is written under the supervision of the HSE (Higher School of Economics) faculty of computer science. I am grateful to my thesis advisor for the early framing of the research questions — particularly the insistence that the thesis should target *open-weight ≤30B* systems as the comparison class, rather than the closed-source frontier. That scoping decision shaped every subsequent architectural choice, and made the eventual story of "scaffolding matters more than scale" empirically tractable.

I am also grateful to the HSE thesis committee for the staged feedback on the dossier's structure. The Stage-1 reviewers' suggestion to introduce metric definitions before progression tables, and the Stage-5 reviewers' insistence that the Phase 28 F2a regression be documented as prominently as the Phase 27 breakthrough, are reflected in the current dossier organisation.

## Research community

This dossier sits on a substantial body of community work. Three specific debts are worth naming.

First, the Spider 2.0 authors (Lei et al. 2024 and the XLang AI consortium) for designing and releasing a benchmark that genuinely tests real-world enterprise SQL generation. Spider 2.0's design choices — live Snowflake databases, manifest-aware DBT projects, evidence-row reasoning — set the empirical ceiling for the thesis's distinctive claim. The decision to evaluate against live database state, rather than against a static dump, is what made the Phase 27 grounding work interesting; without that design choice the cross-DB identifier drift problem would not have existed as a research question.

Second, the Spider-Agent and ReFoRCE authors for being the architectural neighbours against which our open-weight numbers are positioned. The Spider-Agent + Qwen3-Coder published number (31.08 %) is the empirical anchor for the "open-weight ≤30B Spider 2.0 ceiling" claim that frames the thesis. ReFoRCE's reflection-based scaffolding informs the design space discussion in [02_RELATED_WORK/02_sota_systems_2024_2026.md](../02_RELATED_WORK/02_sota_systems_2024_2026.md).

Third, Wang et al. (arXiv:2601.08778) for the annotation-reliability audit that documented the 62.8 % Spider 2.0 audit-mismatch rate. That single paper changed how the thesis presents its Spider 2.0 numbers: every percentage point is now reported with explicit reference to the annotation-noise band, and the thesis's analytical caution about "small absolute differences on Spider 2.0" is methodologically grounded in their work.

## Open-source contributors

The thesis relies on a dense layer of open-source software. The infrastructure-level acknowledgements:

* **The Qwen team** at Alibaba DAMO for releasing the Qwen3-Coder and Qwen2.5-Coder model families under the Qwen License. The 30B-A3B MoE pattern in Qwen3-Coder is the architectural choice that makes 30B-class planning tractable inside a single Colab A100 80 GB session — without that activation pattern, the thesis would have had to choose either a much smaller planner or a much larger compute budget.
* **The Hugging Face team** for the `transformers` library that hosts our inference runtime, and for the Hugging Face Hub that distributes the model weights.
* **The SQLGlot project** (Toby Mao) for the parser and AST manipulation library on which both the F1 identifier guard and the F4 date-cast wrapper depend. The discovery in Phase 28 that Snowflake's `DATE_TRUNC` parses as `exp.TimestampTrunc` rather than `exp.DateTrunc` — a single line of code, but the difference between the F4 wrapper working and not working — illustrates how deeply load-bearing SQLGlot's design choices are for our system.
* **The dbt Labs team** for `dbt-core` and the engine adapters. Phase 31's planned `dbt parse` pre-check exists entirely because dbt's parse stage is exposed as a callable subcommand; without that interface the project-level integration would not be tractable.
* **The PyTorch team** for the underlying CUDA tensor library.
* **The Snowflake Connector for Python and Google Cloud BigQuery Python client maintainers** for the engine adapters our pipeline binds against.

## Compute infrastructure

The dossier's numbers were produced on Google Colab Pro+ subscription compute, primarily A100 80 GB instances. The Colab platform's session-isolated runtime is not designed for the multi-hour FULL runs we ended up needing; the resume scaffolding documented in [08_CUSTOM_TOOLS/09_resilience_patterns.md](../08_CUSTOM_TOOLS/09_resilience_patterns.md) and the bringup memory file at `memory/colab_session_bringup.md` is the operational adaptation that made the FULL runs possible at all.

I am grateful to Google Cloud for the Colab Pro+ infrastructure and to Cloudflare for the free Cloudflare Tunnel service that connects our agent-side scripts to the Colab kernel. The Cloudflare Tunnel's 502-on-large-payload limitation is documented as a known constraint, and the upload-splitting pattern that works around it ([08_CUSTOM_TOOLS/09_resilience_patterns.md](../08_CUSTOM_TOOLS/09_resilience_patterns.md) §3) is an instance of working within infrastructure constraints rather than against them.

The Spider 2.0 Snowflake account hosting the live database state was provided by the Spider 2.0 maintainers under their academic-research access programme. I am grateful for that access; without it the Spider2-Snow lane's 547-task evaluation would not be reproducible.

## Practical contributors and reviewers

Several colleagues at HSE provided practical input that shaped the dossier. Specific contributions:

* Two HSE peers reviewed early drafts of [04_ARCHITECTURE/](../04_ARCHITECTURE/) and provided the feedback that the original "8-stage pipeline diagram" was unreadable; the simpler 6-stage rendering in [04_ARCHITECTURE/11_full_pipeline_diagram.md](../04_ARCHITECTURE/11_full_pipeline_diagram.md) is a direct response.
* A colleague familiar with dbt project structure caught an early misclassification in the Spider2-DBT failure-band taxonomy — initially I had merged `dbt_test_failed` into `ran_ok_but_score_zero`, which obscured the fact that the test-failed band carries the highest information-density signal for Phase 31's design.
* Multiple readers across the thesis committee insisted on the catalog-probe methodology (Phase 28 F2a falsification) being elevated to "Claim 3 of the thesis", rather than being buried in the Phase 28 narrative. That promotion reflects their judgement that the methodological discipline is a transferable contribution, not just a project-specific anecdote.

## A specific note on the AI-assisted research process

The thesis was produced with substantial AI-assisted research and writing support, primarily through extended conversations with large language models acting as research collaborators. This included Phase planning, architectural critique, literature triangulation, error-taxonomy generation, and the drafting of the dossier files themselves. The AI assistance is acknowledged for transparency; the substantive research decisions, the empirical runs, the methodological choices, the failure-mode analyses, and the conclusions drawn from the empirical evidence are the author's responsibility. The Phase 27 F1 stack and the Phase 28 F2a falsification narrative — the two most distinctive contributions of the thesis — were arrived at through a combination of AI-assisted hypothesis enumeration, manual catalog inspection, and empirical pilot iteration. Where the AI assistance materially shaped a claim (e.g. the framing of the Wang et al. annotation-reliability paper as the "metric-granularity bound"), the framing is attributed in the relevant dossier section rather than buried here.

## Personal note

A research project of this duration is difficult to sustain without personal support outside the academic context. I am grateful to my family and friends for their patience during the many months when the thesis displaced more conventional priorities — particularly during the Phase 23 OOM-diagnostic week and the Phase 28 F2a regression weekend, both of which required the kind of intensive empirical iteration that does not fit cleanly into a normal weekly schedule.

I am also grateful to the Colab Pro+ runtime for repeatedly dying at inconvenient moments. The kernel-death recoveries documented in `memory/colab_session_bringup.md` are not a feature I planned to develop, but they ended up being one of the more practically useful artefacts of the project. There is a thesis-internal joke that "Phase 28 was completed *despite* infrastructure, not *because of* infrastructure"; that joke is also an acknowledgement of the cumulative impact of small infrastructure frictions on long-running research projects, and a quiet recommendation to future readers to budget more recovery-engineering time than they think they will need.

## Errors and omissions

Despite the contributions above, this dossier inevitably contains errors. Where the dossier makes a specific empirical claim, the claim is traceable to a specific run output indexed in [10_REFERENCES/02_internal_phase_reports.md](../10_REFERENCES/02_internal_phase_reports.md), and errors in the empirical numbers can be diagnosed against those traces. Where the dossier makes an architectural claim, the claim is traceable to a specific code excerpt in [03_key_code_excerpts.md](03_key_code_excerpts.md) or to a specific tool documentation file in [08_CUSTOM_TOOLS/](../08_CUSTOM_TOOLS/). Where the dossier makes a methodological claim — particularly the claims about annotation reliability, the closed-set planner's design rationale, or the catalog-probe methodology — the responsibility for the claim's accuracy lies with the author. The full set of acknowledged contributors listed above are gratefully credited for the support that made the work possible; any remaining errors are mine alone.
