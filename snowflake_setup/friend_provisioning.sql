-- friend_provisioning.sql — minimal SF objects to grant Spider2-Lite access
-- Run as ACCOUNTADMIN (or any role with the listed privileges).
-- Replace placeholder values where indicated.
--
-- This script creates:
--   1. A dedicated role         (SPIDER2_RW)
--   2. A dedicated warehouse    (SPIDER2_WH, XS, auto-suspend 60s)
--   3. A dedicated user         (SPIDER2_BENCH)
--   4. Grants for read access   to existing Spider2 datasets
--
-- Spider2 datasets are normally hosted on Snowflake's shared sample/Marketplace
-- accounts (see https://github.com/xlang-ai/Spider2/blob/main/assets/Snowflake_Guideline.md).
-- If you (the friend) are hosting your OWN copy of the data, replace the
-- "GRANT USAGE ON DATABASE <DB>" block with the actual database list.

USE ROLE ACCOUNTADMIN;

-- 1. Warehouse (XS is plenty for Spider2-Lite SF queries)
CREATE WAREHOUSE IF NOT EXISTS SPIDER2_WH
    WAREHOUSE_SIZE = 'XSMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Spider2-Lite benchmark execution (Denis HSE)';

-- 2. Dedicated role and grants
CREATE ROLE IF NOT EXISTS SPIDER2_RW
    COMMENT = 'Read-only across Spider2 datasets + run queries on SPIDER2_WH';

GRANT USAGE  ON WAREHOUSE SPIDER2_WH TO ROLE SPIDER2_RW;
GRANT OPERATE ON WAREHOUSE SPIDER2_WH TO ROLE SPIDER2_RW;

-- 3. User (password OR public_key — pick one; do NOT set both initially)
--    Replace 'REPLACE_ME_*' with real values BEFORE running.

-- Option A: password auth
CREATE USER IF NOT EXISTS SPIDER2_BENCH
    LOGIN_NAME = 'spider2_bench'
    PASSWORD = 'REPLACE_ME_STRONG_PASSWORD'
    DEFAULT_ROLE = SPIDER2_RW
    DEFAULT_WAREHOUSE = SPIDER2_WH
    MUST_CHANGE_PASSWORD = FALSE
    COMMENT = 'Spider2-Lite benchmark service account';

-- Option B: key-pair auth (preferred when MFA is enforced on the parent account)
-- ALTER USER SPIDER2_BENCH SET RSA_PUBLIC_KEY = 'REPLACE_ME_PEM_PUBLIC_KEY_BLOB';

GRANT ROLE SPIDER2_RW TO USER SPIDER2_BENCH;

-- 4. Read access to Spider2 datasets
--
-- 4a. If using Snowflake's Marketplace shares (the official Spider2 path),
-- the shared databases are already attached to the account; just grant USAGE.
-- Replace the sample list below with the real share names you receive after
-- filling out the Spider2 Snowflake Access form
-- (https://docs.google.com/forms/d/e/1FAIpQLScbVIYcBkADVr-NcYm9fLMhlxR7zBAzg-jaew1VNRj6B8yD3Q/viewform).
-- Examples observed in resource/databases/snowflake/:
--   AMAZON_VENDOR_ANALYTICS__SAMPLE_DATASET, AUSTIN, BRAZE_USER_EVENT_DEMO_DATASET,
--   CRYPTO, CENSUS_BUREAU_ACS_2, ETHEREUM_BLOCKCHAIN, FINANCE__ECONOMICS, ...

-- For each Spider2 SF database that is shared with the account, run:
--   GRANT IMPORTED PRIVILEGES ON DATABASE <DB_NAME> TO ROLE SPIDER2_RW;
--
-- Do NOT use SELECT/USAGE here for Marketplace shares — IMPORTED PRIVILEGES is
-- the documented way to expose a share to a custom role.

-- 4b. If you are self-hosting (Spider2_Data_Host.md route):
--   GRANT USAGE                 ON DATABASE <DB_NAME>            TO ROLE SPIDER2_RW;
--   GRANT USAGE                 ON ALL SCHEMAS IN DATABASE <DB>  TO ROLE SPIDER2_RW;
--   GRANT SELECT                ON ALL TABLES IN SCHEMA <DB.S>   TO ROLE SPIDER2_RW;
--   GRANT SELECT                ON FUTURE TABLES IN SCHEMA <DB.S> TO ROLE SPIDER2_RW;

-- 5. Hand off the credentials to Denis using a private channel:
--    SNOWFLAKE_ACCOUNT     = (the locator you see in the URL)
--    SNOWFLAKE_USER        = SPIDER2_BENCH
--    SNOWFLAKE_PASSWORD    = (the password set above)
--    SNOWFLAKE_ROLE        = SPIDER2_RW
--    SNOWFLAKE_WAREHOUSE   = SPIDER2_WH
--    SNOWFLAKE_DATABASE    = (any DB granted above; chosen as default context)
--    SNOWFLAKE_SCHEMA      = PUBLIC (or whatever the dataset uses)
--
--    Do NOT paste the password into chat — share via password manager / 1Password / etc.

-- 6. Optional safety: cap warehouse spend
-- (resource monitor capping credits/day, scoped to SPIDER2_WH)
-- CREATE RESOURCE MONITOR IF NOT EXISTS SPIDER2_RM
--     WITH CREDIT_QUOTA = 5
--     FREQUENCY = DAILY
--     START_TIMESTAMP = IMMEDIATELY
--     TRIGGERS ON 80 PERCENT DO NOTIFY
--              ON 100 PERCENT DO SUSPEND;
-- ALTER WAREHOUSE SPIDER2_WH SET RESOURCE_MONITOR = SPIDER2_RM;
