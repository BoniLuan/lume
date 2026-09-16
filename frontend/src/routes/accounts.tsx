import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, CreditCard, Landmark, Plus, WalletCards } from "lucide-react";
import { useState } from "react";

import { api } from "../api/client";
import type { Account, AccountCreate } from "../api/types";
import { PageHeader, Panel } from "../components/layout/page";
import { Button } from "../components/ui/button";
import { Field, Input, Select } from "../components/ui/field";
import { Empty, ErrorNotice, Loading } from "../components/ui/states";
import { currency } from "../lib/currency";
import { todayInSaoPaulo } from "../lib/dates";

export function AccountsRoute() {
  const queryClient = useQueryClient(); const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<AccountCreate>({ name: "", account_type: "checking", account_class: "asset", opening_balance: "0.00", opened_on: todayInSaoPaulo() });
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: () => api<Account[]>("/api/v1/accounts") });
  const create = useMutation({ mutationFn: () => api<Account>("/api/v1/accounts", { method: "POST", body: form }), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["accounts"] }); setShowForm(false); setForm({ name: "", account_type: "checking", account_class: "asset", opening_balance: "0.00", opened_on: todayInSaoPaulo() }); } });
  const archive = useMutation({ mutationFn: (id: string) => api<Account>(`/api/v1/accounts/${id}/archive`, { method: "POST" }), onSuccess: () => queryClient.invalidateQueries() });
  const setType = (accountType: AccountCreate["account_type"]) => setForm((value) => ({ ...value, account_type: accountType, account_class: accountType === "credit_card" ? "liability" : value.account_class }));
  return <div className="page"><PageHeader eyebrow="Money containers" title="Accounts" description="Track where money lives and what each balance means." action={<Button onClick={() => setShowForm((value) => !value)}><Plus size={18} /> Add account</Button>} />
    {showForm ? <Panel title="New account" subtitle="Opening balance anchors your future totals."><form className="inline-form" onSubmit={(event) => { event.preventDefault(); create.mutate(); }}><Field label="Name"><Input required maxLength={100} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="e.g. Nubank" /></Field><Field label="Type"><Select value={form.account_type} onChange={(event) => setType(event.target.value as AccountCreate["account_type"])}><option value="checking">Checking</option><option value="cash">Cash</option><option value="savings">Savings</option><option value="credit_card">Credit card</option><option value="other">Other</option></Select></Field><Field label="Balance class"><Select disabled={form.account_type === "credit_card"} value={form.account_class} onChange={(event) => setForm({ ...form, account_class: event.target.value as AccountCreate["account_class"] })}><option value="asset">Asset</option><option value="liability">Liability</option></Select></Field><Field label="Opening balance"><Input required inputMode="decimal" value={String(form.opening_balance)} onChange={(event) => setForm({ ...form, opening_balance: event.target.value })} /></Field><Field label="Opened on"><Input type="date" value={form.opened_on} onChange={(event) => setForm({ ...form, opened_on: event.target.value })} /></Field><Button type="submit" disabled={create.isPending || !form.name.trim()}>{create.isPending ? "Creating…" : "Create account"}</Button>{create.error ? <ErrorNotice message={create.error.message} /> : null}</form></Panel> : null}
    {accounts.isPending ? <Loading /> : accounts.error ? <ErrorNotice message={accounts.error.message} /> : accounts.data.length === 0 ? <Empty title="No accounts yet" body="Create the account you use most to start recording transactions." /> : <section className="account-grid">{accounts.data.map((item) => { const Icon = item.account_type === "credit_card" ? CreditCard : item.account_type === "cash" ? WalletCards : Landmark; const owed = item.account_class === "liability"; return <article className="account-card" key={item.id}><div className="account-card-head"><span><Icon /></span><Button variant="ghost" size="icon" title="Archive account" onClick={() => archive.mutate(item.id)}><Archive size={17} /></Button></div><small>{item.account_type.replace("_", " ")}</small><h2>{item.name}</h2><div><span>{owed ? "Amount owed" : "Current balance"}</span><strong>{currency(owed ? Math.abs(Number(item.current_balance)) : item.current_balance, item.currency)}</strong></div><p>Opened with {currency(item.opening_balance, item.currency)}</p></article>; })}</section>}
  </div>;
}
