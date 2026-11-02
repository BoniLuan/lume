import type { Account, ReviewDecision, ReviewRow, StatementReview } from "../../api/types";

export function initialDecisions(review: StatementReview): Record<string, ReviewDecision> {
  const saved = new Map(review.decisions.map((decision) => [decision.row_key, decision]));
  return Object.fromEntries(review.rows.map((row) => {
    const decision = saved.get(row.row_key);
    return [row.row_key, {
      row_key: row.row_key,
      kind: decision?.kind ?? row.suggested_kind,
      account_id: decision?.account_id ?? review.account_id,
      description: decision?.description ?? row.description.slice(0, 160),
      category_id: decision?.kind ? decision.category_id : row.suggested_category_id,
      counterparty_account_id: decision?.kind ? decision.counterparty_account_id : row.suggested_counterparty_account_id,
      transaction_id: decision?.transaction_id,
      remember_category: decision?.remember_category ?? false,
      allow_possible_match: decision?.allow_possible_match ?? false,
      action: decision?.action ?? "pending",
    }];
  }));
}

export function decisionError(row: ReviewRow, decision: ReviewDecision, accounts: Account[], statementAccount: string): string | null {
  if (row.resolved_action || decision.action === "pending" || decision.action === "skip") return null;
  const anchor = decision.account_id ?? statementAccount;
  const account = accounts.find((a) => a.id === anchor);
  if (!account || account.archived_at) return "Choose an active account.";
  if (decision.action === "link") {
    if (decision.transaction_id && decision.transaction_id === row.invalid_transaction_id) return "The selected transaction changed or is unavailable. Choose another match.";
    return decision.transaction_id ? null : "Choose the existing transaction.";
  }
  if (!decision.description?.trim()) return "Enter a description.";
  if (decision.kind === "transfer") {
    if (!decision.counterparty_account_id || decision.counterparty_account_id === anchor) return "Choose a different account for the other side of this transfer.";
  } else if (!decision.category_id) return "Choose a category.";
  if (row.candidates.some((m) => m.ledger_account_id === anchor) && !decision.allow_possible_match) return "Review the possible match or confirm this is a separate transaction.";
  return null;
}

// Keep balance arithmetic in fixed-point units, matching the API's four decimal places.
export function moneyUnits(value: string): bigint {
  const negative = value.startsWith("-");
  const [whole, fraction = ""] = value.replace(/^-/, "").split(".");
  return (BigInt(whole || "0") * 10000n + BigInt(fraction.padEnd(4, "0"))) * (negative ? -1n : 1n);
}

export function moneyString(value: bigint): string {
  const absolute = value < 0 ? -value : value;
  return `${value < 0 ? "-" : ""}${absolute / 10000n}.${String(absolute % 10000n).padStart(4, "0")}`;
}

export function projectedBalances(review: StatementReview, decisions: Record<string, ReviewDecision>, accounts: Account[]) {
  const movements = new Map<string, bigint>();
  for (const row of review.rows) {
    const decision = decisions[row.row_key];
    if (!decision || row.resolved_action || decision.action !== "create" || decisionError(row, decision, accounts, review.account_id)) continue;
    if (row.effective_date > (review.metadata.balance_date ?? review.metadata.end_date)) continue;
    const anchor = decision.account_id ?? review.account_id;
    const amount = moneyUnits(row.amount);
    const change = row.kind === "income" ? amount : -amount;
    movements.set(anchor, (movements.get(anchor) ?? 0n) + change);
    if (decision.kind === "transfer" && decision.counterparty_account_id) {
      const other = decision.counterparty_account_id;
      movements.set(other, (movements.get(other) ?? 0n) - change);
    }
  }
  return review.balances.filter((b) => b.account_id === review.account_id || movements.has(b.account_id)).map((balance) => {
    const projected = moneyUnits(balance.current_balance) + (movements.get(balance.account_id) ?? 0n);
    return { ...balance, projected_balance: moneyString(projected), difference: balance.statement_closing_balance != null ? moneyString(moneyUnits(balance.statement_closing_balance) - projected) : null };
  });
}
