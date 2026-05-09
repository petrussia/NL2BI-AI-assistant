# Bridge Status (drive)

Checked at: 2026-04-25T15:57:07.332113+00:00

- `/health`: ok (bridge live before this exec call)
- `/exec` POST: this script ran — exec endpoint working
- write test: `/content/drive/MyDrive/diploma_plan_sql/outputs/logs/_bridge_write_test.txt` exists (51 B)
- read test: artifact recheck listed 25 items
- model in bridge globals: yes (after 01_bridge_globals_import.py)
- tokenizer in bridge globals: yes
- helpers (build_full_schema_prompt_context, lexical_schema_linking, etc.) in scope: yes
