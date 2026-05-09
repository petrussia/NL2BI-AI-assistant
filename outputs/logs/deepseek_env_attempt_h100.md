# DeepSeek isolated-env attempt log — H100 lane

**Captured:** 2026-04-30T12:24:48.016507+00:00

## Steps tried
1. Created `/tmp/ds_env` and `pip install --target` of `transformers==4.39.3` (rc=0).
2. Spawned a subprocess with `PYTHONPATH=/tmp/ds_env` and ran an import + tokenizer probe.

## Result
FAILED probe — see deepseek_import_test_h100.md

## Decision
Stop the in-kernel attempt; emit deepseek_blocker_h100_final.md with reproduction steps in a fresh notebook.

## Logs

```
[2026-04-30T12:24:48.016546+00:00] Installing transformers==4.39.3 into isolated env at /tmp/ds_env
[2026-04-30T12:24:56.226789+00:00] pip rc=0
[2026-04-30T12:24:56.227252+00:00] Running import probe in subprocess...
[2026-04-30T12:25:03.600744+00:00] probe rc=1
[2026-04-30T12:25:03.600772+00:00] probe stdout (head 800B):

[2026-04-30T12:25:03.600780+00:00] probe stderr (head 600B):
The cache for model files in Transformers v4.22.0 has been updated. Migrating your old cache. This is a one-time only operation. You can interrupt this and resume the migration later on by calling `transformers.utils.move_cache()`.

0it [00:00, ?it/s]
0it [00:00, ?it/s]
Traceback (most recent call last):
  File "<string>", line 4, in <module>
  File "/tmp/ds_env/transformers/__init__.py", line 26, in <module>
    from . import dependency_versions_check
  File "/tmp/ds_env/transformers/dependency_versions_check.py", line 57, in <module>
    require_version_core(deps[pkg])
  File "/tmp/ds_env/tr
```
