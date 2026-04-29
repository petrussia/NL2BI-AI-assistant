# B0 Blockers Audit

```json
{
  "checked_at": "2026-04-25T15:37:05.656006+00:00",
  "project_root": "/content/drive/MyDrive/diploma_plan_sql",
  "spider_dir": "/content/drive/MyDrive/diploma_plan_sql/data/spider",
  "dev_json": true,
  "tables_json": true,
  "database_dir": true,
  "sqlite_db_count": 166,
  "three_random_sqlite_read_checks": [
    {
      "path": "database/wrestler/wrestler.sqlite",
      "ok": true,
      "tables_seen": [
        "wrestler",
        "Elimination"
      ]
    },
    {
      "path": "database/concert_singer/concert_singer.sqlite",
      "ok": true,
      "tables_seen": [
        "stadium",
        "singer",
        "concert",
        "singer_in_concert"
      ]
    },
    {
      "path": "database/assets_maintenance/assets_maintenance.sqlite",
      "ok": true,
      "tables_seen": [
        "Third_Party_Companies",
        "Maintenance_Contracts",
        "Parts",
        "Skills",
        "Staff"
      ]
    }
  ],
  "metrics_csv_exists": true,
  "predictions_jsonl_exists": true,
  "error_cases_md_exists": true
}
```

## Notes

Spider assets complete after audit/recovery.
