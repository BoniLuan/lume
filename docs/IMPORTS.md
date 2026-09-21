# Reviewed statement imports

Open **Transactions → Import statement**. Select the Lume account that owns the
statement, then choose a CSV or OFX file. Lume previews every row before saving
anything. Choose a category for income and expense rows, or change a row to
**Transfer** and choose the other Lume account. Skip irrelevant rows. Confirm to
create the selected transactions.

CSV needs a header with date, description, and either a signed amount or debit and
credit columns. English and common Portuguese header names are accepted. Amounts
may use a decimal point or comma, with up to two decimal places. Dates may use
`YYYY-MM-DD`, `DD/MM/YYYY`, or `DD-MM-YYYY`. Signed negative amounts mean money left
the selected account; positive amounts mean money arrived. If an amount column uses
positive values for both directions, include a `type` column with `debit`/`credit`
or `expense`/`income`. OFX uses `DTPOSTED`, `TRNAMT`, `NAME` (or `MEMO`), and
optionally `FITID` within each `STMTTRN`.

Files are limited to 1 MB and 500 rows. The browser accepts UTF-8 and falls back
to Windows-1252 for older bank exports. The server parses the file again when you
confirm, so changing the preview cannot change the imported values. Files are not
stored. Existing transactions with the same account, direction, amount, date within
two days, and normalized description appear as possible matches and default to
Skip. To import a legitimate repeated payment, choose Create and check **Import
despite possible match**. Reimporting an already created row with the same source
identity still skips it. Always review the preview, especially for transfers,
credit-card payments, refunds, loans, and reimbursements: a bank statement cannot
reliably infer their financial meaning.

Checking **Remember this category** stores a category suggestion for later imports
with the same normalized description and direction. It never creates transactions
or categorizes new rows automatically. The rule belongs to your user account and
is removed with the category. Category choices are still validated at confirmation.

The import endpoints are `POST /api/v1/imports/preview` and
`POST /api/v1/imports/commit`. They require an authenticated session and CSRF
protection for browser requests. The request body includes `account_id`,
`filename`, and `content`; commit also includes one decision per preview row.
