import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../api/client";
import type { Account, Category, MatchCandidate, ReviewDecision, ReviewRow } from "../../api/types";
import { Button } from "../../components/ui/button";
import { Field, Input, Select } from "../../components/ui/field";
import { ErrorNotice } from "../../components/ui/states";
import { currency } from "../../lib/currency";
import { displayDate } from "../../lib/dates";
import { decisionError } from "./review";

function CandidateDetails({ match }: { match: MatchCandidate }) {
  return <>
    <strong>{match.description}</strong>
    <span>{displayDate(match.effective_date)} · {currency(match.amount)} · {match.kind}</span>
    <span>{match.account_name}{match.destination_account_name ? ` → ${match.destination_account_name}` : ""}{match.category_name ? ` · ${match.category_name}` : ""}</span>
    <small>{match.reasons.join(" · ")}{match.already_linked ? " · Already linked to another row" : ""}</small>
  </>;
}

export function StatementReviewRow({ row, decision, accounts, categories, statementAccount, reviewId, searchResults, onSearchResults, update, disabled }: {
  row: ReviewRow; decision: ReviewDecision; accounts: Account[]; categories: Category[];
  statementAccount: string; reviewId: string; searchResults: MatchCandidate[]; onSearchResults: (matches: MatchCandidate[]) => void; update: (change: Partial<ReviewDecision>) => void; disabled: boolean;
}) {
  const [search, setSearch] = useState("");
  const lookup = useMutation({ mutationFn: () => api<MatchCandidate[]>(`/api/v1/imports/reviews/${reviewId}/candidates?row_key=${encodeURIComponent(row.row_key)}&search=${encodeURIComponent(search)}`), onSuccess: onSearchResults });
  const matches = [...row.candidates, ...searchResults.filter((m) => !row.candidates.some((candidate) => candidate.transaction_id === m.transaction_id))];
  const anchor = decision.account_id ?? statementAccount;
  const kind = decision.kind ?? row.kind;
  const error = decisionError(row, decision, accounts, statementAccount);
  const selected = matches.find((match) => match.transaction_id === decision.transaction_id);
  const hasMatch = matches.some((match) => match.ledger_account_id === anchor);
  const sameLegInStatement = row.candidates.some((m) => m.transaction_id === decision.transaction_id && m.ledger_account_id === statementAccount);

  if (row.resolved_action) return <div className="review-resolved" role="status">
    <strong>{row.resolved_action === "skip" ? "Ignored" : row.resolved_action === "create" ? "Registered in Lume" : "Linked to an existing transaction"}</strong>
    <p>{row.resolved_action === "skip" ? "This statement row was left out of your ledger." : "This row is already handled. Reopening or reuploading the statement will not create another transaction."}</p>
    {row.resolution_warning ? <p className="form-helper warning">{row.resolution_warning}</p> : null}
    {row.resolved_transaction_id ? <Link className="text-link" to="/app/transactions">View your transactions</Link> : null}
  </div>;

  return <fieldset className="review-editor" disabled={disabled}>
    <legend className="sr-only">Decide how to handle this statement row</legend>
    <Field label="What does this row need?"><Select value={decision.action} onChange={(event) => update({ action: event.target.value as ReviewDecision["action"] })}>
      <option value="pending">Needs review / decide later</option>
      <option value="link">Already registered — link existing</option>
      <option value="create">Register a new transaction</option>
      <option value="skip">Ignore this row</option>
    </Select></Field>
    {decision.action === "pending" || decision.action === "link" ? <div className="review-candidates">
      <h3>Compare with Lume</h3>
      <p className="panel-note">Suggestions use amount, direction and nearby dates across your accounts. Check the purpose and accounts before linking.</p>
      {matches.length ? matches.map((match) => <div className={`review-candidate ${decision.transaction_id === match.transaction_id && decision.action === "link" ? "is-selected" : ""}`} key={match.transaction_id}>
        <div><CandidateDetails match={match} /></div>
        <Button variant="secondary" size="sm" disabled={match.already_linked} onClick={() => update({ action: "link", transaction_id: match.transaction_id, account_id: match.ledger_account_id })}>
          {decision.transaction_id === match.transaction_id && decision.action === "link" ? "Selected" : "Link this transaction"}
        </Button>
      </div>) : <p className="muted">No nearby transaction with the same amount and direction.</p>}
      <form className="review-search" onSubmit={(event) => { event.preventDefault(); lookup.mutate(); }}>
        <Field label="Find another existing transaction"><Input value={search} maxLength={100} onChange={(event) => setSearch(event.target.value)} placeholder="Search your description, across all dates" /></Field>
        <Button type="submit" variant="secondary" disabled={lookup.isPending}>{lookup.isPending ? "Searching…" : "Search"}</Button>
      </form>
      <p className="panel-note">Search shows up to 50 transactions with this amount and direction, across all dates.</p>
      {lookup.error ? <ErrorNotice message={lookup.error.message} /> : null}
      {decision.action === "link" && selected ? <p className="panel-note">Linking keeps “{selected.description}” and its existing accounts and category. No balance changes.{!sameLegInStatement ? " This transaction uses a different account or date; verify that it represents this bank movement." : ""}</p> : null}
    </div> : null}
    {decision.action === "create" ? <>
      <div className="review-fields">
        <Field label="Your description"><Input value={decision.description ?? row.description.slice(0, 160)} maxLength={160} onChange={(event) => update({ description: event.target.value })} /></Field>
        <Field label="Transaction type"><Select value={kind} onChange={(event) => update({ kind: event.target.value as ReviewDecision["kind"], category_id: null, counterparty_account_id: null, remember_category: false })}>
          <option value={row.kind}>{row.kind === "income" ? "Income" : "Expense"}</option><option value="transfer">Transfer / card payment / loan / repayment</option>
        </Select></Field>
        <Field label={row.kind === "income" ? "Account receiving the money" : "Account the money leaves"}><Select value={anchor} onChange={(event) => update({ account_id: event.target.value, allow_possible_match: false })}>
          {accounts.filter((a) => !a.archived_at).map((a) => <option value={a.id} key={a.id}>{a.name}</option>)}
        </Select></Field>
        {kind === "transfer" ? <Field label={row.kind === "income" ? "From account" : "To account"}><Select value={decision.counterparty_account_id ?? ""} onChange={(event) => update({ counterparty_account_id: event.target.value || null })}>
          <option value="">Choose the other account</option>{accounts.filter((a) => a.id !== anchor && !a.archived_at).map((a) => <option value={a.id} key={a.id}>{a.name} · {a.account_type.replaceAll("_", " ")}</option>)}
        </Select></Field> : <Field label="Category"><Select value={decision.category_id ?? ""} onChange={(event) => update({ category_id: event.target.value || null })}>
          <option value="">Choose a category</option>{categories.filter((c) => c.kind === kind && !c.archived_at).map((c) => <option value={c.id} key={c.id}>{c.name}</option>)}
        </Select></Field>}
      </div>
      {kind === "transfer" ? <p className="panel-note">{row.kind === "income" ? accounts.find((a) => a.id === decision.counterparty_account_id)?.name ?? "Other account" : accounts.find((a) => a.id === anchor)?.name} → {row.kind === "income" ? accounts.find((a) => a.id === anchor)?.name : accounts.find((a) => a.id === decision.counterparty_account_id)?.name ?? "Other account"}. Transfers move money between accounts without counting as income or spending.</p> : <label className="checkbox-row"><input type="checkbox" checked={decision.remember_category ?? false} onChange={(event) => update({ remember_category: event.target.checked })} /> Suggest this category next time</label>}
      {anchor !== statementAccount ? <p className="form-helper warning">You are assigning this row to a different account. It will not change the mapped statement account’s balance.</p> : null}
      {hasMatch ? <label className="checkbox-row"><input type="checkbox" checked={decision.allow_possible_match ?? false} onChange={(event) => update({ allow_possible_match: event.target.checked })} /> I reviewed the possible match; this is a separate transaction</label> : null}
      <Button variant="ghost" onClick={() => update({ action: "link" })}>Compare with existing transactions</Button>
    </> : null}
    {decision.action === "skip" ? <p className="panel-note">This row will be marked ignored when you apply your decisions. Nothing will be added to Lume.</p> : null}
    {error ? <p className="form-helper warning">{error}</p> : null}
  </fieldset>;
}
