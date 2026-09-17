import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useState } from "react";

import { api } from "../api/client";
import type { Account, AccountLedger, Dashboard } from "../api/types";
import { PageHeader, Panel } from "../components/layout/page";
import { Button } from "../components/ui/button";
import { Input, Select } from "../components/ui/field";
import { Empty, ErrorNotice, Loading } from "../components/ui/states";
import { currency } from "../lib/currency";
import { currentMonth, displayDate, monthLabel } from "../lib/dates";

type ReportView = "overview" | "accounts";

function monthRange(month: string): { start: string; end: string } {
  const [year, monthNumber] = month.split("-").map(Number);
  const lastDay = new Date(Date.UTC(year ?? 2000, monthNumber ?? 1, 0)).getUTCDate();
  return { start: `${month}-01`, end: `${month}-${String(lastDay).padStart(2, "0")}` };
}

function signedCurrency(value: string, code: string): string {
  return `${Number(value) > 0 ? "+" : ""}${currency(value, code)}`;
}

export function ReportsRoute() {
  const [view, setView] = useState<ReportView>("overview");
  const [month, setMonth] = useState(currentMonth());
  const [accountId, setAccountId] = useState("");
  const range = monthRange(month);
  const exportUrl = `/api/v1/reports/transactions.csv?start_date=${range.start}&end_date=${range.end}`;
  const accounts = useQuery({
    queryKey: ["accounts", "all"],
    queryFn: () => api<Account[]>("/api/v1/accounts?include_archived=true"),
  });
  const selectedAccountId = accountId || accounts.data?.[0]?.id || "";
  const report = useQuery({
    queryKey: ["dashboard", month],
    queryFn: () => api<Dashboard>(`/api/v1/dashboard?month=${month}`),
    enabled: view === "overview",
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
      <div className="report-tabs" role="tablist" aria-label="Report type">
        <Button variant={view === "overview" ? "primary" : "secondary"} onClick={() => setView("overview")}>Monthly overview</Button>
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
      ) : accounts.isPending ? <Loading /> : accounts.error ? <ErrorNotice message={accounts.error.message} /> : !accounts.data.length ? (
        <Empty title="No accounts" body="Create an account before using balance reconciliation." />
      ) : (
        <div className="account-report">
          <Panel title="Choose an account" subtitle={`Activity during ${monthLabel(month)}`}>
            <Select value={selectedAccountId} onChange={(event) => setAccountId(event.target.value)} aria-label="Account">
              {accounts.data.map((account) => <option key={account.id} value={account.id}>{account.name}{account.archived_at ? " (Archived)" : ""}</option>)}
            </Select>
          </Panel>
          {ledger.isPending ? <Loading /> : ledger.error ? <ErrorNotice message={ledger.error.message} /> : ledger.data ? (
            <>
              <Panel title={ledger.data.account_name} subtitle={`${displayDate(ledger.data.start_date)}–${displayDate(ledger.data.end_date)}`}>
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
