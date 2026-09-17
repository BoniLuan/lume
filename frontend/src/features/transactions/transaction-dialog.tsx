import { zodResolver } from "@hookform/resolvers/zod";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useEffect, useMemo } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { api } from "../../api/client";
import type { Account, Category, Transaction, TransactionCreate } from "../../api/types";
import { Button } from "../../components/ui/button";
import { Field, Input, MoneyInput, Select } from "../../components/ui/field";
import { ErrorNotice } from "../../components/ui/states";
import { todayInSaoPaulo } from "../../lib/dates";

type EntryMode = "expense" | "income" | "transfer" | "loan_out" | "loan_repayment" | "credit_payment";

const schema = z
  .object({
    amount: z.string().regex(/^\d+(?:[.,]\d{1,4})?$/, "Enter a valid amount"),
    mode: z.enum(["expense", "income", "transfer", "loan_out", "loan_repayment", "credit_payment"]),
    description: z.string().trim().min(1, "Description is required").max(160),
    account_id: z.string().min(1, "Choose an account"),
    destination_account_id: z.string().optional(),
    category_id: z.string().optional(),
    effective_date: z.string().min(1),
    notes: z.string().max(2000).optional(),
  })
  .superRefine((value, context) => {
    if (!["expense", "income"].includes(value.mode) && !value.destination_account_id) {
      context.addIssue({ code: "custom", path: ["destination_account_id"], message: "Choose a destination" });
    }
    if (["expense", "income"].includes(value.mode) && !value.category_id) {
      context.addIssue({ code: "custom", path: ["category_id"], message: "Choose a category" });
    }
    if (value.destination_account_id && value.destination_account_id === value.account_id) {
      context.addIssue({ code: "custom", path: ["destination_account_id"], message: "Choose a different account" });
    }
  });

type Values = z.infer<typeof schema>;

function transactionMode(item?: Transaction | null): EntryMode {
  return item?.kind ?? "expense";
}

function defaults(item?: Transaction | null): Values {
  return {
    amount: item?.amount ?? "",
    mode: transactionMode(item),
    description: item?.description ?? "",
    account_id: item?.account_id ?? "",
    category_id: item?.category_id ?? "",
    destination_account_id: item?.destination_account_id ?? "",
    effective_date: item?.effective_date ?? todayInSaoPaulo(),
    notes: item?.notes ?? "",
  };
}

