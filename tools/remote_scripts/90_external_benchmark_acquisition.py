# Step X: acquire Spider 2.0-Lite + BIRD Mini-Dev from official public sources
# into Drive (NOT local). Build acquisition manifests with sha256 + sizes +
# timestamps. Build 30-example diverse processed slices for both. Document
# evaluation limitations honestly.

import csv
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.request
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
EXT_ROOT = PROJECT_ROOT / 'external_benchmarks'
EXT_ROOT.mkdir(parents=True, exist_ok=True)

S2_DIR = EXT_ROOT / 'spider2_lite'
BIRD_DIR = EXT_ROOT / 'bird_mini_dev'
for d in [S2_DIR, BIRD_DIR]:
    for sub in ['raw','processed','manifests']:
        (d/sub).mkdir(parents=True, exist_ok=True)

LOGS = PROJECT_ROOT / 'outputs' / 'logs'
LOGS.mkdir(parents=True, exist_ok=True)
NOW = dt.datetime.now(dt.timezone.utc).isoformat()


def sh(*args, cwd=None, timeout=600):
    return subprocess.run(list(args), cwd=cwd, capture_output=True,
                          text=True, timeout=timeout)


def sha256_of(p: Path):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


# ============================================================
# A. SPIDER 2.0-LITE
# ============================================================
print('=== Spider 2.0-Lite acquisition ===', flush=True)
S2_URL = 'https://github.com/xlang-ai/Spider2.git'
S2_RAW = S2_DIR / 'raw' / 'Spider2'

if not S2_RAW.exists():
    # Shallow clone — repo is large but most of it is databases we don't need
    print(f'cloning {S2_URL} (shallow) into {S2_RAW}', flush=True)
    r = sh('git', 'clone', '--depth', '1', '--filter=blob:none',
           '--sparse', S2_URL, str(S2_RAW), timeout=600)
    print('clone rc=', r.returncode, 'err=', r.stderr[-300:] if r.stderr else '')
    if r.returncode == 0:
        # sparse-checkout only the lite directory
        sh('git', '-C', str(S2_RAW), 'sparse-checkout', 'set', 'spider2-lite', timeout=120)
else:
    print(f'Spider2 repo already at {S2_RAW}; skipping clone')

# Locate spider2-lite tasks file
candidate_paths = [
    S2_RAW / 'spider2-lite' / 'spider2-lite.jsonl',
    S2_RAW / 'spider2-lite' / 'spider2lite.jsonl',
    S2_RAW / 'spider2-lite' / 'tasks.jsonl',
]
lite_jsonl = None
for c in candidate_paths:
    if c.exists():
        lite_jsonl = c
        break

# Fallback: glob search inside spider2-lite/
if lite_jsonl is None and (S2_RAW/'spider2-lite').exists():
    found = list((S2_RAW/'spider2-lite').rglob('*.jsonl'))
    if found:
        # Prefer the one that contains 'spider2' in name
        found.sort(key=lambda p: (0 if 'spider2' in p.name.lower() else 1, p.stat().st_size))
        lite_jsonl = found[0]

s2_manifest_md = LOGS / 'spider2_lite_acquisition.md'
s2_limitations = LOGS / 'spider2_lite_eval_limitations.md'

if lite_jsonl is None:
    s2_manifest_md.write_text(textwrap.dedent(f'''
    # Spider 2.0-Lite acquisition (FAILED)

    **Captured:** {NOW}
    **Source URL:** {S2_URL}
    **Method:** shallow git clone with sparse-checkout to `spider2-lite/`
    **Outcome:** could not locate `spider2-lite.jsonl` after clone.

    Investigate `{S2_RAW/"spider2-lite"}` manually; the repo layout may have changed.
    ''').strip()+'\n', encoding='utf-8')
    print('SPIDER2_LITE_ACQUISITION_FAILED — no jsonl found')
    s2_examples = []
