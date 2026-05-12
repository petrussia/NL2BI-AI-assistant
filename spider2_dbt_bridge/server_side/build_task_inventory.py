#!/usr/bin/env python3
"""build_task_inventory.py — emit one JSON per task with structural facts
that the local taxonomy classifier needs. Mode B (offline labeling): may
read gold spec; output is for taxonomy CSV only, never for prompt building.
"""
import json, os, sys
from pathlib import Path

ROOT = Path('/home/denis/dbt/vendor/Spider2/spider2-dbt')
EXAMPLES = ROOT / 'examples'
TASK_JSONL = EXAMPLES / 'spider2-dbt.jsonl'
GOLD_JSONL = ROOT / 'evaluation_suite' / 'gold' / 'spider2_eval.jsonl'


def _summarize_dir(d: Path) -> dict:
    if not d.exists() or not d.is_dir():
        return {'exists': False}
    out = {'exists': True}
    out['has_dbt_project_yml'] = (d / 'dbt_project.yml').exists()
    out['has_profiles_yml'] = (d / 'profiles.yml').exists()
    out['has_packages_yml'] = (d / 'packages.yml').exists()
    out['has_macros_dir'] = (d / 'macros').is_dir()
    out['has_seeds_dir'] = (d / 'seeds').is_dir()
    out['has_snapshots_dir'] = (d / 'snapshots').is_dir()
    out['has_tests_dir'] = (d / 'tests').is_dir()
    models = d / 'models'
    out['has_models_dir'] = models.is_dir()
    sql_files = list(models.rglob('*.sql')) if models.is_dir() else []
    yml_files = list(models.rglob('*.yml')) if models.is_dir() else []
    out['model_sql_count'] = len(sql_files)
    out['yml_count'] = len(yml_files)
    out['model_files'] = sorted(p.relative_to(d).as_posix() for p in sql_files)
    return out


def _classify_file_body(p: Path) -> dict:
    """Return facts about a model SQL file: empty / stub / substantive."""
    try:
        text = p.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return {'readable': False}
    n = len(text.strip())
    upper = text.upper()
    return {
        'readable': True,
        'chars': n,
        'is_empty': n == 0,
        'has_select': 'SELECT' in upper,
        'has_with': upper.lstrip().startswith('WITH'),
        'has_todo': 'TODO' in upper or 'FIXME' in upper or 'STUB' in upper,
        'has_ref_macro': '{{ ref(' in text or '{{ref(' in text,
        'has_source_macro': '{{ source(' in text or '{{source(' in text,
        'lines': text.count('\n') + 1,
    }


def main() -> int:
    if not TASK_JSONL.exists():
        print(f'FAIL: {TASK_JSONL} not found'); return 2
    if not GOLD_JSONL.exists():
        print(f'WARN: {GOLD_JSONL} not found'); gold_map = {}
    else:
        gold_map = {}
        for ln in GOLD_JSONL.open(encoding='utf-8'):
            try:
                e = json.loads(ln)
                gold_map[e.get('instance_id')] = e
            except Exception:
                continue

    rows = []
    for ln in TASK_JSONL.open(encoding='utf-8'):
        try:
            it = json.loads(ln)
        except Exception:
            continue
        iid = it.get('instance_id', '')
        instr = it.get('instruction', '')
        ex_dir = EXAMPLES / iid
        ex = _summarize_dir(ex_dir)

        # Gold target (Mode B labeling only)
        gold = gold_map.get(iid) or {}
        evals = gold.get('evaluation') or {}
        evals = evals if isinstance(evals, list) else [evals]
        gold_targets, gold_dbs, gold_cond_cols = [], [], []
        for em in evals:
            params = em.get('parameters') or {}
            for t in (params.get('condition_tabs') or []):
                if t and t not in gold_targets: gold_targets.append(t)
            gd = params.get('gold')
            if gd: gold_dbs.append(gd)
            for cc in (params.get('condition_cols') or []):
                gold_cond_cols.append(cc)

        # Likely target file in upstream
        likely_target_files = []
        target_existed = False
        for t in gold_targets:
            candidates = []
            if ex.get('has_models_dir'):
                models_dir = ex_dir / 'models'
                for p in models_dir.rglob('*.sql'):
                    stem = p.stem
                    if stem.lower() == t.lower():
                        candidates.append(p.relative_to(ex_dir).as_posix())
                        target_existed = True
                    elif t.lower() in stem.lower() or stem.lower() in t.lower():
                        candidates.append(p.relative_to(ex_dir).as_posix())
            likely_target_files.extend(candidates)

        # Body classification of likely targets
        target_bodies = []
        for rel in likely_target_files[:3]:
            target_bodies.append({
                'path': rel,
                **_classify_file_body(ex_dir / rel),
            })

        rows.append({
            'instance_id': iid,
            'instruction': instr[:300],
            'instruction_short': instr[:120],
            'example_dir': str(ex_dir),
            'inventory': ex,
            'gold_target_tables': gold_targets,
            'gold_dbs': gold_dbs,
            'gold_cond_cols': gold_cond_cols,
            'likely_target_files': likely_target_files,
            'target_file_existed_in_upstream': target_existed,
            'target_bodies': target_bodies,
        })

    print(json.dumps(rows, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
