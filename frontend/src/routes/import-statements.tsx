import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, FileUp } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import type { Account, Category, StatementCommit, StatementDecision, StatementPreview } from "../api/types";
import { PageHeader, Panel } from "../components/layout/page";
import { Button } from "../components/ui/button";
import { Field, Input, Select } from "../components/ui/field";
import { Empty, ErrorNotice, Loading } from "../components/ui/states";
import { currency } from "../lib/currency";
import { displayDate } from "../lib/dates";

type Source = { account_id: string; filename: string; content: string };

export function ImportStatementsRoute() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [accountId, setAccountId] = useState("");
  const [source, setSource] = useState<Source | null>(null);
  const [preview, setPreview] = useState<StatementPreview | null>(null);
  const [decisions, setDecisions] = useState<Record<string, StatementDecision>>({});
  const [fileError, setFileError] = useState("");
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: () => api<Account[]>("/api/v1/accounts") });
  const categories = useQuery({ queryKey: ["categories"], queryFn: () => api<Category[]>("/api/v1/categories") });
  const selectedAccount = accountId || accounts.data?.[0]?.id || "";
  const previewRequest = useMutation({
    mutationFn: (payload: Source) => api<StatementPreview>("/api/v1/imports/preview", { method: "POST", body: payload }),
    onSuccess: (result, payload) => {
      setSource(payload);
      setPreview(result);
      setDecisions(Object.fromEntries(result.rows.map((row) => [row.row_key, {
        row_key: row.row_key,
        action: row.matched_transaction_id ? "skip" : "create",
        kind: row.kind,
        category_id: row.suggested_category_id,
        counterparty_account_id: null,
        remember_category: false,
        allow_possible_match: false,
      }])));
    },
  });
  const commit = useMutation({
    mutationFn: () => api<StatementCommit>("/api/v1/imports/commit", {
      method: "POST",
      body: { ...source, decisions: preview?.rows.map((row) => decisions[row.row_key]) },
    }),
    onSuccess: async () => {
      await queryClient.invalidateQueries();
      void navigate("/app/transactions");
    },
  });
  const update = (key: string, change: Partial<StatementDecision>) => setDecisions((all) => {
    const previous = all[key];
    return previous ? { ...all, [key]: { ...previous, ...change } } : all;
  });
  const unresolved = preview?.rows.some((row) => {
    const decision = decisions[row.row_key];
    if (!decision || decision.action === "skip") return false;
    if (row.matched_transaction_id && !decision.allow_possible_match) return true;
    return decision.kind === "transfer" ? !decision.counterparty_account_id : !decision.category_id;
  }) ?? false;
  const chosenCount = preview?.rows.filter((row) => decisions[row.row_key]?.action === "create").length ?? 0;

  async function chooseFile(file: File | undefined) {
    setFileError("");
    setPreview(null);
    if (!file || !selectedAccount) return;
    if (file.size > 1_000_000) { setFileError("Choose a statement smaller than 1 MB."); return; }
    const buffer = await file.arrayBuffer();
    let content: string;
    try { content = new TextDecoder("utf-8", { fatal: true }).decode(buffer); }
    catch { content = new TextDecoder("windows-1252").decode(buffer); }
    previewRequest.mutate({ account_id: selectedAccount, filename: file.name, content });
  }

  return <div className="page">
    <PageHeader eyebrow="Reviewed import" title="Import a statement" description="Bring bank or card activity into Lume without duplicating transactions you already recorded." action={<Link className="button button-secondary button-md" to="/app/transactions"><ArrowLeft size={17} /> Transactions</Link>} />
    <Panel title="Choose a statement" subtitle="CSV or OFX, up to 1 MB and 500 rows">
      {accounts.isPending ? <Loading /> : accounts.error ? <ErrorNotice message={accounts.error.message} /> : !accounts.data.length ? <Empty title="No account yet" body="Create an account before importing its statement." /> : <div className="import-source">
        <Field label="Lume account"><Select value={selectedAccount} onChange={(event) => { setAccountId(event.target.value); setPreview(null); }}><option value="">Choose account</option>{accounts.data.map((account) => <option value={account.id} key={account.id}>{account.name}</option>)}</Select></Field>
        <Field label="Statement file"><Input type="file" accept=".csv,.ofx,text/csv" onChange={(event) => void chooseFile(event.target.files?.[0])} /></Field>
        <p className="muted">Your file is parsed for preview. Nothing changes until you approve the selected rows below.</p>
      </div>}
      {fileError ? <ErrorNotice message={fileError} /> : null}
      {previewRequest.error ? <ErrorNotice message={previewRequest.error.message} /> : null}
    </Panel>
    {previewRequest.isPending ? <Loading /> : preview ? <Panel title="Review rows" subtitle={`${preview.rows.length} rows · ${chosenCount} selected to create`} className="import-review">
      <p className="panel-note">Possible matches are skipped unless you explicitly choose to import them. Review card payments, transfers between your accounts, loans and reimbursements: change their type to Transfer and choose the other account. Category suggestions come from your earlier approved imports.</p>
      {categories.isPending ? <Loading /> : categories.error ? <ErrorNotice message={categories.error.message} /> : <div className="import-rows">{preview.rows.map((row) => {
        const decision = decisions[row.row_key];
        if (!decision) return null;
        const kind = decision.kind ?? row.kind;
        const available = categories.data.filter((category) => category.kind === kind);
        return <article key={row.row_key} className={row.matched_transaction_id ? "possible-match" : ""}>
          <div className="import-row-summary"><strong>{row.description}</strong><span>{displayDate(row.effective_date)} · {row.kind === "expense" ? "−" : "+"}{currency(row.amount)}{row.matched_transaction_id ? " · possible match" : ""}</span></div>
          <div className="import-row-controls">
            <Field label="Action"><Select value={decision.action} onChange={(event) => update(row.row_key, { action: event.target.value as StatementDecision["action"] })}><option value="create">Create</option><option value="skip">Skip</option></Select></Field>
            {decision.action === "create" ? <>{row.matched_transaction_id ? <label className="checkbox-row"><input type="checkbox" checked={decision.allow_possible_match ?? false} onChange={(event) => update(row.row_key, { allow_possible_match: event.target.checked })} /> Import despite possible match</label> : null}<Field label="Type"><Select value={kind} onChange={(event) => update(row.row_key, { kind: event.target.value as StatementDecision["kind"], category_id: null, counterparty_account_id: null })}><option value={row.kind}>{row.kind === "income" ? "Income" : "Expense"}</option><option value="transfer">Transfer</option></Select></Field>
            {kind === "transfer" ? <Field label="Other account"><Select value={decision.counterparty_account_id ?? ""} onChange={(event) => update(row.row_key, { counterparty_account_id: event.target.value || null })}><option value="">Choose account</option>{accounts.data?.filter((account) => account.id !== selectedAccount).map((account) => <option value={account.id} key={account.id}>{account.name}</option>)}</Select></Field> : <><Field label="Category"><Select value={decision.category_id ?? ""} onChange={(event) => update(row.row_key, { category_id: event.target.value || null })}><option value="">Choose category</option>{available.map((category) => <option value={category.id} key={category.id}>{category.name}</option>)}</Select></Field><label className="checkbox-row"><input type="checkbox" checked={decision.remember_category} onChange={(event) => update(row.row_key, { remember_category: event.target.checked })} /> Remember this category</label></>}
            </> : null}
          </div>
        </article>;
      })}</div>}
      {unresolved ? <p className="form-helper warning">Choose a category or other account for every selected row, and confirm any possible match you want to import.</p> : null}
      {commit.error ? <ErrorNotice message={commit.error.message} /> : null}
      <Button disabled={commit.isPending || unresolved || chosenCount === 0} onClick={() => commit.mutate()}><FileUp size={17} /> {commit.isPending ? "Importing…" : `Import ${chosenCount} selected rows`}</Button>
    </Panel> : null}
  </div>;
}
