import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import type { Account, AccountLedger, AccountReconciliation, Dashboard, SpendingInsights } from "../api/types";
import { PageHeader, Panel } from "../components/layout/page";
import { Button } from "../components/ui/button";
import { Field, Input, MoneyInput, Select } from "../components/ui/field";
import { Empty, ErrorNotice, Loading } from "../components/ui/states";
import { currency } from "../lib/currency";
import { currentMonth, displayDate, monthLabel, todayInSaoPaulo } from "../lib/dates";

type ReportView = "overview" | "spending" | "accounts";
type Comparison = { account_id: string; as_of_date: string; actual_balance: string };

function monthRange(month: string): { start: string; end: string } {
  const [year, monthNumber] = month.split("-").map(Number);
  const lastDay = new Date(Date.UTC(year ?? 2000, monthNumber ?? 1, 0)).getUTCDate();
  return { start: `${month}-01`, end: `${month}-${String(lastDay).padStart(2, "0")}` };
}

function signedCurrency(value: string, code: string): string {
  return `${Number(value) > 0 ? "+" : ""}${currency(value, code)}`;
}

export function ReportsRoute() {
  const [searchParams] = useSearchParams();
  const [view, setView] = useState<ReportView>(searchParams.get("view") === "accounts" ? "accounts" : "overview");
  const [month, setMonth] = useState(currentMonth());
  const [accountId, setAccountId] = useState(searchParams.get("account_id") ?? "");
  const [asOfDate, setAsOfDate] = useState(todayInSaoPaulo());
  const [actualBalance, setActualBalance] = useState("");
  const [cardBalanceKind, setCardBalanceKind] = useState<"owed" | "credit">("owed");
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const range = monthRange(month);
  const exportUrl = `/api/v1/reports/transactions.csv?start_date=${range.start}&end_date=${range.end}`;
  const accounts = useQuery({
    queryKey: ["accounts", "all"],
    queryFn: () => api<Account[]>("/api/v1/accounts?include_archived=true"),
  });
  const selectedAccountId = accountId || accounts.data?.[0]?.id || "";
  const selectedAccount = accounts.data?.find((item) => item.id === selectedAccountId);
  const liability = selectedAccount?.account_class === "liability";
  const canCompare = /^-?\d+(?:\.\d{1,2})?$/.test(actualBalance) && (!liability || !actualBalance.startsWith("-"));
  const report = useQuery({
    queryKey: ["dashboard", month],
    queryFn: () => api<Dashboard>(`/api/v1/dashboard?month=${month}`),
    enabled: view === "overview",
  });
  const reconciliation = useQuery({
    queryKey: ["account-reconciliation", comparison],
    queryFn: () => {
      if (!comparison) throw new Error("Choose an account and actual balance");
      return api<AccountReconciliation>("/api/v1/reports/account-reconciliation", { method: "POST", body: comparison });
    },
    enabled: view === "accounts" && comparison !== null,
  });
  const ledger = useQuery({
    queryKey: ["account-ledger", selectedAccountId, range.start, range.end],
    queryFn: () => {
      const params = new URLSearchParams({
        account_id: selectedAccountId,
        start_date: range.start,
        end_date: range.end,
      });
      return api<AccountLedger>(`/api/v1/reports/account-ledger?${params}`);
    },
    enabled: view === "accounts" && Boolean(selectedAccountId),
  });

  return (
    <div className="page">
      <PageHeader
        eyebrow="Analysis"
        title="Reports"
        description="Review monthly performance or explain every change behind an account balance."
        action={
          <div className="report-actions">
            <Input
              className="month-picker"
              type="month"
              value={month}
              onChange={(event) => setMonth(event.target.value)}
            />
            <a className="button button-secondary button-md" href={exportUrl} download>
              <Download size={17} /> Export CSV
            </a>
          </div>
        }
      />
      <div className="report-tabs" role="group" aria-label="Report type">
        <Button variant={view === "overview" ? "primary" : "secondary"} onClick={() => setView("overview")}>Monthly overview</Button>
        <Button variant={view === "spending" ? "primary" : "secondary"} onClick={() => setView("spending")}>Spending insights</Button>
        <Button variant={view === "accounts" ? "primary" : "secondary"} onClick={() => setView("accounts")}>Account balances</Button>
      </div>
      {view === "overview" ? (
        report.isPending ? <Loading /> : report.error ? <ErrorNotice message={report.error.message} /> : (
          <div className="report-grid">
            <Panel title={monthLabel(month)} subtitle="Monthly result">
              <dl className="report-totals">
                <div><dt>Income</dt><dd className="positive-text">{currency(report.data.income)}</dd></div>
                <div><dt>Expenses</dt><dd>{currency(report.data.expense)}</dd></div>
                <div><dt>Net change</dt><dd>{currency(report.data.net)}</dd></div>
              </dl>
            </Panel>
            <Panel title="Category spending" subtitle="Ranked by actual expense">
              {report.data.categories.length ? (
                <div className="report-table" role="table">
                  <div role="row" className="table-head"><span>Category</span><span>Amount</span><span>Share</span></div>
                  {report.data.categories.map((item) => (
                    <div role="row" key={item.category_id}>
                      <strong>{item.category_name}</strong>
                      <span>{currency(item.amount)}</span>
                      <span>{Number(report.data.expense) ? `${((Number(item.amount) / Number(report.data.expense)) * 100).toFixed(1)}%` : "0%"}</span>
                    </div>
                  ))}
                </div>
              ) : <Empty title="No expense data" body="Record expenses to build this report." />}
            </Panel>
            <Panel title="Monthly comparison" subtitle="A readable six-month history" className="full-panel">
              <div className="report-table" role="table">
                <div role="row" className="table-head"><span>Month</span><span>Income</span><span>Expenses</span></div>
                {report.data.trend.map((item) => (
                  <div role="row" key={item.month}>
                    <strong>{monthLabel(item.month)}</strong>
                    <span className="positive-text">{currency(item.income)}</span>
                    <span>{currency(item.expense)}</span>
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        )
      ) : view === "spending" ? <SpendingInsightsPanel month={month} /> : accounts.isPending ? <Loading /> : accounts.error ? <ErrorNotice message={accounts.error.message} /> : !accounts.data.length ? (
        <Empty title="No accounts" body="Create an account before using balance reconciliation." />
      ) : (
        <div className="account-report">
          <Panel title="Choose an account" subtitle={`Activity during ${monthLabel(month)}`}>
            <Select value={selectedAccountId} onChange={(event) => { setAccountId(event.target.value); setComparison(null); }} aria-label="Account">
              {accounts.data.map((account) => <option key={account.id} value={account.id}>{account.name}{account.archived_at ? " (Archived)" : ""}</option>)}
            </Select>
          </Panel>
          <Panel title="Compare with your real balance" subtitle="Read-only check for a date you choose">
            <p className="panel-note">For credit cards, compare the total outstanding balance on that date, including purchases outside the latest closed invoice. This check never creates or changes transactions.</p>
            <form className="reconcile-form" onSubmit={(event) => {
              event.preventDefault();
              if (!selectedAccountId || !canCompare) return;
              const actual = liability && cardBalanceKind === "owed" && Number(actualBalance) !== 0 ? `-${actualBalance}` : actualBalance;
              setComparison({ account_id: selectedAccountId, as_of_date: asOfDate, actual_balance: actual });
            }}>
              <Field label="Balance date"><Input type="date" required min={selectedAccount?.opened_on} max={todayInSaoPaulo()} value={asOfDate} onChange={(event) => { setAsOfDate(event.target.value); setComparison(null); }} /></Field>
              {liability ? <Field label="Card balance type"><Select value={cardBalanceKind} onChange={(event) => { setCardBalanceKind(event.target.value as "owed" | "credit"); setComparison(null); }}><option value="owed">Amount owed</option><option value="credit">Card credit / overpayment</option></Select></Field> : null}
              <Field label={liability ? "Actual amount" : "Actual account balance"}><MoneyInput required allowNegative={!liability} value={actualBalance} onChange={(event) => { setActualBalance(event.target.value); setComparison(null); }} placeholder="0.00" /></Field>
              <Button type="submit" disabled={!canCompare || !selectedAccountId}>Compare balances</Button>
            </form>
            {reconciliation.isPending && comparison ? <Loading /> : reconciliation.error && comparison ? <ErrorNotice message={reconciliation.error.message} /> : reconciliation.data && comparison ? <div className="reconcile-result">
              <div><span>Lume on {displayDate(reconciliation.data.as_of_date)}</span><strong>{signedCurrency(reconciliation.data.calculated_balance, reconciliation.data.currency)}</strong></div>
              <div><span>Actual balance</span><strong>{signedCurrency(reconciliation.data.actual_balance, reconciliation.data.currency)}</strong></div>
              <div className="equation-total"><span>Difference (actual − Lume)</span><strong className={Number(reconciliation.data.difference) === 0 ? "positive-text" : "negative-text"}>{signedCurrency(reconciliation.data.difference, reconciliation.data.currency)}</strong></div>
              <p className="panel-note">{Number(reconciliation.data.difference) === 0 ? "Balances match for this date." : "Review missing or repeated purchases, refunds, payments, and the opening balance. Do not add an invoice payment unless it happened."}</p>
              <details className="reconcile-details"><summary>How Lume calculated this balance</summary><div className="balance-equation">
                <div><span>Opening balance</span><strong>{signedCurrency(reconciliation.data.opening_balance, reconciliation.data.currency)}</strong></div>
                <div><span>Income</span><strong>+{currency(reconciliation.data.income, reconciliation.data.currency)}</strong></div>
                <div><span>Expenses</span><strong>−{currency(reconciliation.data.expense, reconciliation.data.currency)}</strong></div>
                <div><span>Transfers in</span><strong>+{currency(reconciliation.data.transfers_in, reconciliation.data.currency)}</strong></div>
                <div><span>Transfers out</span><strong>−{currency(reconciliation.data.transfers_out, reconciliation.data.currency)}</strong></div>
              </div><small>{reconciliation.data.movement_count} movements through {displayDate(reconciliation.data.as_of_date)}</small></details>
              {month !== reconciliation.data.as_of_date.slice(0, 7) ? <Button variant="secondary" size="sm" onClick={() => setMonth(reconciliation.data.as_of_date.slice(0, 7))}>Show this month in the timeline</Button> : null}
            </div> : null}
          </Panel>
          {ledger.isPending ? <Loading /> : ledger.error ? <ErrorNotice message={ledger.error.message} /> : ledger.data ? (
            <>
              <Panel title={ledger.data.account_name} subtitle={`${displayDate(ledger.data.start_date)}–${displayDate(ledger.data.end_date)}`} className="full-panel">
                <div className="balance-equation">
                  <div><span>Original opening balance</span><strong>{currency(ledger.data.account_opening_balance, ledger.data.currency)}</strong></div>
                  <div><span>Activity before this period</span><strong>{signedCurrency(ledger.data.activity_before_period, ledger.data.currency)}</strong></div>
                  <div className="equation-total"><span>Balance at period start</span><strong>{currency(ledger.data.starting_balance, ledger.data.currency)}</strong></div>
                  <div><span>Income</span><strong className="positive-text">+{currency(ledger.data.income, ledger.data.currency)}</strong></div>
                  <div><span>Expenses</span><strong>−{currency(ledger.data.expense, ledger.data.currency)}</strong></div>
                  <div><span>Transfers in</span><strong className="positive-text">+{currency(ledger.data.transfers_in, ledger.data.currency)}</strong></div>
                  <div><span>Transfers out</span><strong>−{currency(ledger.data.transfers_out, ledger.data.currency)}</strong></div>
                  <div className="equation-total"><span>Balance at period end</span><strong>{currency(ledger.data.closing_balance, ledger.data.currency)}</strong></div>
                </div>
                {ledger.data.account_class === "liability" ? <p className="panel-note">Liability balances use ledger signs: a negative balance represents money you owe.</p> : null}
              </Panel>
              <Panel title="Balance timeline" subtitle={`${ledger.data.entries.length} movements, oldest first`} className="full-panel">
                {ledger.data.entries.length ? (
                  <div className="ledger-scroll"><div className="ledger-table" role="table">
                    <div role="row" className="table-head"><span>Date</span><span>Details</span><span>Change</span><span>Balance</span></div>
                    {ledger.data.entries.map((entry) => (
                      <div role="row" key={entry.transaction_id}>
                        <span>{displayDate(entry.effective_date)}</span>
                        <div><strong>{entry.description}</strong><small>{entry.category_name ?? entry.counterparty_account_name ?? entry.kind}</small></div>
                        <span className={entry.direction === "in" ? "positive-text" : "negative-text"}>{signedCurrency(entry.balance_change, ledger.data.currency)}</span>
                        <strong>{currency(entry.running_balance, ledger.data.currency)}</strong>
                      </div>
                    ))}
                  </div></div>
                ) : <Empty title="No movements in this period" body="The starting and ending balances are equal." />}
              </Panel>
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}


function SpendingInsightsPanel({ month }: { month: string }) {
  const insights = useQuery({
    queryKey: ["spending-insights", month],
    queryFn: () => api<SpendingInsights>(`/api/v1/reports/spending-insights?month=${month}`),
  });
  if (insights.isPending) return <Loading />;
  if (insights.error) return <ErrorNotice message={insights.error.message} />;
  const data = insights.data;
  return <div className="report-grid">
    <Panel title="Spending movement" subtitle={`${monthLabel(month)} compared with the previous calendar month`}>
      <dl className="report-totals">
        <div><dt>This month</dt><dd>{currency(data.expense)}</dd></div>
        <div><dt>Previous month</dt><dd>{currency(data.previous_expense)}</dd></div>
        <div><dt>Change</dt><dd className={Number(data.change) > 0 ? "negative-text" : "positive-text"}>{signedCurrency(data.change, data.currency)}</dd></div>
      </dl>
      <p className="panel-note">The current month may still be in progress. Transfers and card payments are excluded from spending.</p>
    </Panel>
    <Panel title="Where expenses were recorded" subtitle="Separate card purchases from direct bank spending">
      {data.accounts.length ? <div className="report-table" role="table">
        <div role="row" className="table-head"><span>Account</span><span>Transactions</span><span>Spent</span></div>
        {data.accounts.map((row) => <div role="row" key={row.account_id}><strong>{row.account_name}</strong><span>{row.count}</span><span>{currency(row.amount, data.currency)}</span></div>)}
      </div> : <Empty title="No spending this month" body="Record a purchase to see which accounts carry your expenses." />}
    </Panel>
    <Panel title="Category changes" subtitle="Current and previous month, including categories that stopped" className="full-panel">
      {data.categories.length ? <div className="report-table spending-category-table" role="table">
        <div role="row" className="table-head"><span>Category</span><span>This month</span><span>Previous</span><span>Change</span></div>
        {data.categories.map((row) => <div role="row" key={row.category_id}><strong>{row.category_name}</strong><span>{currency(row.amount, data.currency)}</span><span>{currency(row.previous_amount, data.currency)}</span><span className={Number(row.change) > 0 ? "negative-text" : "positive-text"}>{signedCurrency(row.change, data.currency)}</span></div>)}
      </div> : <Empty title="No category activity" body="Record expenses to compare categories." />}
    </Panel>
  </div>;
}
