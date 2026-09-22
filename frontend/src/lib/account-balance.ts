import type { Account } from "../api/types";

export function accountBalanceDisplay(account: Account): { label: string; amount: string } {
  const signed = account.current_balance;
  if (account.account_class !== "liability") {
    return { label: account.account_type === "receivable" ? "Still owed to you" : "Current balance", amount: signed };
  }
  if (Number(signed) < 0) return { label: "Amount owed", amount: signed.slice(1) };
  if (Number(signed) > 0) return { label: account.account_type === "credit_card" ? "Card credit" : "Credit balance", amount: signed };
  return { label: "Paid off", amount: signed };
}
