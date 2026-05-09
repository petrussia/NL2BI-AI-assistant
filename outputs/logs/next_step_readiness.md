# Next Step Readiness

Updated: 2026-04-25T15:46:40.278409+00:00

## Status
- B0 EX (smoke10): 1.0000
- B1 EX (smoke10): 1.0000
- Winner on smoke10: tie

## Readiness
- Ready for smoke25 (B0 and B1 rerun on the existing smoke_25 subset): **yes**
- Ready for B2 (Plan->SQL with schema/domain retrieval, validation, repair, exec-guided selection): **no**

## Remaining blockers for B2
- Planner module (JSON Plan) is not implemented yet.
- Retrieval indexes for schema and domain docs are not built.
- Validation and SQL repair loop not integrated.

## Recommendation
smoke25 for B0 and B1 (cheap, gives a less noisy EX comparison before any architectural change).

## Rationale
Both baselines are strong on n=10; n=25 reduces noise and surfaces failure modes that smoke10 hides.
