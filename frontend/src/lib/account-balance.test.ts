import { describe, expect, it } from "vitest";

import type { Account } from "../api/types";
import { accountBalanceDisplay } from "./account-balance";

function card(balance: string): Account {
  return { account_class: "liability", account_type: "credit_card", current_balance: balance } as Account;
}

describe("credit card balance labels", () => {
  it("distinguishes debt, zero, and overpayment", () => {
    expect(accountBalanceDisplay(card("-150.0000"))).toEqual({ label: "Amount owed", amount: "150.0000" });
    expect(accountBalanceDisplay(card("0.0000"))).toEqual({ label: "Paid off", amount: "0.0000" });
    expect(accountBalanceDisplay(card("50.0000"))).toEqual({ label: "Card credit", amount: "50.0000" });
  });
});
