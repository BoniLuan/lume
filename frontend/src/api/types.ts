import type { components } from "./generated-types";

export type Account = components["schemas"]["AccountResponse"];
export type AccountLedger = components["schemas"]["AccountLedgerResponse"];
export type AccountReconciliation = components["schemas"]["AccountReconciliationResponse"];
export type SpendingInsights = components["schemas"]["SpendingInsightsResponse"];
export type AccountCreate = components["schemas"]["AccountCreate"];
export type Budget = components["schemas"]["BudgetResponse"];
export type Category = components["schemas"]["CategoryResponse"];
export type CategoryCreate = components["schemas"]["CategoryCreate"];
export type Dashboard = components["schemas"]["DashboardResponse"];
export type Recurring = components["schemas"]["RecurringResponse"];
export type RecurringCreate = components["schemas"]["RecurringCreate"];
export type Session = components["schemas"]["SessionResponse"];
export type SessionItem = components["schemas"]["SessionListItem"];
export type Transaction = components["schemas"]["TransactionResponse"];
export type TransactionCreate = components["schemas"]["TransactionCreate"];
export type TransactionPage = components["schemas"]["TransactionPage"];
export type User = components["schemas"]["UserResponse"];

export type StatementPreview = components["schemas"]["StatementPreviewResponse"];
export type StatementDecision = components["schemas"]["StatementDecision"];
export type StatementCommit = components["schemas"]["StatementCommitResponse"];

export type StatementReview = components["schemas"]["ReviewResponse"];
export type ReviewDecision = components["schemas"]["ReviewDecision"];
export type ReviewSummary = components["schemas"]["ReviewSummary"];
export type ReviewRow = components["schemas"]["ReviewRow"];
export type MatchCandidate = components["schemas"]["MatchCandidate"];
export type ReviewApply = components["schemas"]["ReviewApplyResponse"];
