import { describe, expect, it } from "vitest";

import type { Account, Transaction } from "../api/types";
import { transactionMode, transactionTypeLabel } from "./transaction-mode";

const account = (id: string, account_type: Account["account_type"], account_class: Account["account_class"] = "asset") => ({ id, account_type, account_class } as Account);
const transfer = (account_id: string, destination_account_id: string) => ({ kind: "transfer", account_id, destination_account_id } as Transaction);

describe("transaction transfer semantics", () => {
  const accounts = [
    account("bank", "checking"),
    account("card", "credit_card", "liability"),
    account("receivable", "receivable"),
    account("savings", "savings"),
  ];

  it("recognizes card payments from their destination account", () => {
    const item = transfer("bank", "card");
    expect(transactionMode(item, accounts)).toBe("credit_payment");
    expect(transactionTypeLabel(item, accounts)).toBe("Credit card payment");
  });

  it("distinguishes loans, repayments, and ordinary transfers", () => {
    expect(transactionMode(transfer("bank", "receivable"), accounts)).toBe("loan_out");
    expect(transactionMode(transfer("receivable", "bank"), accounts)).toBe("loan_repayment");
    expect(transactionMode(transfer("bank", "savings"), accounts)).toBe("transfer");
  });
});
