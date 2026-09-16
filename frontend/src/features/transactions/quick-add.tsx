import { zodResolver } from "@hookform/resolvers/zod";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { api } from "../../api/client";
import type { Account, Category, Transaction, TransactionCreate } from "../../api/types";
import { todayInSaoPaulo } from "../../lib/dates";
import { Button } from "../../components/ui/button";
import { Field, Input, Select } from "../../components/ui/field";
import { ErrorNotice } from "../../components/ui/states";

const schema = z
  .object({
    amount: z.string().regex(/^\d+(?:[.,]\d{1,4})?$/, "Enter a valid amount"),
    kind: z.enum(["expense", "income", "transfer"]),
    description: z.string().trim().min(1, "Description is required").max(160),
    account_id: z.string().min(1, "Choose an account"),
    destination_account_id: z.string().optional(),
    category_id: z.string().optional(),
    effective_date: z.string().min(1),
    notes: z.string().max(2000).optional(),
  })
  .superRefine((value, context) => {
    if (value.kind === "transfer" && !value.destination_account_id) {
      context.addIssue({ code: "custom", path: ["destination_account_id"], message: "Choose a destination" });
    }
    if (value.kind !== "transfer" && !value.category_id) {
      context.addIssue({ code: "custom", path: ["category_id"], message: "Choose a category" });
    }
  });

type Values = z.infer<typeof schema>;

export function QuickAdd({ compact = false }: { compact?: boolean }) {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: () => api<Account[]>("/api/v1/accounts") });
  const categories = useQuery({ queryKey: ["categories"], queryFn: () => api<Category[]>("/api/v1/categories") });
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      amount: "",
      kind: "expense",
      description: "",
      account_id: "",
      category_id: "",
      destination_account_id: "",
      effective_date: todayInSaoPaulo(),
      notes: "",
    },
  });
  const kind = useWatch({ control: form.control, name: "kind" });
  const suitableCategories = useMemo(
    () => categories.data?.filter((category) => category.kind === kind) ?? [],
    [categories.data, kind],
  );

  useEffect(() => {
    if (open && !form.getValues("account_id") && accounts.data?.[0]) {
      form.setValue("account_id", accounts.data[0].id);
    }
  }, [accounts.data, form, open]);

  useEffect(() => {
    form.setValue("category_id", suitableCategories[0]?.id ?? "");
  }, [form, suitableCategories]);

  const create = useMutation({
    mutationFn: (values: Values) => {
      const payload: TransactionCreate = {
        kind: values.kind,
        amount: values.amount.replace(",", "."),
        description: values.description.trim(),
        account_id: values.account_id,
        effective_date: values.effective_date,
        client_request_id: crypto.randomUUID(),
        notes: values.notes?.trim() || null,
        category_id: values.kind === "transfer" ? null : values.category_id,
        destination_account_id: values.kind === "transfer" ? values.destination_account_id : null,
      };
      return api<Transaction>("/api/v1/transactions", { method: "POST", body: payload });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries();
      form.reset({
        amount: "",
        kind: "expense",
        description: "",
        account_id: accounts.data?.[0]?.id ?? "",
        category_id: "",
        destination_account_id: "",
        effective_date: todayInSaoPaulo(),
        notes: "",
      });
      setOpen(false);
    },
  });

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button className={compact ? "quick-add-fab" : undefined} size={compact ? "icon" : "md"}>
          <Plus size={18} aria-hidden="true" /> <span className={compact ? "sr-only" : undefined}>Add transaction</span>
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content className="dialog-content">
          <div className="dialog-heading">
            <div><span className="eyebrow">Quick entry</span><Dialog.Title>Add transaction</Dialog.Title></div>
            <Dialog.Close asChild><Button variant="ghost" size="icon" aria-label="Close"><X size={20} /></Button></Dialog.Close>
          </div>
          <Dialog.Description className="muted">Record money movement in a few focused fields.</Dialog.Description>
          <form className="form-grid" onSubmit={(event) => void form.handleSubmit((values) => create.mutate(values))(event)}>
            <Field label="Amount" error={form.formState.errors.amount?.message}>
              <div className="amount-input"><span>R$</span><Input autoFocus inputMode="decimal" placeholder="0.00" {...form.register("amount")} /></div>
            </Field>
            <Field label="Type">
              <Select {...form.register("kind")}>
                <option value="expense">Expense</option><option value="income">Income</option><option value="transfer">Transfer</option>
              </Select>
            </Field>
            <Field label="Description" error={form.formState.errors.description?.message}>
              <Input placeholder={kind === "expense" ? "e.g. Groceries" : "e.g. Salary"} {...form.register("description")} />
            </Field>
            <Field label="Account" error={form.formState.errors.account_id?.message}>
              <Select {...form.register("account_id")}><option value="">Choose account</option>{accounts.data?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select>
            </Field>
            {kind === "transfer" ? (
              <Field label="Destination" error={form.formState.errors.destination_account_id?.message}>
                <Select {...form.register("destination_account_id")}><option value="">Choose destination</option>{accounts.data?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select>
              </Field>
            ) : (
              <Field label="Category" error={form.formState.errors.category_id?.message}>
                <Select {...form.register("category_id")}><option value="">Choose category</option>{suitableCategories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select>
              </Field>
            )}
            <Field label="Date"><Input type="date" {...form.register("effective_date")} /></Field>
            <details className="form-details"><summary>Add a note</summary><Field label="Note"><Input placeholder="Optional detail" {...form.register("notes")} /></Field></details>
            {create.error ? <ErrorNotice message={create.error.message} /> : null}
            {!accounts.isPending && accounts.data?.length === 0 ? <ErrorNotice message="Create an account before recording a transaction." /> : null}
            <Button type="submit" size="lg" disabled={create.isPending || !accounts.data?.length}>{create.isPending ? "Saving…" : "Save transaction"}</Button>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
