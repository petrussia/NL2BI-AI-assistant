# Planner v4 diagnosis on BIRD full (Qwen2.5-Coder-7B)

**N** = 500; **planner_used** = 500; **plan_valid** = 2 (0.40%); **fallback_used** = 498 (99.60%); **execution_match** = 98 (19.60%).

## Fallback reasons

```json
{
  "invalid_plan": 498,
  "": 2
}
```

## Plan-object presence

```json
{
  "no_plan_obj": 498,
  "has_plan_obj": 2
}
```

## Repair-count distribution

```json
{
  "0": 500
}
```

## Diagnosis

- The v4 planner produces plans that fail JSON-Schema validation in ~99.6% of BIRD items.
- All such items fall back to **B1_v3** (linker only), so B2_v4 effectively degrades to B1_v3 + planner overhead.
- Execution match rate is therefore close to B1_v3, not above it.

## Recommendation

- Either soften the v4 plan schema (relax required fields; accept partial plans) **or** revert to v3 plan template for BIRD.
- Alternatively, use B3_v4 (retrieval + evidence) as the BIRD production baseline — it dominates both B0 and B2_v4 by a large margin on full BIRD.

## Sample of valid plans (if any)

```json
[
  {
    "idx": 398,
    "question": "What is the most common bond type?",
    "plan": {
      "intent": "select_aggregate",
      "tables": [
        "bond"
      ],
      "operations": [
        "COUNT",
        "GROUP BY",
        "ORDER BY DESC",
        "LIMIT 1"
      ],
      "columns": [
        "bond_type"
      ],
      "answer_shape": "scalar"
    },
    "sql": "SELECT bond_type FROM bond GROUP BY bond_type ORDER BY COUNT(*) DESC LIMIT 1;",
    "em": true
  },
  {
    "idx": 464,
    "question": "What is the grade span offered in the school with the highest longitude?",
    "plan": {
      "intent": "select_other",
      "tables": [
        "schools"
      ],
      "operations": [
        "ORDER BY",
        "LIMIT"
      ],
      "columns": [
        "GSoffered"
      ],
      "order_by": [
        "Longitude DESC"
      ],
      "limit": 1,
      "answer_shape": "scalar"
    },
    "sql": "SELECT GSoffered FROM schools ORDER BY Longitude DESC LIMIT 1;",
    "em": false
  }
]
```
