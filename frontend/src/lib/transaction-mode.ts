import type { Account, Transaction } from "../api/types";

export type EntryMode = "expense" | "income" | "transfer" | "loan_out" | "loan_repayment" | "credit_payment";

export function transactionMode(item: Transaction | null | undefined, accounts: Account[] = []): EntryMode {
  if (!item || item.kind !== "transfer") return item?.kind ?? "expense";
  const source = accounts.find((account) => account.id === item.account_id);
  const destination = accounts.find((account) => account.id === item.destination_account_id);
  if (destination?.account_type === "credit_card") return "credit_payment";
  if (destination?.account_type === "receivable") return "loan_out";
  if (source?.account_type === "receivable") return "loan_repayment";
  return "transfer";
}

export function transactionTypeLabel(item: Transaction, accounts: Account[] = []): string {
  const mode = transactionMode(item, accounts);
  if (mode === "credit_payment") return "Credit card payment";
  if (mode === "loan_out") return "Loan";
  if (mode === "loan_repayment") return "Loan repayment";
  if (mode === "transfer") return "Transfer";
  return mode === "income" ? "Income" : "Expense";
}
