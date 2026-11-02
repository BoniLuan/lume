import { describe, expect, it } from "vitest";

import type { Account, ReviewDecision, StatementReview } from "../../api/types";
import { decisionError, initialDecisions, moneyString, moneyUnits, projectedBalances } from "./review";

const accounts = [{ id: "bank" }, { id: "card" }] as Account[];
const review = {
  account_id: "bank", decisions: [],
  metadata: { end_date: "2026-10-31" },
  rows: [{ row_key: "payment", kind: "expense", amount: "25.1000", description: "Pagamento de fatura", effective_date: "2026-10-05", candidates: [], suggested_kind: "transfer", suggested_counterparty_account_id: "card" }],
  balances: [{ account_id: "bank", current_balance: "100.0000", statement_closing_balance: "74.9000" }, { account_id: "card", current_balance: "-25.1000" }],
} as unknown as StatementReview;

describe("statement review decisions", () => {
  it("keeps suggested card payments pending until the user decides", () => {
    const decisions = initialDecisions(review);
    expect(decisions.payment).toMatchObject({ action: "pending", kind: "transfer", counterparty_account_id: "card" });
    expect(projectedBalances(review, decisions, accounts)[0]?.projected_balance).toBe("100.0000");
  });

  it("preserves cleared fields when reopening a saved draft", () => {
    const saved = { ...review, decisions: [{ row_key: "payment", action: "create", kind: "transfer", counterparty_account_id: null, description: "", remember_category: false, allow_possible_match: false } as ReviewDecision] };
    const decisions = initialDecisions(saved);
    expect(decisions.payment?.counterparty_account_id).toBeNull();
    expect(decisions.payment?.description).toBe("");
    expect(decisionError(saved.rows[0]!, decisions.payment!, accounts, "bank")).toBe("Enter a description.");
  });

  it("projects both transfer legs exactly and excludes resolved rows", () => {
    const decisions = initialDecisions(review);
    decisions.payment!.action = "create";
    const projected = projectedBalances(review, decisions, accounts);
    expect(projected[0]).toMatchObject({ projected_balance: "74.9000", difference: "0.0000" });
    expect(projected[1]?.projected_balance).toBe("0.0000");
    const resolved = { ...review, rows: [{ ...review.rows[0]!, resolved_action: "create" as const }] };
    expect(projectedBalances(resolved, decisions, accounts)[0]?.projected_balance).toBe("100.0000");
    expect(moneyString(moneyUnits("-0.1000") + moneyUnits("0.3000"))).toBe("0.2000");
  });

  it.each([false, true])("requires duplicate confirmation even when already linked = %s", (already_linked) => {
    const row = { ...review.rows[0]!, candidates: [{ ledger_account_id: "bank", already_linked }] } as StatementReview["rows"][number];
    const decisions = initialDecisions(review);
    decisions.payment!.action = "create";
    expect(decisionError(row, decisions.payment!, accounts, "bank")).toContain("possible match");
    decisions.payment!.allow_possible_match = true;
    expect(decisionError(row, decisions.payment!, accounts, "bank")).toBeNull();
  });
});