export function TransactionDialog({
  open,
  onOpenChange,
  transaction,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  transaction?: Transaction | null;
}) {
  const queryClient = useQueryClient();
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: () => api<Account[]>("/api/v1/accounts") });
  const categories = useQuery({ queryKey: ["categories"], queryFn: () => api<Category[]>("/api/v1/categories") });
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: defaults(transaction) });
  const mode = useWatch({ control: form.control, name: "mode" });
  const sourceId = useWatch({ control: form.control, name: "account_id" });
  const destinationId = useWatch({ control: form.control, name: "destination_account_id" });
  const categoryId = useWatch({ control: form.control, name: "category_id" });
  const isTransfer = !["expense", "income"].includes(mode);
  const suitableCategories = useMemo(
    () => categories.data?.filter((category) => category.kind === mode) ?? [],
    [categories.data, mode],
  );
  const sourceAccounts = useMemo(() => {
    const records = accounts.data ?? [];
    if (mode === "loan_repayment") return records.filter((item) => item.account_type === "receivable");
    if (mode === "credit_payment" || mode === "loan_out") {
      return records.filter((item) => item.account_class === "asset" && item.account_type !== "receivable");
    }
    return records;
  }, [accounts.data, mode]);
  const destinationAccounts = useMemo(() => {
    const records = accounts.data ?? [];
    if (mode === "loan_out") return records.filter((item) => item.account_type === "receivable");
    if (mode === "loan_repayment") {
      return records.filter((item) => item.account_class === "asset" && item.account_type !== "receivable");
    }
    if (mode === "credit_payment") return records.filter((item) => item.account_type === "credit_card");
    return records.filter((item) => item.id !== sourceId);
  }, [accounts.data, mode, sourceId]);

  useEffect(() => {
    if (open) form.reset(defaults(transaction));
  }, [form, open, transaction]);

  useEffect(() => {
    if (!open) return;
    const source = sourceAccounts.find((item) => item.id === sourceId) ?? sourceAccounts[0];
    if (source?.id !== sourceId) form.setValue("account_id", source?.id ?? "");
    if (!isTransfer) {
      if (destinationId) form.setValue("destination_account_id", "");
      return;
    }
    const destination = destinationAccounts.find(
      (item) => item.id === destinationId && item.id !== source?.id,
    ) ?? destinationAccounts.find((item) => item.id !== source?.id);
    if (destination?.id !== destinationId) {
      form.setValue("destination_account_id", destination?.id ?? "");
    }
  }, [destinationAccounts, destinationId, form, isTransfer, open, sourceAccounts, sourceId]);

  useEffect(() => {
    if (!open || isTransfer) return;
    const category = suitableCategories.find((item) => item.id === categoryId) ?? suitableCategories[0];
    if (category?.id !== categoryId) form.setValue("category_id", category?.id ?? "");
  }, [categoryId, form, isTransfer, open, suitableCategories]);

  const save = useMutation({
    mutationFn: (values: Values) => {
      const kind = values.mode === "expense" || values.mode === "income" ? values.mode : "transfer";
      const payload: TransactionCreate = {
        kind,
        amount: values.amount.replace(",", "."),
        description: values.description.trim(),
        account_id: values.account_id,
        effective_date: values.effective_date,
        client_request_id: transaction ? transaction.client_request_id : crypto.randomUUID(),
        notes: values.notes?.trim() || null,
        category_id: kind === "transfer" ? null : values.category_id,
        destination_account_id: kind === "transfer" ? values.destination_account_id : null,
      };
      if (transaction) {
        const update = { ...payload };
        delete update.client_request_id;
        return api<Transaction>(`/api/v1/transactions/${transaction.id}`, { method: "PATCH", body: update });
      }
      return api<Transaction>("/api/v1/transactions", { method: "POST", body: payload });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries();
      onOpenChange(false);
    },
  });

  const helper = mode === "loan_out"
    ? "Moves value into a receivable account. It does not count as spending."
    : mode === "loan_repayment"
      ? "Moves repaid principal back to your account. It does not count as income."
      : mode === "credit_payment"
        ? "Settles card debt from an asset account without creating another expense."
        : mode === "transfer"
          ? "Use this when value remains yours in another account."
          : null;
  const missingGuidedAccount = (mode === "loan_out" || mode === "loan_repayment") && !(accounts.data ?? []).some((item) => item.account_type === "receivable")
    ? "Create a Receivable account before recording loans."
    : mode === "credit_payment" && !(accounts.data ?? []).some((item) => item.account_type === "credit_card")
      ? "Create a Credit card account before recording its payment."
      : null;

  return <Dialog.Root open={open} onOpenChange={onOpenChange}><Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog-content">
    <div className="dialog-heading"><div><span className="eyebrow">{transaction ? "Ledger correction" : "Quick entry"}</span><Dialog.Title>{transaction ? "Edit transaction" : "Add transaction"}</Dialog.Title></div><Dialog.Close asChild><Button variant="ghost" size="icon" aria-label="Close"><X size={20} /></Button></Dialog.Close></div>
    <Dialog.Description className="muted">{transaction ? "Changes immediately update balances, budgets, and reports." : "Record money movement in a few focused fields."}</Dialog.Description>
    <form className="form-grid" onSubmit={(event) => void form.handleSubmit((values) => save.mutate(values))(event)}>
      <Field label="Amount" error={form.formState.errors.amount?.message}><div className="amount-input"><span>R$</span><MoneyInput autoFocus placeholder="0.00" {...form.register("amount")} /></div></Field>
      <Field label="Type"><Select {...form.register("mode")}><option value="expense">Expense</option><option value="income">Income</option><option value="transfer">Transfer between accounts</option><option value="loan_out">Lend money</option><option value="loan_repayment">Record repayment</option><option value="credit_payment">Pay credit card</option></Select></Field>
      {helper ? <p className="form-helper">{helper}</p> : null}
      <Field label="Description" error={form.formState.errors.description?.message}><Input placeholder={mode === "expense" ? "e.g. Groceries" : mode === "income" ? "e.g. Salary" : "e.g. Repayment from Ana"} {...form.register("description")} /></Field>
      <Field label={mode === "loan_repayment" ? "Receivable" : "From account"} error={form.formState.errors.account_id?.message}><Select {...form.register("account_id")}><option value="">Choose account</option>{sourceAccounts.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field>
      {isTransfer ? <Field label={mode === "loan_out" ? "Receivable" : mode === "credit_payment" ? "Credit card" : "To account"} error={form.formState.errors.destination_account_id?.message}><Select {...form.register("destination_account_id")}><option value="">Choose destination</option>{destinationAccounts.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field> : <Field label="Category" error={form.formState.errors.category_id?.message}><Select {...form.register("category_id")}><option value="">Choose category</option>{suitableCategories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field>}
      <Field label="Date"><Input type="date" {...form.register("effective_date")} /></Field>
      <details className="form-details"><summary>Add a note</summary><Field label="Note"><Input placeholder="Optional detail" {...form.register("notes")} /></Field></details>
      {missingGuidedAccount ? <ErrorNotice message={missingGuidedAccount} /> : null}{save.error ? <ErrorNotice message={save.error.message} /> : null}
      <Button type="submit" size="lg" disabled={save.isPending || !accounts.data?.length || Boolean(missingGuidedAccount)}>{save.isPending ? "Saving…" : transaction ? "Save changes" : "Save transaction"}</Button>
    </form>
  </Dialog.Content></Dialog.Portal></Dialog.Root>;
}