else:
    # Read entries
    s2_examples = []
    with lite_jsonl.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                s2_examples.append(json.loads(line))
            except Exception:
                pass
    print(f'Spider2-Lite tasks loaded: {len(s2_examples)} from {lite_jsonl}')

    # Compute manifest stats
    lite_sha = sha256_of(lite_jsonl)
    lite_size = lite_jsonl.stat().st_size
    db_dist = Counter(ex.get('db_id') or ex.get('db') or 'unknown' for ex in s2_examples)

    s2_manifest = {
        'benchmark': 'Spider 2.0-Lite',
        'source_url': S2_URL,
        'official_site': 'https://spider2-sql.github.io/',
        'acquisition_method': 'shallow git clone + sparse-checkout',
        'downloaded_at_utc': NOW,
        'tasks_file': str(lite_jsonl.relative_to(EXT_ROOT)),
        'tasks_file_sha256': lite_sha,
        'tasks_file_bytes': lite_size,
        'n_tasks': len(s2_examples),
        'unique_dbs': len(db_dist),
        'license_note': 'Apache-2.0 per Spider2 LICENSE; see repo for details',
    }
    (S2_DIR/'manifests'/'spider2_lite_manifest.json').write_text(
        json.dumps(s2_manifest, indent=2), encoding='utf-8')

    # Build a 30-example diverse processed slice
    by_db = {}
    for i, ex in enumerate(s2_examples):
        dbid = ex.get('db_id') or ex.get('db') or ex.get('instance_id', '_').split('_')[0]
        by_db.setdefault(dbid, []).append((i, ex))

    selected = []
    db_keys = sorted(by_db.keys())
    # Round-robin pull to maximize DB coverage
    idx_per_db = {k: 0 for k in db_keys}
    while len(selected) < 30 and any(idx_per_db[k] < len(by_db[k]) for k in db_keys):
        for k in db_keys:
            if idx_per_db[k] < len(by_db[k]):
                i, ex = by_db[k][idx_per_db[k]]
                idx_per_db[k] += 1
                selected.append({
                    'idx': len(selected),
                    'original_id': ex.get('instance_id') or ex.get('id') or i,
                    'db_id': k,
                    'question': ex.get('question') or ex.get('instruction') or '',
                    'gold_sql': ex.get('query') or ex.get('sql') or ex.get('SQL') or '',
                    'source_split': 'spider2-lite',
                    'source_path': str(lite_jsonl.relative_to(EXT_ROOT)),
                    'extras': {k2: v for k2, v in ex.items()
                               if k2 not in ('db_id','db','instance_id','id','question','instruction','query','sql','SQL')},
                })
                if len(selected) >= 30: break

    out_slice = S2_DIR/'processed'/'spider2lite_30_diverse.json'
    out_slice.write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding='utf-8')

    # Audit
    sel_db_dist = Counter(s['db_id'] for s in selected)
    audit_md = LOGS / 'spider2lite_30_diverse_audit.md'
    has_gold = sum(1 for s in selected if s['gold_sql'])
    audit_md.write_text(textwrap.dedent(f'''
    # spider2lite_30_diverse audit

    **Captured:** {NOW}
    **Slice path:** `{out_slice.relative_to(PROJECT_ROOT)}`
    **N items:** {len(selected)}
    **Unique DBs:** {len(sel_db_dist)}
    **Items with gold_sql present:** {has_gold} / {len(selected)}

    ## Distribution by db_id
    | db_id | count |
    |---|---|
    ''').strip() + '\n' + '\n'.join(
        f'| `{k}` | {v} |' for k, v in sorted(sel_db_dist.items(), key=lambda x: (-x[1], x[0]))
    ) + '\n', encoding='utf-8')

    s2_manifest_md.write_text(textwrap.dedent(f'''
    # Spider 2.0-Lite acquisition

    **Captured:** {NOW}
    **Official source:** {S2_URL}
    **Official site:** https://spider2-sql.github.io/
    **Acquisition method:** shallow `git clone --depth 1 --filter=blob:none --sparse`, then `git sparse-checkout set spider2-lite`
    **Tasks file:** `{lite_jsonl.relative_to(EXT_ROOT)}`
    **SHA-256:** `{lite_sha}`
    **Size (bytes):** {lite_size}
    **N tasks loaded:** {len(s2_examples)}
    **Unique DBs:** {len(db_dist)}
    **License:** Apache-2.0 (per Spider2 repo LICENSE)

    ## Processed slice
    - `{out_slice.relative_to(PROJECT_ROOT)}` — 30 examples, max-diverse DB coverage (round-robin pull across distinct db_ids)

    ## Manifest JSON
    `{(S2_DIR/"manifests"/"spider2_lite_manifest.json").relative_to(PROJECT_ROOT)}`
    ''').strip()+'\n', encoding='utf-8')

    # Honest limitations note
    s2_limitations.write_text(textwrap.dedent(f'''
    # Spider 2.0-Lite — evaluation limitations

    **Captured:** {NOW}

    ## Why we cannot compute Execution Match (EX) on this slice from Colab

    Spider 2.0-Lite tasks reference databases hosted on **BigQuery / Snowflake / DuckDB-extensions** (depending on the task). Executing the gold SQL against these requires:
    - active credentials to the corresponding cloud data warehouse (BigQuery service account, Snowflake user/password, etc.); AND
    - the original tables loaded into that warehouse (Spider 2.0 distributes pointer references, not the data).

    Colab kernels do **not** carry these credentials and the project scope (NL→SQL extraction subsystem of Shubin) does not include provisioning a BigQuery/Snowflake account. **Therefore EX cannot be computed** on this slice from the current runtime.

    ## What we CAN do honestly
    1. Generate predicted SQL with each baseline (B0/B1/B2_v2) and each model (Qwen-Coder-7B, Llama-3.1-8B).
    2. Save predictions to `outputs/predictions/spider2lite_30_diverse_*` for inspection.
    3. Report **structural metrics** that are computable without execution:
       - non-empty SQL emission rate
       - SQL parser-validity (sqlglot)
       - mean SQL length (tokens)
       - presence of expected SQL constructs (JOIN, GROUP BY, WHERE, subqueries) per model/baseline
    4. (Optionally) Compute **string-level Exact Match** vs the published gold SQL strings (a strict metric, not executable).
    5. Document this gap as an **environmental evaluation limitation**, not a methodological one.

    ## Honest classification
    External validation slice — **prediction-only on Spider 2.0-Lite, EX not computable from Colab.** The mandatory operational evaluation continues on internal Spider subsets (smoke_10, smoke_25, multidb_30) where we have sandboxed SQLite execution.
    ''').strip()+'\n', encoding='utf-8')

