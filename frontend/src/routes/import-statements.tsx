import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ChevronLeft, ChevronRight, FileUp, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useBlocker } from "react-router-dom";

import { ApiError, api } from "../api/client";
import type { Account, Category, MatchCandidate, ReviewApply, ReviewDecision, ReviewSummary, StatementReview } from "../api/types";
import { PageHeader, Panel } from "../components/layout/page";
import { Button } from "../components/ui/button";
import { Field, Input, Select } from "../components/ui/field";
import { Empty, ErrorNotice, Loading } from "../components/ui/states";
import { decisionError, initialDecisions, projectedBalances } from "../features/imports/review";
import { StatementReviewRow } from "../features/imports/review-row";
import { currency } from "../lib/currency";
import { displayDate } from "../lib/dates";

type Source = { filename: string; content: string };
const actionLabels = { pending: "Needs review", create: "Register", link: "Link existing", skip: "Ignore" };

export function ImportStatementsRoute() {
  const queryClient = useQueryClient();
  const [accountId, setAccountId] = useState("");
  const [source, setSource] = useState<Source | null>(null);
  const [review, setReview] = useState<StatementReview | null>(null);
  const [decisions, setDecisions] = useState<Record<string, ReviewDecision>>({});
  const [selectedKey, setSelectedKey] = useState("");
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [fileError, setFileError] = useState("");
  const [dirty, setDirty] = useState(false);
  const [notice, setNotice] = useState("");
  const [discard, setDiscard] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<Record<string, MatchCandidate[]>>({});
  const blocker = useBlocker(dirty);
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: () => api<Account[]>("/api/v1/accounts") });
  const categories = useQuery({ queryKey: ["categories"], queryFn: () => api<Category[]>("/api/v1/categories") });
  const reviews = useQuery({ queryKey: ["import-reviews"], queryFn: () => api<ReviewSummary[]>("/api/v1/imports/reviews") });
  const activeAccounts = accounts.data?.filter((a) => !a.archived_at) ?? [];

  function loadReview(result: StatementReview) {
    setReview(result);
    setDecisions(initialDecisions(result));
    setSelectedKey((current) => result.rows.some((row) => row.row_key === current) ? current : result.rows.find((r) => !r.resolved_action)?.row_key ?? result.rows[0]?.row_key ?? "");
    setDirty(false);
    setDiscard(null);
    setSearchResults({});
  }
  const open = useMutation({
    mutationFn: (id: string) => api<StatementReview>(`/api/v1/imports/reviews/${id}`),
    onSuccess: (result) => { loadReview(result); save.reset(); apply.reset(); if (blocker.state === "blocked") blocker.reset(); setFilter("all"); setSearch(""); setNotice("Saved review opened. Ledger balances and matches have been refreshed."); },
  });
  const start = useMutation({
    mutationFn: () => api<StatementReview>("/api/v1/imports/reviews", { method: "POST", body: { ...source, account_id: accountId } }),
    onSuccess: async (result) => { loadReview(result); save.reset(); apply.reset(); setNotice("Review saved. Each row starts pending until you decide what to do."); await queryClient.invalidateQueries({ queryKey: ["import-reviews"] }); },
  });
  const save = useMutation({
    mutationFn: () => api<StatementReview>(`/api/v1/imports/reviews/${review?.id}`, { method: "PUT", body: { version: review?.version, decisions: review?.rows.map((row) => decisions[row.row_key]) } }),
    onSuccess: async (result) => { loadReview(result); setNotice("Progress saved. Your ledger has not changed."); await queryClient.invalidateQueries({ queryKey: ["import-reviews"] }); },
  });
  const apply = useMutation({
    mutationFn: () => api<ReviewApply>(`/api/v1/imports/reviews/${review?.id}/apply`, { method: "POST", body: { version: review?.version, decisions: review?.rows.map((row) => decisions[row.row_key]) } }),
    onSuccess: async (result) => {
      loadReview(result.review);
      setNotice(`${result.created} registered · ${result.linked} linked · ${result.ignored} ignored · ${result.pending} still pending. Your progress is saved.`);
      await queryClient.invalidateQueries();
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api<void>(`/api/v1/imports/reviews/${id}`, { method: "DELETE" }),
    onSuccess: async (_, id) => { if (review?.id === id) { setReview(null); setDirty(false); } setDiscard(null); setNotice("Saved review and uploaded file deleted. Existing transactions and reconciliation links remain."); await queryClient.invalidateQueries({ queryKey: ["import-reviews"] }); },
  });
  const conflict = [save.error, apply.error].some((error) => error instanceof ApiError && error.status === 409);
  const busy = start.isPending || open.isPending || save.isPending || apply.isPending || remove.isPending;
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  async function saveAndLeave() {
    try {
      await save.mutateAsync();
      if (blocker.state === "blocked") blocker.proceed();
    } catch {
      // The save error stays visible; navigation remains blocked until the user decides.
    }
  }

  function update(key: string, change: Partial<ReviewDecision>) {
    setDecisions((all) => ({ ...all, [key]: { ...all[key]!, ...change } }));
    setDirty(true);
    setNotice("");
  }
  async function chooseFile(file: File | undefined) {
    setFileError("");
    setSource(null);
    if (!file) return;
    if (file.size > 1_000_000) { setFileError("Choose a statement smaller than 1 MB."); return; }
    if (!/\.(csv|ofx)$/i.test(file.name)) { setFileError("Choose a CSV or OFX statement."); return; }
    try {
      const buffer = await file.arrayBuffer();
      let content: string;
      try { content = new TextDecoder("utf-8", { fatal: true }).decode(buffer); }
      catch { content = new TextDecoder("windows-1252").decode(buffer); }
      setSource({ filename: file.name, content });
    } catch { setFileError("Could not read this file. Choose it again."); }
  }

  const rows = review?.rows ?? [];
  const pending = rows.filter((r) => !r.resolved_action && decisions[r.row_key]?.action === "pending").length;
  const handled = rows.filter((r) => r.resolved_action).length;
  const ready = rows.filter((r) => !r.resolved_action && decisions[r.row_key]?.action !== "pending");
  const errors = ready.filter((r) => decisionError(r, decisions[r.row_key]!, accounts.data ?? [], review?.account_id ?? ""));
  const selectedLinks = ready.filter((r) => decisions[r.row_key]?.action === "link").map((r) => `${decisions[r.row_key]?.transaction_id}|${decisions[r.row_key]?.account_id ?? review?.account_id}`);
  const duplicateLink = new Set(selectedLinks).size !== selectedLinks.length;
  const filtered = rows.filter((r) => {
    const action = r.resolved_action ? "handled" : decisions[r.row_key]?.action ?? "pending";
    return (filter === "all" || filter === action || (filter === "ready" && action !== "pending" && action !== "handled")) && r.description.toLocaleLowerCase().includes(search.toLocaleLowerCase());
  });
  const selected = filtered.find((r) => r.row_key === selectedKey) ?? filtered[0];
  const selectedIndex = selected ? filtered.indexOf(selected) : -1;
  const balances = review ? projectedBalances(review, decisions, accounts.data ?? []) : [];
  const createCount = ready.filter((r) => decisions[r.row_key]?.action === "create").length;
  const linkCount = ready.filter((r) => decisions[r.row_key]?.action === "link").length;
  const ignoreCount = ready.filter((r) => decisions[r.row_key]?.action === "skip").length;
  const allErrors = [start.error, open.error, save.error, apply.error, remove.error];

  return <div className="page">
    <PageHeader eyebrow="Statement reconciliation" title="Review a statement" description="Recognize each movement, compare it with Lume, and register only what is missing." action={<Link className="button button-secondary button-md" to="/app/transactions"><ArrowLeft size={17} /> Transactions</Link>} />
    {notice ? <p className="review-notice" role="status">{notice}</p> : null}
    {blocker.state === "blocked" ? <div className="review-leave-prompt" role="alertdialog" aria-labelledby="review-leave-title" aria-describedby="review-leave-description">
      <h2 id="review-leave-title">Save your review before leaving?</h2>
      <p id="review-leave-description">Your latest decisions have not been saved. Saving progress does not register any transactions.</p>
      <Button disabled={busy || conflict} onClick={() => void saveAndLeave()}>Save and leave</Button>
      <Button variant="secondary" disabled={busy} onClick={() => blocker.proceed()}>Discard changes and leave</Button>
      <Button variant="ghost" disabled={busy} onClick={() => blocker.reset()}>Stay here</Button>
    </div> : null}
    {conflict && review ? <div className="review-conflict" role="alert">
      <strong>This review needs to be refreshed.</strong>
      <p>Another save or reconciliation may have changed it. Reloading replaces your unsaved decisions with the latest saved progress and refreshes matches. You can inspect your current choices before reloading.</p>
      <Button variant="secondary" disabled={busy} onClick={() => open.mutate(review.id)}>Discard local changes and reload</Button>
    </div> : null}
    {allErrors.map((error, i) => error ? <ErrorNotice key={i} message={error.message} /> : null)}
    <Panel title="Open a statement" subtitle="CSV or OFX · up to 1 MB and 500 rows">
      {accounts.isPending ? <Loading /> : accounts.error ? <ErrorNotice message={accounts.error.message} /> : !activeAccounts.length ? <Empty title="No account yet" body="Create an account before reviewing a statement." /> : <fieldset className="import-source" disabled={busy || dirty}>
        <Field label="Statement file"><Input type="file" accept=".csv,.ofx,text/csv" onChange={(event) => void chooseFile(event.target.files?.[0])} /></Field>
        <Field label="Account this statement describes"><Select value={accountId} onChange={(event) => setAccountId(event.target.value)}><option value="">Choose the bank or card account</option>{activeAccounts.map((a) => <option value={a.id} key={a.id}>{a.name}</option>)}</Select></Field>
        <p className="muted">A checking statement can include payments to your card and investments. You can choose both sides of each movement during review. Card purchases need the card’s own statement.</p>
        <Button disabled={!source || !accountId || busy || dirty} onClick={() => { setFilter("all"); setSearch(""); start.mutate(); }}><FileUp size={17} /> {start.isPending ? "Opening…" : "Open review"}</Button>
        <p className="muted">The uploaded statement and saved decisions are stored privately in your Lume account so you can return later. Nothing enters your ledger until you apply decisions.</p>
      </fieldset>}
      {fileError ? <ErrorNotice message={fileError} /> : null}
      {reviews.error ? <ErrorNotice message={reviews.error.message} /> : reviews.data?.length ? <details className="review-saved"><summary>Saved reviews ({reviews.data.length})</summary>{reviews.data.map((item) => <div className="review-saved-item" key={item.id}>
        <span><strong>{item.filename}</strong><small>{accounts.data?.find((a) => a.id === item.account_id)?.name} · Saved {new Date(item.updated_at + "Z").toLocaleString()}</small></span>
        <Button variant="secondary" size="sm" disabled={busy || dirty} onClick={() => open.mutate(item.id)}>Resume</Button>
        <Button variant="ghost" size="sm" disabled={busy || dirty} onClick={() => setDiscard(item.id)}>Delete saved file</Button>
      </div>)}</details> : null}
      {discard ? <div className="review-delete-confirm"><p>Delete this saved review and uploaded file? Registered transactions and reconciliation links will remain.</p><Button variant="danger" disabled={busy} onClick={() => remove.mutate(discard)}>Delete review</Button><Button variant="ghost" onClick={() => setDiscard(null)}>Cancel</Button></div> : null}
      {dirty ? <p className="form-helper warning">Save your progress before opening another statement. Changes are not saved automatically.</p> : null}
    </Panel>

    {review ? <>
      <Panel title={review.filename} subtitle={`${review.metadata.institution ?? "Statement"} · ${displayDate(review.metadata.start_date)} – ${displayDate(review.metadata.end_date)}${review.metadata.account_last_four ? ` · Account ending ${review.metadata.account_last_four}` : ""}`} className="import-review">
        <div className="review-progress"><span>{handled} handled</span><span>{ready.length} decisions ready</span><span>{pending} need review</span><span>{rows.length} total rows</span></div>
        <progress className="review-progress-bar" value={handled + ready.length - errors.length} max={rows.length} aria-label="Statement review progress" />
        <div className="review-toolbar"><Field label="Show rows"><Select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">All movements</option><option value="pending">Needs review</option><option value="ready">Decisions ready</option><option value="handled">Already handled</option></Select></Field><Field label="Find a statement row"><Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search bank description" /></Field></div>
        {categories.isPending ? <Loading /> : categories.error ? <ErrorNotice message={categories.error.message} /> : <div className="review-workspace">
          <nav className="review-checklist" aria-label="Statement rows">{filtered.map((row) => <button type="button" key={row.row_key} aria-current={selected?.row_key === row.row_key ? "true" : undefined} className={selected?.row_key === row.row_key ? "is-selected" : ""} onClick={() => setSelectedKey(row.row_key)}>
            <span>{displayDate(row.effective_date)}<strong>{row.kind === "expense" ? "−" : "+"}{currency(row.amount)}</strong></span>
            <strong>{row.description}</strong><small>{row.resolved_action ? row.resolved_action === "skip" ? "Ignored" : "Handled" : actionLabels[decisions[row.row_key]?.action ?? "pending"]}{row.resolution_warning ? " · Check linked transaction" : ""}{row.candidates.length && !row.resolved_action ? ` · ${row.candidates.length} possible ${row.candidates.length === 1 ? "match" : "matches"}` : ""}</small>
          </button>)}</nav>
          {selected ? <div className="review-detail">
            <div className="review-navigation"><Button variant="ghost" size="sm" disabled={selectedIndex <= 0} onClick={() => setSelectedKey(filtered[selectedIndex - 1]!.row_key)}><ChevronLeft size={16} /> Previous</Button><span>{selectedIndex + 1} of {filtered.length}</span><Button variant="ghost" size="sm" disabled={selectedIndex >= filtered.length - 1} onClick={() => setSelectedKey(filtered[selectedIndex + 1]!.row_key)}>Next <ChevronRight size={16} /></Button></div>
            <div className="review-bank-row"><span className="eyebrow">Original bank movement</span><h3>{selected.kind === "expense" ? "−" : "+"}{currency(selected.amount)}</h3><span>{displayDate(selected.effective_date)} · {accounts.data?.find((a) => a.id === review.account_id)?.name}</span><p>{selected.description}</p>{selected.source_id ? <details><summary>Bank reference</summary><small>{selected.source_id}</small></details> : null}</div>
            <StatementReviewRow key={selected.row_key} row={selected} decision={decisions[selected.row_key]!} reviewId={review.id} statementAccount={review.account_id} accounts={accounts.data ?? []} categories={categories.data} searchResults={searchResults[selected.row_key] ?? []} onSearchResults={(matches) => setSearchResults((all) => ({ ...all, [selected.row_key]: matches }))} update={(change) => update(selected.row_key, change)} disabled={busy} />
          </div> : <Empty title="No rows in this view" body="Change the filter or search to continue reviewing." />}
        </div>}
      </Panel>
      <Panel title="Balance preview" subtitle={`Balances as of ${displayDate(review.metadata.balance_date ?? review.metadata.end_date)} · only complete new registrations change the projection`} className="import-review">
        <div className="review-balance-table"><table><thead><tr><th>Account</th><th>In Lume</th><th>After registrations</th><th>Bank closing balance</th><th>Difference</th></tr></thead><tbody>{balances.map((balance) => <tr key={balance.account_id}><td>{balance.account_name}</td><td>{currency(balance.current_balance)}</td><td>{currency(balance.projected_balance)}</td><td>{balance.statement_closing_balance != null ? currency(balance.statement_closing_balance) : "Not in this file"}</td><td>{balance.difference != null ? currency(balance.difference) : "—"}</td></tr>)}</tbody></table></div>
        {review.metadata.inferred_opening_balance != null ? <p className="panel-note">Opening balance inferred from this statement: {currency(review.metadata.inferred_opening_balance)} · Lume before the period: {currency(review.opening_lume_balance)} · Difference: {currency(review.opening_difference ?? "0")}. A matching closing balance can still hide earlier discrepancies.</p> : null}
        <p className="panel-note">Difference = bank balance − projected Lume balance. Credit cards use signed balances; a negative balance means money owed. Pending rows are excluded.</p>
        <details className="review-saved"><summary>Lume entries still unmatched in this period ({review.unmatched_transactions.length})</summary><p className="panel-note">These records are not necessarily wrong or missing from the bank. Compare them before editing anything. Save progress to refresh this list after choosing links.</p>{review.unmatched_transactions.map((tx) => <div className="review-unmatched" key={tx.transaction_id}><strong>{tx.description}</strong><span>{displayDate(tx.effective_date)} · {currency(tx.amount)} · {tx.account_name}{tx.destination_account_name ? ` → ${tx.destination_account_name}` : ""}</span></div>)}</details>
      </Panel>
      <div className="review-footer">
        <div><strong>{createCount} to register · {linkCount} to link · {ignoreCount} to ignore</strong><small>{pending} rows will remain pending. {dirty ? "You have unsaved changes." : "Progress saved."}</small></div>
        <Button variant="secondary" disabled={busy || !dirty || conflict} onClick={() => save.mutate()}><Save size={17} /> {save.isPending ? "Saving…" : "Save progress"}</Button>
        <Button disabled={busy || conflict || !ready.length || errors.length > 0 || duplicateLink || accounts.isPending || categories.isPending} onClick={() => apply.mutate()}>{apply.isPending ? "Applying…" : "Apply reviewed decisions"}</Button>
        {errors.length ? <p className="form-helper warning">Complete {errors.length} selected {errors.length === 1 ? "row" : "rows"} before applying. You can save incomplete progress or leave a row pending.</p> : null}
        {duplicateLink ? <p className="form-helper warning">Two rows are linked to the same transaction for the same account. Review those decisions before applying.</p> : null}
      </div>
    </> : null}
  </div>;
}
