# Statement review and registration

Open **Transactions → Import statement**, choose a CSV or OFX file, select the
account the statement describes, and open the review. A checking statement can
contain card payments and investment movements while still describing only the
checking account. Individual card purchases require the card statement.

Every row starts **Needs review**. Select a row in the checklist to see its full
original bank description, date, amount, and possible existing Lume transactions.
Choose one action:

- **Already registered — link existing**: compare account names, category, amount,
  date, and description; select the existing transaction. Its ledger values and
  your description remain unchanged.
- **Register a new transaction**: date and amount come from the statement. Review
  the prefilled description, type, category, and account. Transfers, payments,
  savings movements, loans, and principal repayments have two accounts and do not
  count as income or spending. Account assignment can differ per row.
- **Ignore**: explicitly leave the row out of the ledger.
- **Needs review / decide later**: leave the row pending while handling other rows.

**Save progress** persists decisions without changing the ledger. Incomplete
registrations can be saved. Save explicitly before leaving or opening another
statement. Leaving through app navigation offers Save and leave, Discard changes
and leave, or Stay here. A failed save keeps the review open. **Saved reviews → Resume** refreshes matches and balances. **Apply
reviewed decisions** atomically registers, links, and ignores the chosen rows;
pending rows stay available for a later session. Applied rows become read-only.
Correct a linked ledger entry through Transactions; the review warns if its date,
amount, direction, or void status no longer agrees with the bank row.

## Matching and balances

Candidates use equal amount, compatible direction, and dates within two days.
Descriptions need not match. Same-account candidates come first; different-account
candidates show the account assignment explicitly. Search can find up to 50 matching
transactions across all dates, optionally filtered by your description. A candidate
is a suggestion, never an automatic link. Creating a separate nearby transaction
requires explicit confirmation when a same-account candidate exists, including
transactions already linked to another statement row.

Source identities are scoped to the mapped statement account. Reopening or
reuploading a resolved row does not register it again. A transaction can be linked
once per affected ledger account: both sides of a single transfer may be reconciled
against their respective statements, but two bank rows cannot reuse the same leg.
Existing imports using the prior retry key are also recognized. Duplicate links,
ownership, amounts, direction, references, and active accounts are validated again
when applying. Concurrent stale saves return 409 instead of overwriting progress.
The recovery action can discard local choices and reload the latest saved review
without a full page refresh. Search results stay visible while switching rows.

OFX metadata exposes the institution, masked account suffix, currency, statement
period, and reported closing balance/date. Currency must agree with the mapped
account. OFX files containing multiple statement-account sections are rejected
with instructions to export each account separately; they are never flattened
silently into a single account.

The balance preview shows Lume balances and the effect of complete new
registrations for each affected account at the statement balance date (or period
end for CSV). Links and ignored/pending rows do not change balances. Only the
mapped account has an external comparison unless the file supplies another
statement. The difference is `bank closing balance − projected Lume balance`.
Credit-card balances use signed ledger values; negative means owed.

When the closing balance date matches the period end, Lume also infers the opening
balance from the statement movements and compares it with Lume before the period.
The list of unmatched Lume entries helps reveal earlier discrepancies or entries
missing from the file. A zero closing difference alone does not prove every row is
correct. Save progress to refresh the unmatched list after choosing links.

## File formats and retention

CSV needs a header with date, description, and either a signed amount or debit and
credit columns. English and common Portuguese header names are accepted. Amounts
may use a decimal point or comma, with up to two decimal places. Dates may use
`YYYY-MM-DD`, `DD/MM/YYYY`, or `DD-MM-YYYY`. Negative means money left the assigned
account; positive means money arrived. For positive amounts in both directions,
include a `type` column using `debit`/`credit` or `expense`/`income`.

OFX uses `DTPOSTED`, `TRNAMT`, `NAME` (or `MEMO`), and optional `FITID` within each
`STMTTRN`. Files are limited to 1 MB and 500 rows. The browser accepts UTF-8 and
falls back to Windows-1252. The server reparses stored source content when saving
or applying; clients cannot change source dates or amounts through decisions.
The gateway allows 3 MB API request bodies to accommodate a 1 MB statement plus
JSON encoding and up to 500 decisions; file and row limits still apply in the API.
Full bank descriptions remain available even when your ledger description is
shortened or edited. Category rules are suggestions based on approved choices.

Uploaded content and draft decisions are stored in owner-scoped database records,
covered by the existing database backup policy. The UI exposes this before opening
a review. **Delete saved file** deletes the review and uploaded content, retaining
ledger transactions and minimal row resolutions (including the original bank
description) to preserve reconciliation history and prevent duplicate imports.
Up to 50 recently saved reviews are listed; uploading the same file reopens its
existing review even if it is outside that list.

## API and rollout

The workspace uses `/api/v1/imports/reviews`: POST opens a review; GET lists recent
reviews; GET/PUT/DELETE `/{id}` resumes, saves, or deletes it; GET
`/{id}/candidates?row_key=...&search=...` searches existing transactions; POST
`/{id}/apply` applies reviewed decisions. Save/apply bodies include `version` and
exactly one decision per parsed row. Reads require authentication and browser writes
require CSRF. All access is owner-scoped. The earlier `/imports/preview` and
`/imports/commit` endpoints remain for compatibility.

Migration **0007** creates `import_reviews` and `import_row_resolutions`. Apply it
before starting the updated API and frontend. Development: `make migrate` after
building the updated API image. Production follows the existing explicit migration
and deployment runbook. No statement data is imported by the migration.
