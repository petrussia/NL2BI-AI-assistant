# DeepSeek import test (isolated env) — H100 lane

**Captured:** 2026-04-30T12:24:48.016507+00:00
**Isolated env:** `/tmp/ds_env`
**Pinned transformers:** `transformers==4.39.3`

## Probe stdout
```

```

## Probe stderr (if any)
```
The cache for model files in Transformers v4.22.0 has been updated. Migrating your old cache. This is a one-time only operation. You can interrupt this and resume the migration later on by calling `transformers.utils.move_cache()`.

0it [00:00, ?it/s]
0it [00:00, ?it/s]
Traceback (most recent call last):
  File "<string>", line 4, in <module>
  File "/tmp/ds_env/transformers/__init__.py", line 26, in <module>
    from . import dependency_versions_check
  File "/tmp/ds_env/transformers/dependency_versions_check.py", line 57, in <module>
    require_version_core(deps[pkg])
  File "/tmp/ds_env/transformers/utils/versions.py", line 117, in require_version_core
    return require_version(requirement, hint)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/tmp/ds_env/transformers/utils/versions.py", line 111, in require_version
    _compare_versions(op, got_ver, want_ver, requirement, pkg, hint)
  File "/tmp/ds_env/transformers/utils/versions.py", line 44, in _compare_versions
    raise ImportError(
ImportError: tokenizers>=0.14,<0.19 is required for a normal functioning of this module, but found tokenizers==0.19.1.
Try: `pip install transformers -U` or `pip install -e '.[dev]'` if you're working with git main

```

## Verdict
PROBE FAILED — see stderr above
