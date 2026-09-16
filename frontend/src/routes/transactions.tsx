import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, Undo2 } from "lucide-react";
import { useMemo, useState } from "react";

import { api } from "../api/client";
import type { Account, Category, Transaction, TransactionPage } from "../api/types";
import { PageHeader, Panel } from "../components/layout/page";
import { Button } from "../components/ui/button";
import { Input, Select } from "../components/ui/field";
import { Empty, ErrorNotice, Loading } from "../components/ui/states";
import { QuickAdd } from "../features/transactions/quick-add";
import { currency } from "../lib/currency";
import { displayDate } from "../lib/dates";

export function TransactionsRoute() {
  const [kind, setKind] = useState(""); const [search, setSearch] = useState("");
  const queryClient = useQueryClient();
  const queryString = useMemo(() => { const params = new URLSearchParams({ limit: "100" }); if (kind) params.set("kind", kind); if (search.trim()) params.set("search", search.trim()); return params.toString(); }, [kind, search]);
  const transactions = useQuery({ queryKey: ["transactions", queryString], queryFn: () => api<TransactionPage>(`/api/v1/transactions?${queryString}`) });
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: () => api<Account[]>("/api/v1/accounts") });
  const categories = useQuery({ queryKey: ["categories"], queryFn: () => api<Category[]>("/api/v1/categories") });
  const voidTransaction = useMutation({ mutationFn: (id: string) => api<Transaction>(`/api/v1/transactions/${id}/void`, { method: "POST" }), onSuccess: () => queryClient.invalidateQueries() });
  const accountName = (id: string) => accounts.data?.find((item) => item.id === id)?.name ?? "Account";
  const categoryName = (id: string | null) => categories.data?.find((item) => item.id === id)?.name ?? "Transfer";
  return <div className="page"><PageHeader eyebrow="Ledger" title="Transactions" description="Every movement, searchable and easy to review." action={<QuickAdd />} /><Panel title="Activity" action={<div className="filters"><label className="search-field"><Search size={17} /><Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search descriptions" aria-label="Search transactions" /></label><Select value={kind} onChange={(event) => setKind(event.target.value)} aria-label="Filter by type"><option value="">All types</option><option value="expense">Expenses</option><option value="income">Income</option><option value="transfer">Transfers</option></Select></div>}>
    {transactions.isPending ? <Loading /> : transactions.error ? <ErrorNotice message={transactions.error.message} /> : transactions.data.items.length === 0 ? <Empty title="No transactions found" body="Add your first transaction or adjust these filters." /> : <div className="transaction-list">{transactions.data.items.map((item) => <article key={item.id}><span className={`transaction-mark ${item.kind}`}>{item.kind === "income" ? "+" : item.kind === "expense" ? "−" : "↗"}</span><div><strong>{item.description}</strong><small>{categoryName(item.category_id)} · {accountName(item.account_id)} · {displayDate(item.effective_date)}</small></div><span className={`transaction-amount ${item.kind}`}>{item.kind === "expense" ? "−" : item.kind === "income" ? "+" : ""}{currency(item.amount)}</span><Button variant="ghost" size="icon" title="Void transaction" aria-label={`Void ${item.description}`} onClick={() => voidTransaction.mutate(item.id)}><Undo2 size={16} /></Button></article>)}</div>}
  </Panel></div>;
}
