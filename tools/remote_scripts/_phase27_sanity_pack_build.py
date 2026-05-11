"""Phase 27 Step 2 sanity — re-upload pack builder, build pack for one
Snow task, verify only 1 unique TABLE_CATALOG in the pack tables.
"""
import base64
import sys

# Read patched builder from local — base64 encoded
b64 = '__PACK_B64__'
src = base64.b64decode(b64).decode('utf-8')
with open('/content/drive/MyDrive/diploma_plan_sql/repo/src/evaluation/schema_pack_builder_v18.py', 'w', encoding='utf-8') as f:
    f.write(src)
print('uploaded patched schema_pack_builder_v18.py')

# Reload modules
import importlib
DRV_EVAL = '/content/drive/MyDrive/diploma_plan_sql/repo/src/evaluation'
if DRV_EVAL not in sys.path: sys.path.insert(0, DRV_EVAL)
for mod in ['schema_pack_builder_v18', 'schema_linking_v18']:
    if mod in sys.modules: importlib.reload(sys.modules[mod])
import schema_pack_builder_v18 as sb
import schema_linking_v18 as sl

# Build pack for one Spider2-Snow task using PATENTS db
catalog = sl.load_catalog_jsonl(
    __import__('pathlib').Path('/content/drive/MyDrive/diploma_plan_sql/outputs/cache/spider2_snow_live_catalog_v18.jsonl'),
    'snow')
print(f'catalog cols total: {len(catalog)}')

linker = sl.SchemaLinker(catalog)

# Test 1: with db_filter (correct path)
q = 'How many active patent assignees are there per region per year?'
link = linker.query(q, db_filter='PATENTS', top_columns=80, top_tables=20)
print(f'linker hits with db_filter=PATENTS: {len(link.hits)}')
pack = sb.build_pack(link, lane='snow', alias='PATENTS',
                      max_tables=8, max_cols_per_table=22, all_catalog_cols=catalog)
unique_dbs = {t['db'] for t in pack['tables']}
print(f'pack tables: {len(pack["tables"])}')
print(f'unique TABLE_CATALOGs in pack: {sorted(unique_dbs)}')
assert unique_dbs == {'PATENTS'}, f'LEAK: pack has multiple catalogs {unique_dbs}'

# Test 2: without db_filter (old behavior + new defense)
link2 = linker.query(q, top_columns=80, top_tables=20)
print(f'linker hits NO db_filter: {len(link2.hits)}')
unique_dbs_link = {h.record.db for h in link2.hits}
print(f'  raw linker hits span DBs: {sorted(unique_dbs_link)[:10]}...({len(unique_dbs_link)} total)')
pack2 = sb.build_pack(link2, lane='snow', alias='PATENTS',
                       max_tables=8, max_cols_per_table=22, all_catalog_cols=catalog)
unique_dbs2 = {t['db'] for t in pack2['tables']}
print(f'pack2 tables (after defense): {len(pack2["tables"])}')
print(f'unique TABLE_CATALOGs in pack2 (alias=PATENTS): {sorted(unique_dbs2)}')
assert unique_dbs2.issubset({'PATENTS'}), f'F1 DEFENSE FAILED: pack2 has {unique_dbs2}'

print()
print('ALL SANITY CHECKS PASSED')
print(f'pack table samples:')
for t in pack['tables'][:3]:
    print(f'  {t["db"]}.{t["schema"]}.{t["table"]} ({len(t["columns"])} cols, {len(t.get("all_columns",[]))} all_cols)')
