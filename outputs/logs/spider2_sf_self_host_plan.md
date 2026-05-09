# Spider2 Snowflake — self-host / share plan

_Generated from `snowflake_setup/probe_databases.py` output. Identifies
the path to unblocking real Spider2 SF execution given the current
account location._

## Current account snapshot

| Field | Value |
|---|---|
| `CURRENT_USER()` | `SPIDER2_BENCH` |
| `CURRENT_ROLE()` | `SPIDER2_RW` |
| `CURRENT_ACCOUNT()` | `DI69621` |
| `CURRENT_ORGANIZATION_NAME()` | `QOBJWEZ` |
| Account identifier (for sharing) | **`QOBJWEZ.DI69621`** |
| `CURRENT_REGION()` | `AWS_AP_SOUTH_1` |
| Cloud | AWS |
| Region (short) | `ap-south-1` (Mumbai) |
| `CURRENT_VERSION()` | `10.16.101` |

## Self-host eligibility

- Spider2 official self-host (per `assets/Spider2_Data_Host.md` and the
  `lfy79001/spider2-data-share` README) requires the receiving account
  to be in **AWS us-west-2 (Oregon)**.
- Current account is `AWS ap-south-1` (Mumbai).
- **Self-host eligible: NO.**

There are two paths forward.

## Path A — Marketplace share from xlang-ai (cross-region OK)

Snowflake **secure data shares can cross regions** as long as both
sides allow it; xlang-ai routinely gives Marketplace access to
academic / research accounts in any region. This is the lighter-weight
option.

1. Submit the
   [Spider2 Snowflake Access form](https://docs.google.com/forms/d/e/1FAIpQLScbVIYcBkADVr-NcYm9fLMhlxR7zBAzg-jaew1VNRj6B8yD3Q/viewform).
2. Provide the account identifier `QOBJWEZ.DI69621` (org.account).
3. State the region: `AWS_AP_SOUTH_1` (so xlang-ai sets up cross-region
   replication or attaches the cross-region listing).
4. Wait for the share to land. Once attached, the database appears in
   `SHOW DATABASES` automatically; `GRANT IMPORTED PRIVILEGES ON
   DATABASE <DB> TO ROLE SPIDER2_RW` may be needed.

### Sample email

```
Subject: Spider2 Snowflake access request — QOBJWEZ.DI69621 (ap-south-1)

Hi xlang-ai team,

I am running Spider2-Lite SF and Spider2-Snow benchmarks for an
NL2SQL diploma project. My Snowflake account is:

  Account identifier:     QOBJWEZ.DI69621
  Cloud / region:         AWS / ap-south-1 (Mumbai)
  Service user:           SPIDER2_BENCH
  Role:                   SPIDER2_RW
  Warehouse:              SPIDER2_WH (XSMALL, AUTO_SUSPEND 60s)
  Default DB / schema:    SPIDER2_WORK / PUBLIC

Could you please share the Spider2 Snowflake datasets (the 58 listed
under spider2-lite/resource/databases/snowflake/, plus the spider2-snow
share) with this account? Cross-region works for me; the read-only
benchmark queries are small (XSMALL warehouse, AUTO_SUSPEND, capped
queries) so the cost should be minimal.

Thanks!
```

### After the share lands

```sql
-- (run as ACCOUNTADMIN once)
GRANT IMPORTED PRIVILEGES ON DATABASE <SHARED_DB> TO ROLE SPIDER2_RW;
-- Repeat for every shared database the share exposes.
```

Verify with:
```bash
python snowflake_setup/probe_databases.py
```
The `MISSING` list should shrink.

## Path B — Self-host (requires new account in AWS us-west-2)

If Marketplace share is not feasible, Spider2 also supports self-host
via a one-shot Secure Data Share from the authors:

```sql
CREATE OR REPLACE DATABASE SPIDER2_MERGED_250922
  FROM SHARE "SDB71929".SHARE_FOR_SPIDER2_DB;
```

Per the `lfy79001/spider2-data-share` repo, this share is published
**only to AWS us-west-2 accounts**. Receiving it on `ap-south-1` will
fail with "share not available in this region".

### To go self-host

1. Create a NEW Snowflake account.
   - Cloud: **AWS**
   - Region: **US West (Oregon) — us-west-2**
   - Edition: Standard is enough.
   - Choose any organization name; remember it.
2. Run our existing `friend_provisioning.sql` in the new account
   (creates `SPIDER2_RW`, `SPIDER2_WH`, `SPIDER2_BENCH`).
3. Email xlang-ai with the new account identifier (`<NEW_ORG>.<NEW_ACCOUNT>`)
   and request the secure data share for SDB71929.
4. After the share is granted:
   ```sql
   USE ROLE ACCOUNTADMIN;
   CREATE OR REPLACE DATABASE SPIDER2_MERGED_250922
     FROM SHARE "SDB71929".SHARE_FOR_SPIDER2_DB;

   GRANT IMPORTED PRIVILEGES ON DATABASE SPIDER2_MERGED_250922 TO ROLE SPIDER2_RW;
   ```
5. Clone `https://github.com/lfy79001/spider2-data-share` and run the
   migration scripts in order:
   ```bash
   python database_mapping.py
   python create_databases.py
   python create_tables.py
   ```
   This unpacks `SPIDER2_MERGED_250922` into the 58 individual
   databases the benchmark expects (`PATENTS`, `CRYPTO`, etc.).
6. Update `snowflake_setup/.env` with the new account credentials.
7. Re-run `python snowflake_setup/probe_databases.py` — the
   `MISSING` list should be 0.

### Risks of Path B

- **New account = new credit grant.** Free trial covers $400 / 30 days
  in USD-equivalent credits. Migration scripts read all 58 databases
  with table copies; with XSMALL, auto-suspend, and cached results,
  the migration itself is bounded but not free.
- **Two SF accounts to manage.** The current ap-south-1 account stays
  available for our own SPIDER2_WORK; the new us-west-2 account would
  hold Spider2 datasets.
- **Region cost.** XSMALL warehouse credit price is the same across
  regions; egress + replication if any is the only delta. Spider2
  queries are short, so the practical cost is small.

## Recommendation

Try **Path A** first (Marketplace share). It's lower-friction:
- Single account, no migration scripts.
- xlang-ai routinely sets these up.
- Cross-region works because Snowflake auto-replicates shared listings
  to the consumer's home region on first read.

Fall back to **Path B** only if xlang-ai cannot share into ap-south-1.

## What this PR does NOT do

This bridge does not migrate data, mail anyone, or create new
accounts. It (a) records the blocker, (b) provides the exact email +
SQL templates, (c) gates real SF execution behind a `readiness=true`
check so the runner refuses to manufacture predictions against
non-existent databases.

`outputs/snowflake/readiness/databases_visible.{json,md}` is the
machine-readable snapshot of the current state.
