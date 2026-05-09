#!/usr/bin/env python3
"""analyze_tasks.py — for each Spider2-DBT task, summarize what gold expects:
  - which condition_tabs (target tables to populate)
  - how many target tables, columns
  - whether the example dir has those tables already as model files

Output: JSONL one line per task, sorted by 'tractability heuristic'.
"""
import json
from pathlib import Path

ROOT = Path('/home/denis/dbt/vendor/Spider2/spider2-dbt')
GOLD = ROOT / 'evaluation_suite' / 'gold' / 'spider2_eval.jsonl'
EXAMPLES = ROOT / 'examples'
TASK_JSONL = EXAMPLES / 'spider2-dbt.jsonl'


def main():
    tasks = {}
    for ln in TASK_JSONL.open(encoding='utf-8'):
        try:
            it = json.loads(ln)
            tasks[it['instance_id']] = it
        except Exception: continue

    out = []
    for ln in GOLD.open(encoding='utf-8'):
        try:
            g = json.loads(ln)
        except Exception: continue
        iid = g.get('instance_id')
        evals = g.get('evaluation') or {}
        evals = evals if isinstance(evals, list) else [evals]
        cond_tabs = []; cond_cols = []
        gold_dbs = []
        for em in evals:
            p = em.get('parameters') or {}
            cond_tabs.extend(p.get('condition_tabs') or [])
            cond_cols.extend(p.get('condition_cols') or [])
            gd = p.get('gold')
            if gd: gold_dbs.append(gd)
        ex_dir = EXAMPLES / iid
        models_dir = ex_dir / 'models'
        existing_models = []
        if models_dir.exists():
            for p in models_dir.rglob('*.sql'):
                existing_models.append(p.relative_to(models_dir).as_posix())
        # Tractability heuristic: 1 condition table + few cols + tables NOT yet present in models/
        n_target_tabs = len(set(cond_tabs))
        max_cols = max((len(c) for c in cond_cols), default=0)
        tabs_already_present = sum(
            1 for t in cond_tabs
            if any(p.endswith(f'{t}.sql') or p.endswith(f'{t}.SQL') for p in existing_models))
        out.append({
            'instance_id': iid,
            'instruction_short': (tasks.get(iid, {}).get('instruction', '') or '')[:120],
            'gold_dbs': sorted(set(gold_dbs)),
            'n_target_tabs': n_target_tabs,
            'target_tabs': sorted(set(cond_tabs)),
            'max_cond_cols': max_cols,
            'existing_models_n': len(existing_models),
            'tabs_already_present': tabs_already_present,
            # Lower is more tractable
            'tractability_rank': (n_target_tabs * 100 + max_cols
                                    - tabs_already_present * 5),
        })

    out.sort(key=lambda r: r['tractability_rank'])
    for r in out:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == '__main__':
    main()
