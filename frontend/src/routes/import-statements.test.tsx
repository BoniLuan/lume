import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { ApiError, api } from "../api/client";
import type { StatementReview } from "../api/types";
import { ImportStatementsRoute } from "./import-statements";

vi.mock("../api/client", async (importOriginal) => ({ ...await importOriginal<typeof import("../api/client")>(), api: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

function fixture(): StatementReview {
  return {
    id: "review", filename: "october.ofx", version: 1, account_id: "bank", updated_at: "2026-11-02T12:00:00",
    metadata: { start_date: "2026-10-01", end_date: "2026-10-31" }, balances: [], opening_lume_balance: "0.0000", unmatched_transactions: [],
    rows: [
      { row_key: "salary", effective_date: "2026-10-05", description: "Bank incoming Pix", amount: "100.0000", kind: "income", suggested_kind: "income", candidates: [{ transaction_id: "tx", description: "My salary", amount: "100.0000", effective_date: "2026-10-05", kind: "income", account_id: "bank", account_name: "Nubank", ledger_account_id: "bank", category_name: "Salary", reasons: ["Same amount", "Same date", "Same account"], already_linked: false }] },
      { row_key: "later", effective_date: "2026-10-06", description: "Uncertain bank row", amount: "5.0000", kind: "expense", suggested_kind: "expense", candidates: [] },
    ], decisions: [{ row_key: "salary", action: "pending" }, { row_key: "later", action: "pending" }],
  } as unknown as StatementReview;
}

async function openReview({ searched = false, conflictOn = "", failedSave = false } = {}) {
  const review = fixture();
  const remoteMatch = review.rows[0]!.candidates[0]!;
  if (searched) review.rows[0]!.candidates = [];
  let currentVersion = 1;
  let saveAttempt = 0;
  vi.mocked(api).mockImplementation((path, options) => {
    const respond = <T,>(value: T) => Promise.resolve(value);
    if (path === "/api/v1/accounts") return respond([{ id: "bank", name: "Nubank", account_type: "checking", currency: "BRL" }]);
    if (path === "/api/v1/categories") return respond([]);
    if (path === "/api/v1/imports/reviews") return respond([{ id: review.id, filename: review.filename, account_id: "bank", updated_at: review.updated_at }]);
    if (path.includes("/candidates?")) return respond([remoteMatch]);
    if (options?.method === "PUT") {
      saveAttempt += 1;
      if (failedSave) return Promise.reject(new ApiError(503, "Save unavailable"));
      if (conflictOn === "save" && saveAttempt === 1) { currentVersion = 2; return Promise.reject(new ApiError(409, "This review changed in another tab. Reopen it before saving.")); }
      currentVersion += 1;
      return respond({ ...review, version: currentVersion, decisions: (options.body as { decisions: unknown[] }).decisions });
    }
    if (path.endsWith("/apply")) {
      if (conflictOn === "apply") { currentVersion = 2; return Promise.reject(new ApiError(409, "Another row already linked this transaction. Reopen the review.")); }
      return respond({ created: 0, linked: 1, ignored: 0, pending: 1, review: { ...review, version: currentVersion + 1, rows: [{ ...review.rows[0], resolved_action: "link", resolved_transaction_id: "tx" }, review.rows[1]] } });
    }
    return respond({ ...review, version: currentVersion });
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter([
    { path: "/app/imports", element: <ImportStatementsRoute /> },
    { path: "/app/transactions", element: <p>Transactions destination</p> },
  ], { initialEntries: ["/app/imports"] });
  render(<QueryClientProvider client={queryClient}><RouterProvider router={router} /></QueryClientProvider>);
  const user = userEvent.setup();
  await user.click(await screen.findByText("Saved reviews (1)"));
  await user.click(screen.getByRole("button", { name: "Resume" }));
  await screen.findByLabelText("What does this row need?");
  return { user, router };
}

it("resumes, links, saves progress, and applies only reviewed rows", async () => {
  const { user } = await openReview();
  expect(screen.getByLabelText("What does this row need?")).toHaveValue("pending");
  expect(screen.getByRole("button", { name: "Apply reviewed decisions" })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Link this transaction" }));
  await user.click(screen.getByRole("button", { name: "Save progress" }));
  await screen.findByText("Progress saved. Your ledger has not changed.");
  expect(vi.mocked(api).mock.calls.some(([path]) => path.endsWith("/apply"))).toBe(false);
  await user.click(screen.getByRole("button", { name: "Apply reviewed decisions" }));
  expect(await screen.findByText("0 registered · 1 linked · 0 ignored · 1 still pending. Your progress is saved.")).toBeInTheDocument();
  const applied = vi.mocked(api).mock.calls.find(([path]) => path.endsWith("/apply"));
  expect(applied?.[1]?.body).toMatchObject({ version: 2, decisions: [{ row_key: "salary", action: "link", transaction_id: "tx", account_id: "bank" }, { row_key: "later", action: "pending" }] });
});

it("blocks unsaved in-app navigation and can save progress before leaving", async () => {
  const { user } = await openReview();
  await user.click(screen.getByRole("button", { name: "Link this transaction" }));
  await user.click(screen.getByRole("link", { name: "Transactions" }));
  expect(await screen.findByRole("alertdialog")).toHaveTextContent("Save your review before leaving?");
  expect(screen.queryByText("Transactions destination")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Stay here" }));
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  expect(screen.getByLabelText("What does this row need?")).toHaveValue("link");
  await user.click(screen.getByRole("link", { name: "Transactions" }));
  await user.click(screen.getByRole("button", { name: "Save and leave" }));
  expect(await screen.findByText("Transactions destination")).toBeInTheDocument();
  const saveCall = vi.mocked(api).mock.calls.find(([, options]) => options?.method === "PUT");
  expect(saveCall?.[1]?.body).toMatchObject({ decisions: [{ row_key: "salary", action: "link" }, { row_key: "later", action: "pending" }] });
});

it("leaves without saving only when the user explicitly discards changes", async () => {
  const { user } = await openReview();
  await user.click(screen.getByRole("button", { name: "Link this transaction" }));
  await user.click(screen.getByRole("link", { name: "Transactions" }));
  await user.click(screen.getByRole("button", { name: "Discard changes and leave" }));
  expect(await screen.findByText("Transactions destination")).toBeInTheDocument();
  expect(vi.mocked(api).mock.calls.some(([, options]) => options?.method === "PUT")).toBe(false);
});

it("keeps navigation blocked when saving before leaving fails", async () => {
  const { user } = await openReview({ failedSave: true });
  await user.click(screen.getByRole("button", { name: "Link this transaction" }));
  await user.click(screen.getByRole("link", { name: "Transactions" }));
  await user.click(screen.getByRole("button", { name: "Save and leave" }));
  expect(await screen.findByText("Save unavailable")).toBeInTheDocument();
  expect(screen.getByRole("alertdialog")).toBeInTheDocument();
  expect(screen.queryByText("Transactions destination")).not.toBeInTheDocument();
});

it.each(["save", "apply"])("can recover from a %s conflict without reloading the page", async (conflictOn) => {
  const { user } = await openReview({ conflictOn });
  await user.click(screen.getByRole("button", { name: "Link this transaction" }));
  await user.click(screen.getByRole("button", { name: conflictOn === "save" ? "Save progress" : "Apply reviewed decisions" }));
  const reload = await screen.findByRole("button", { name: "Discard local changes and reload" });
  expect(reload).toBeEnabled();
  expect(screen.getByRole("button", { name: "Resume" })).toBeDisabled();
  await user.click(reload);
  await waitFor(() => expect(screen.getByLabelText("What does this row need?")).toHaveValue("pending"));
  expect(screen.queryByText("This review needs to be refreshed.")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Link this transaction" }));
  await user.click(screen.getByRole("button", { name: "Save progress" }));
  await screen.findByText("Progress saved. Your ledger has not changed.");
  const saves = vi.mocked(api).mock.calls.filter(([, options]) => options?.method === "PUT");
  expect(saves.at(-1)?.[1]?.body).toMatchObject({ version: 2 });
});

it("preserves selected searched transaction details while navigating between rows", async () => {
  const { user } = await openReview({ searched: true });
  await user.click(screen.getByRole("button", { name: "Search" }));
  await user.click(await screen.findByRole("button", { name: "Link this transaction" }));
  expect(screen.getByText("My salary")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Next" }));
  await user.click(screen.getByRole("button", { name: "Previous" }));
  expect(screen.getByText("My salary")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Selected" })).toBeInTheDocument();
  expect(screen.getByLabelText("What does this row need?")).toHaveValue("link");
  expect(vi.mocked(api).mock.calls.some(([, options]) => options?.method === "PUT")).toBe(false);
});