# ============================================================
# B. BIRD MINI-DEV
# ============================================================
print('=== BIRD Mini-Dev acquisition ===', flush=True)
BIRD_URL = 'https://github.com/bird-bench/mini_dev.git'
BIRD_RAW = BIRD_DIR / 'raw' / 'mini_dev'

if not BIRD_RAW.exists():
    print(f'cloning {BIRD_URL} (shallow) into {BIRD_RAW}', flush=True)
    r = sh('git', 'clone', '--depth', '1', BIRD_URL, str(BIRD_RAW), timeout=600)
    print('clone rc=', r.returncode, 'err=', r.stderr[-300:] if r.stderr else '')
else:
    print(f'BIRD mini_dev repo already at {BIRD_RAW}; skipping clone')

# Locate the mini-dev tasks file (BIRD usually publishes mini_dev.json with question + SQL + db_id)
bird_json_candidates = [
    BIRD_RAW / 'mini_dev_sqlite.json',
    BIRD_RAW / 'mini_dev.json',
    BIRD_RAW / 'llm' / 'mini_dev_data' / 'mini_dev_sqlite.json',
    BIRD_RAW / 'data' / 'mini_dev.json',
    BIRD_RAW / 'data' / 'mini_dev_sqlite.json',
]
bird_json = None
for c in bird_json_candidates:
    if c.exists():
        bird_json = c; break

if bird_json is None and BIRD_RAW.exists():
    found = list(BIRD_RAW.rglob('*mini_dev*.json'))
    if not found:
        found = list(BIRD_RAW.rglob('*.json'))
    found = [p for p in found if 'package' not in p.name.lower()]
    found.sort(key=lambda p: (0 if 'mini' in p.name.lower() and 'sqlite' in p.name.lower() else
                              (1 if 'mini' in p.name.lower() else 2),
                              -p.stat().st_size))
    if found:
        bird_json = found[0]

bird_manifest_md = LOGS / 'bird_mini_dev_acquisition.md'

