# ADR 0003: Positive amounts and single-row transfers

Status: accepted, 2026-09-16.

Every stored transaction amount is a positive `DECIMAL(19,4)`. Its kind determines
the balance effect. A transfer is one atomic row with source and destination
accounts, rather than two loosely linked rows.

Positive amounts remove ambiguous sign conventions at API boundaries. A single
transfer row cannot become half-complete and is naturally excluded from income,
expense, and budgets. Multi-currency transfers are deferred; v1 requires both
accounts and the user to share one currency.
