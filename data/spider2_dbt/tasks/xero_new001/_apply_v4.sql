```diff
--- a/models/xero__profit_and_loss_report.sql
+++ b/models/xero__profit_and_loss_report.sql
@@ -1,4 +1,4 @@
 version: 2
 
-models:
+models:
   - name: xero__profit_and_loss_report
     description: 
       This model represents individual line items in the profit and loss (P&L) report at the month and account level. It is derived from `xero__general_ledger` and aggregates net amounts for revenue and expenses. Each record reflects the monthly movement of funds for a given account, which helps assess an organization's financial performance over time.
     columns:
       - name: profit_and_loss_id
         description: Unique identifier for each profit and loss entry.
       - name: date_month
         description: The month for which the profit and loss entry is calculated.
       - name: account_id
         description: Identifier for the account involved in the transaction.
       - name: account_name
         description: Name of the account involved in the transaction.
       - name: account_type
         description: Type of the account (e.g., Revenue, Expense).
       - name: net_amount
         description: Net amount associated with the transaction.
       - name: balance
         description: Running balance of the account up to the specified month.
 
-config-version: 2
+config-version: 2
 
 require-dbt-version: [">=1.3.0", "<2.0.0"]
 
 profile: 'xero_new'
 
 vars:
   xero_source:
     xero_account_identifier: "xero_account_data"
     xero_contact_identifier: "xero_contact_data"
     xero_invoice_line_item_identifier: "xero_invoice_line_item_data"
     xero_invoice_identifier: "xero_invoice_data"
     xero_journal_line_identifier: "xero_journal_line_data"
     xero_journal_identifier: "xero_journal_data"
     xero_organization_identifier: "xero_organization_data"
     xero_bank_transaction_identifier: "xero_bank_transaction_data"
     xero_credit_note_identifier: "xero_credit_note_data"
 
 models:
   - name: xero__profit_and_loss_report
     description: 
       This model represents individual line items in the profit and loss (P&L) report at the month and account level. It is derived from `xero__general_ledger` and aggregates net amounts for revenue and expenses. Each record reflects the monthly movement of funds for a given account, which helps assess an organization's financial performance over time.
     columns:
       - name: profit_and_loss_id
         description: Unique identifier for each profit and loss entry.
       - name: date_month
         description: The month for which the profit and loss entry is calculated.
       - name: account_id
         description: Identifier for the account involved in the transaction.
       - name: account_name
         description: Name of the account involved in the transaction.
       - name: account_type
         description: Type of the account (e.g., Revenue, Expense).
       - name: net_amount
         description: Net amount associated with the transaction.
       - name: balance
         description: Running balance of the account up to the specified month.
 
 config-version: 2
 
 require-dbt-version: [">=1.3.0", "<2.0.0"]
 
 profile: 'xero_new'
 
 vars:
   xero_source:
     xero_account_identifier: "xero_account_data"
     xero_contact_identifier: "xero_contact_data"
     xero_invoice_line_item_identifier: "xero_invoice_line_item_data"
     xero_invoice_identifier: "xero_invoice_data"
     xero_journal_line_identifier: "xero_journal_line_data"
     xero_journal_identifier: "xero_journal_data"
     xero_organization_identifier: "xero_organization_data"
     xero_bank_transaction_identifier: "xero_bank_transaction_data"
     xero_credit_note_identifier: "xero_credit_note_data"
 
 models:
   - name: xero__profit_and_loss_report
     description: 
       This model represents individual line items in the profit and loss (P&L) report at the month and account level. It is derived from `xero__general_ledger` and aggregates net amounts for revenue and expenses. Each record reflects the monthly movement of funds for a given account, which helps assess an organization's financial performance over time.
     columns:
       - name: profit_and_loss_id
         description: Unique identifier for each profit and loss entry.
       - name: date_month
         description: The month for which the profit and loss entry is calculated.
       - name: account_id
         description: Identifier for the account involved in the transaction.
       - name: account_name
         description: Name of the account involved in the transaction.
       - name: account_type
         description: Type of the account (e.g., Revenue, Expense).
       - name: net_amount
         description: Net amount associated with the transaction.
       - name: balance
         description: Running balance of the account up to the specified month.
 
 config-version: 2
 
 require-dbt-version: [">=1.3.0", "<2.0.0"]
 
 profile: 'xero_new'
 
 vars:
   xero_source:
     xero_account_identifier: "xero_account_data"
     xero_contact_identifier: "xero_contact_data"
     xero_invoice_line_item_identifier: "xero_invoice_line_item_data"
     xero_invoice_identifier: "xero_invoice_data"
     xero_journal_line_identifier: "xero_journal_line_data"
     xero_journal_identifier: "xero_journal_data"
     xero_organization_identifier: "xero_organization_data"
     xero_bank_transaction_identifier: "xero_bank_transaction_data"
     xero_credit_note_identifier: "xero_credit_note_data"
 
 models:
   - name: xero__profit_and_loss_report
     description: 
       This model represents individual line items in the profit and loss (P&L) report at the month and account level. It is derived from `xero__general_ledger` and aggregates net amounts for revenue and expenses. Each record reflects the monthly movement of funds for a given account, which helps assess an organization's financial performance over time.
     columns:
       - name: profit_and_loss_id
         description: Unique identifier for each profit and loss entry.
       - name: date_month
         description: The month for which the profit and loss entry is calculated.
       - name: account_id
         description: Identifier for the account involved in the transaction.
       - name: account_name
         description: Name of the account involved in the transaction.
       - name: account_type
         description: Type of the account (e.g., Revenue, Expense).
       - name: net_amount
         description: Net amount associated with the transaction.
       - name: balance
         description: Running balance of the account up to the specified month.
 
 config-version: 2
 
 require-dbt-version: [">=1.3.0", "<2.0.0"]
 
 profile: 'xero