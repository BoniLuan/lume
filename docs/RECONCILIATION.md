# Account reconciliation

Lume keeps each account's signed ledger balance as its opening balance plus actual
transactions. An expense on a credit-card account makes its balance more negative;
a real payment from a bank account is one transfer into the card account and makes
the balance less negative. A negative card balance is an amount owed, zero is paid
off, and a positive card balance is a credit or overpayment.

In **Reports → Account balances**, select the account, date, and balance reported
by the bank or card provider for that same date. For a credit card, choose whether
the amount is **owed** or a **card credit**; Lume applies the ledger sign for you.
Compare against the card's total outstanding balance rather than just the most
recent closed invoice, because later purchases can remain outstanding. The
comparison shows `actual balance − Lume balance` and never creates or edits a
transaction. The amount entered is sent in an authenticated request body and is
not stored.

Use the balance timeline and transfers in/out totals to find missing purchases,
refunds, duplicate payments, or an incorrect opening balance. Correct the source
record; do not add a payment merely to make a balance reach zero. Changing the
opening balance changes all later calculated balances, so reserve it for an
incorrect starting point.

**Reports → Spending insights** compares the chosen month with the preceding
calendar month, breaks expense totals down by account, and shows category changes.
Card payments and other transfers are excluded from spending. The current month
may be incomplete, so the comparison is descriptive rather than a projection.