if bird_json is None:
    bird_manifest_md.write_text(textwrap.dedent(f'''
    # BIRD Mini-Dev acquisition (FAILED)

    **Captured:** {NOW}
    **Source URL:** {BIRD_URL}
    **Method:** shallow git clone
    **Outcome:** could not locate mini_dev json after clone.
    ''').strip()+'\n', encoding='utf-8')
    print('BIRD_ACQUISITION_FAILED — no json found')
    bird_examples = []
else:
    bird_examples = json.loads(bird_json.read_text(encoding='utf-8'))
    if isinstance(bird_examples, dict):
        # Some versions wrap a list under a top-level key
        for key in ('data','examples','questions','mini_dev'):
            if key in bird_examples and isinstance(bird_examples[key], list):
                bird_examples = bird_examples[key]; break
    if not isinstance(bird_examples, list):
        bird_examples = []
    print(f'BIRD mini-dev examples loaded: {len(bird_examples)} from {bird_json}')

    bird_sha = sha256_of(bird_json)
    bird_size = bird_json.stat().st_size

    def get_db(ex):
        return ex.get('db_id') or ex.get('database') or ex.get('database_name') or 'unknown'

    db_dist = Counter(get_db(ex) for ex in bird_examples)

    bird_manifest = {
        'benchmark': 'BIRD Mini-Dev',
        'source_url': BIRD_URL,
        'official_site': 'https://bird-bench.github.io/',
        'acquisition_method': 'shallow git clone',
        'downloaded_at_utc': NOW,
        'tasks_file': str(bird_json.relative_to(EXT_ROOT)),
        'tasks_file_sha256': bird_sha,
        'tasks_file_bytes': bird_size,
        'n_tasks': len(bird_examples),
        'unique_dbs': len(db_dist),
        'license_note': 'See BIRD repo LICENSE; mini_dev is the public small dev split',
    }
    (BIRD_DIR/'manifests'/'bird_mini_dev_manifest.json').write_text(
        json.dumps(bird_manifest, indent=2), encoding='utf-8')

    # 30-example diverse slice via round-robin DB coverage
    by_db = {}
    for i, ex in enumerate(bird_examples):
        by_db.setdefault(get_db(ex), []).append((i, ex))
    selected = []
    db_keys = sorted(by_db.keys())
    idx_per_db = {k: 0 for k in db_keys}
    while len(selected) < 30 and any(idx_per_db[k] < len(by_db[k]) for k in db_keys):
        for k in db_keys:
            if idx_per_db[k] < len(by_db[k]):
                i, ex = by_db[k][idx_per_db[k]]
                idx_per_db[k] += 1
                selected.append({
                    'idx': len(selected),
                    'original_id': ex.get('question_id') or ex.get('id') or i,
                    'db_id': get_db(ex),
                    'question': ex.get('question') or '',
                    'gold_sql': ex.get('SQL') or ex.get('query') or ex.get('sql') or '',
                    'evidence': ex.get('evidence',''),
                    'source_split': 'bird-mini-dev',
                    'source_path': str(bird_json.relative_to(EXT_ROOT)),
                })
                if len(selected) >= 30: break

    out_slice = BIRD_DIR/'processed'/'bird_minidev_30_diverse.json'
    out_slice.write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding='utf-8')

    sel_db_dist = Counter(s['db_id'] for s in selected)
    has_gold = sum(1 for s in selected if s['gold_sql'])
    audit_md = LOGS / 'bird_minidev_30_diverse_audit.md'
    audit_md.write_text(textwrap.dedent(f'''
    # bird_minidev_30_diverse audit

    **Captured:** {NOW}
    **Slice path:** `{out_slice.relative_to(PROJECT_ROOT)}`
    **N items:** {len(selected)}
    **Unique DBs:** {len(sel_db_dist)}
    **Items with gold_sql present:** {has_gold} / {len(selected)}

    ## Distribution by db_id
    | db_id | count |
    |---|---|
    ''').strip() + '\n' + '\n'.join(
        f'| `{k}` | {v} |' for k, v in sorted(sel_db_dist.items(), key=lambda x: (-x[1], x[0]))
    ) + '\n', encoding='utf-8')

    # Locate BIRD mini-dev SQLite databases (for actual EX execution)
    db_dirs = []
    for cand in ['mini_dev_database', 'database', 'mini_dev_databases',
                 'llm/mini_dev_data/mini_dev_database',
                 'data/dev_databases', 'data/mini_dev_database']:
        p = BIRD_RAW / cand
        if p.exists() and p.is_dir():
            db_dirs.append(p)
    if not db_dirs:
        # try to find any folder with .sqlite files
        for p in BIRD_RAW.rglob('*.sqlite'):
            if p.parent.parent not in db_dirs:
                db_dirs.append(p.parent.parent)
                break
    sqlite_files = []
    if db_dirs:
        for d in db_dirs:
            sqlite_files.extend(list(d.rglob('*.sqlite')))

    bird_manifest_md.write_text(textwrap.dedent(f'''
    # BIRD Mini-Dev acquisition

    **Captured:** {NOW}
    **Official source:** {BIRD_URL}
    **Official site:** https://bird-bench.github.io/
    **Acquisition method:** shallow `git clone --depth 1`
    **Tasks file:** `{bird_json.relative_to(EXT_ROOT)}`
    **SHA-256:** `{bird_sha}`
    **Size (bytes):** {bird_size}
    **N tasks loaded:** {len(bird_examples)}
    **Unique DBs:** {len(db_dist)}

    ## Processed slice
    - `{out_slice.relative_to(PROJECT_ROOT)}` — 30 examples, max-diverse DB coverage

    ## Database availability
    - SQLite database directories detected: {[str(d.relative_to(EXT_ROOT)) for d in db_dirs] if db_dirs else "NONE — would need to download separately"}
    - SQLite files found: {len(sqlite_files)}

    ## Manifest JSON
    `{(BIRD_DIR/"manifests"/"bird_mini_dev_manifest.json").relative_to(PROJECT_ROOT)}`
    ''').strip()+'\n', encoding='utf-8')

