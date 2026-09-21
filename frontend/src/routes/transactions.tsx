import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp, Pencil, Search, Undo2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import type { Account, Category, Transaction, TransactionPage } from "../api/types";
import { PageHeader, Panel } from "../components/layout/page";
import { Button } from "../components/ui/button";
import { Input, Select } from "../components/ui/field";
import { Empty, ErrorNotice, Loading } from "../components/ui/states";
import { QuickAdd } from "../features/transactions/quick-add";
import { TransactionDialog } from "../features/transactions/transaction-dialog";
import { currency } from "../lib/currency";
import { displayDate } from "../lib/dates";

export function TransactionsRoute() {
  const [kind, setKind] = useState("");
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<Transaction | null>(null);
  const queryClient = useQueryClient();
  const queryString = useMemo(() => {
    const params = new URLSearchParams({ limit: "100" });
    if (kind) params.set("kind", kind);
    if (search.trim()) params.set("search", search.trim());
    return params.toString();
  }, [kind, search]);
  const transactions = useQuery({ queryKey: ["transactions", queryString], queryFn: () => api<TransactionPage>(`/api/v1/transactions?${queryString}`) });
  const accounts = useQuery({ queryKey: ["accounts", "all"], queryFn: () => api<Account[]>("/api/v1/accounts?include_archived=true") });
  const categories = useQuery({ queryKey: ["categories", "all"], queryFn: () => api<Category[]>("/api/v1/categories?include_archived=true") });
  const voidTransaction = useMutation({ mutationFn: (id: string) => api<Transaction>(`/api/v1/transactions/${id}/void`, { method: "POST" }), onSuccess: () => queryClient.invalidateQueries() });
  const account = (id: string) => accounts.data?.find((item) => item.id === id);
  const category = (id: string | null) => categories.data?.find((item) => item.id === id);
  const accountLabel = (id: string) => { const item = account(id); return item ? `${item.name}${item.archived_at ? " (Archived)" : ""}` : "Account"; };
  const categoryLabel = (id: string | null) => { const item = id ? category(id) : null; return item ? `${item.name}${item.archived_at ? " (Archived)" : ""}` : "Transfer"; };
  return <div className="page"><PageHeader eyebrow="Ledger" title="Transactions" description="Every movement, searchable and easy to review." action={<div className="row-actions"><Link className="button button-secondary button-md" to="/app/imports"><FileUp size={17} /> Import statement</Link><QuickAdd /></div>} /><Panel title="Activity" action={<div className="filters"><label className="search-field"><Search size={17} /><Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search descriptions" aria-label="Search transactions" /></label><Select value={kind} onChange={(event) => setKind(event.target.value)} aria-label="Filter by type"><option value="">All types</option><option value="expense">Expenses</option><option value="income">Income</option><option value="transfer">Transfers</option></Select></div>}>
    {transactions.isPending ? <Loading /> : transactions.error ? <ErrorNotice message={transactions.error.message} /> : transactions.data.items.length === 0 ? <Empty title="No transactions found" body="Add your first transaction or adjust these filters." /> : <div className="transaction-list">{transactions.data.items.map((item) => <article key={item.id}><span className={`transaction-mark ${item.kind}`}>{item.kind === "income" ? "+" : item.kind === "expense" ? "−" : "↗"}</span><div><strong>{item.description}</strong><small>{categoryLabel(item.category_id)} · {accountLabel(item.account_id)}{item.destination_account_id ? ` → ${accountLabel(item.destination_account_id)}` : ""} · {displayDate(item.effective_date)}</small></div><span className={`transaction-amount ${item.kind}`}>{item.kind === "expense" ? "−" : item.kind === "income" ? "+" : ""}{currency(item.amount)}</span><div className="row-actions"><Button variant="ghost" size="icon" title="Edit transaction" aria-label={`Edit ${item.description}`} onClick={() => setEditing(item)}><Pencil size={16} /></Button><Button variant="ghost" size="icon" title="Void transaction" aria-label={`Void ${item.description}`} onClick={() => voidTransaction.mutate(item.id)}><Undo2 size={16} /></Button></div></article>)}</div>}
  </Panel><TransactionDialog open={editing !== null} onOpenChange={(open) => { if (!open) setEditing(null); }} transaction={editing} /></div>;
}
