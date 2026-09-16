import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, Pencil, Plus, X } from "lucide-react";
import { useState } from "react";

import { api } from "../api/client";
import type { Category, CategoryCreate } from "../api/types";
import { PageHeader, Panel } from "../components/layout/page";
import { Button } from "../components/ui/button";
import { Field, Input, Select } from "../components/ui/field";
import { Empty, ErrorNotice, Loading } from "../components/ui/states";

export function CategoriesRoute() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<CategoryCreate>({ name: "", kind: "expense", color: "#d89050", icon: null });
  const [editing, setEditing] = useState<Category | null>(null);
  const [editForm, setEditForm] = useState<{ name: string; color: string | null }>({ name: "", color: "#d89050" });
  const categories = useQuery({ queryKey: ["categories"], queryFn: () => api<Category[]>("/api/v1/categories") });
  const create = useMutation({ mutationFn: () => api<Category>("/api/v1/categories", { method: "POST", body: form }), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["categories"] }); setForm({ ...form, name: "" }); } });
  const update = useMutation({ mutationFn: () => api<Category>(`/api/v1/categories/${editing?.id}`, { method: "PATCH", body: editForm }), onSuccess: async () => { await queryClient.invalidateQueries(); setEditing(null); } });
  const archive = useMutation({ mutationFn: (id: string) => api<Category>(`/api/v1/categories/${id}/archive`, { method: "POST" }), onSuccess: () => queryClient.invalidateQueries() });
  const groups = { expense: categories.data?.filter((item) => item.kind === "expense") ?? [], income: categories.data?.filter((item) => item.kind === "income") ?? [] };
  return <div className="page"><PageHeader eyebrow="Classification" title="Categories" description="Use a small, meaningful set of labels to make spending patterns visible." /><Panel title="Create a category"><form className="inline-form compact" onSubmit={(event) => { event.preventDefault(); create.mutate(); }}><Field label="Name"><Input required maxLength={80} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="e.g. Pets" /></Field><Field label="Applies to"><Select value={form.kind} onChange={(event) => setForm({ ...form, kind: event.target.value as CategoryCreate["kind"] })}><option value="expense">Expenses</option><option value="income">Income</option></Select></Field><Field label="Color"><Input type="color" value={form.color ?? "#d89050"} onChange={(event) => setForm({ ...form, color: event.target.value })} /></Field><Button type="submit" disabled={create.isPending || !form.name.trim()}><Plus size={17} /> Create</Button>{create.error ? <ErrorNotice message={create.error.message} /> : null}</form></Panel>
    {categories.isPending ? <Loading /> : categories.error ? <ErrorNotice message={categories.error.message} /> : categories.data.length === 0 ? <Empty title="No categories" body="Default categories appear when an operator creates the user." /> : <div className="two-column">{(["expense", "income"] as const).map((kind) => <Panel key={kind} title={kind === "expense" ? "Expense categories" : "Income categories"} subtitle={`${groups[kind].length} active`}><div className="category-list">{groups[kind].map((item) => <div key={item.id}><i style={{ background: item.color ?? "#d89050" }} /><span>{item.name}</span><div className="row-actions"><Button variant="ghost" size="icon" onClick={() => { setEditForm({ name: item.name, color: item.color ?? "#d89050" }); setEditing(item); }} aria-label={`Edit ${item.name}`}><Pencil size={16} /></Button><Button variant="ghost" size="icon" onClick={() => archive.mutate(item.id)} aria-label={`Archive ${item.name}`}><Archive size={16} /></Button></div></div>)}</div></Panel>)}</div>}
    <Dialog.Root open={editing !== null} onOpenChange={(open) => { if (!open) setEditing(null); }}><Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog-content"><div className="dialog-heading"><div><span className="eyebrow">Classification</span><Dialog.Title>Edit category</Dialog.Title></div><Dialog.Close asChild><Button variant="ghost" size="icon" aria-label="Close"><X size={20} /></Button></Dialog.Close></div><Dialog.Description className="muted">The new label and color also appear on historical transactions.</Dialog.Description><form className="form-grid" onSubmit={(event) => { event.preventDefault(); update.mutate(); }}><Field label="Name"><Input required maxLength={80} value={editForm.name} onChange={(event) => setEditForm({ ...editForm, name: event.target.value })} /></Field><Field label="Color"><Input type="color" value={editForm.color ?? "#d89050"} onChange={(event) => setEditForm({ ...editForm, color: event.target.value })} /></Field>{update.error ? <ErrorNotice message={update.error.message} /> : null}<Button type="submit" size="lg" disabled={update.isPending || !editForm.name.trim()}>{update.isPending ? "Saving…" : "Save category"}</Button></form></Dialog.Content></Dialog.Portal></Dialog.Root>
  </div>;
}