# ============================================================
# Final acquisition summary
# ============================================================
summary = textwrap.dedent(f'''
# External benchmark acquisition — summary

_Generated: {NOW}_

| Benchmark | Status | Tasks loaded | Unique DBs | Slice |
|---|---|---|---|---|
| Spider 2.0-Lite | {"OK" if 's2_examples' in dir() and s2_examples else "FAILED"} | {len(s2_examples) if 's2_examples' in dir() else 0} | {len(set((ex.get('db_id') or ex.get('db') or 'unknown') for ex in s2_examples)) if 's2_examples' in dir() and s2_examples else 0} | `external_benchmarks/spider2_lite/processed/spider2lite_30_diverse.json` |
| BIRD Mini-Dev | {"OK" if 'bird_examples' in dir() and bird_examples else "FAILED"} | {len(bird_examples) if 'bird_examples' in dir() else 0} | {len(set((ex.get('db_id') or ex.get('database') or 'unknown') for ex in bird_examples)) if 'bird_examples' in dir() and bird_examples else 0} | `external_benchmarks/bird_mini_dev/processed/bird_minidev_30_diverse.json` |

## Drive layout
```
{EXT_ROOT.relative_to(PROJECT_ROOT)}/
├── spider2_lite/
│   ├── raw/Spider2/        (sparse-checkout: spider2-lite/)
│   ├── processed/spider2lite_30_diverse.json
│   └── manifests/spider2_lite_manifest.json
└── bird_mini_dev/
    ├── raw/mini_dev/       (full shallow clone)
    ├── processed/bird_minidev_30_diverse.json
    └── manifests/bird_mini_dev_manifest.json
```

## Audit logs
- `outputs/logs/spider2_lite_acquisition.md`
- `outputs/logs/spider2lite_30_diverse_audit.md`
- `outputs/logs/spider2_lite_eval_limitations.md` (if EX not computable)
- `outputs/logs/bird_mini_dev_acquisition.md`
- `outputs/logs/bird_minidev_30_diverse_audit.md`
''').strip() + '\n'
(LOGS/'external_benchmark_acquisition_summary.md').write_text(summary, encoding='utf-8')
print('=== ACQUISITION SUMMARY ===')
print(summary)
