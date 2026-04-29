# Spider Source And Audit

- Checked at: 2026-04-25T15:37:05.656738+00:00
- Source: existing assets
- dev.json found: True
- tables.json found: True
- database/ found: True
- SQLite DB count: 166

## Three Random SQLite Read Checks

```json
[
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
]
```
