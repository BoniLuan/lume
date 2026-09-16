import { useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, CalendarClock, PiggyBank, Wallet } from "lucide-react";

import { api } from "../api/client";
import type { Account, Category, Dashboard } from "../api/types";
import { PageHeader, Panel } from "../components/layout/page";
import { Empty, ErrorNotice, Loading } from "../components/ui/states";
import { QuickAdd } from "../features/transactions/quick-add";
import { currency, percentage } from "../lib/currency";
import { currentMonth, displayDate, monthLabel } from "../lib/dates";

export function DashboardRoute() {
  const month = currentMonth();
  const dashboard = useQuery({ queryKey: ["dashboard", month], queryFn: () => api<Dashboard>(`/api/v1/dashboard?month=${month}`) });
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: () => api<Account[]>("/api/v1/accounts") });
  const categories = useQuery({ queryKey: ["categories"], queryFn: () => api<Category[]>("/api/v1/categories") });
  if (dashboard.isPending) return <div className="page"><Loading label="Building your overview" /></div>;
  if (dashboard.error) return <div className="page"><ErrorNotice message={dashboard.error.message} /></div>;
  const data = dashboard.data;
  const accountName = (id: string) => accounts.data?.find((item) => item.id === id)?.name ?? "Account";
  const categoryName = (id: string | null) => categories.data?.find((item) => item.id === id)?.name ?? "Other";
  const categoryMax = Math.max(...data.categories.map((item) => Number(item.amount)), 1);
  const trendMax = Math.max(...data.trend.flatMap((item) => [Number(item.income), Number(item.expense)]), 1);
  return <div className="page"><PageHeader eyebrow={monthLabel(month)} title={`Good to see you.`} description="Here is the shape of your money this month." action={<QuickAdd />} />
    <section className="metric-grid">
      <article className="metric-card"><span className="metric-icon positive"><ArrowUpRight /></span><small>Earned</small><strong>{currency(data.income, data.currency)}</strong><p>Income this month</p></article>
      <article className="metric-card"><span className="metric-icon negative"><ArrowDownRight /></span><small>Spent</small><strong>{currency(data.expense, data.currency)}</strong><p>Expenses this month</p></article>
      <article className="metric-card"><span className="metric-icon neutral"><Wallet /></span><small>Net change</small><strong>{currency(data.net, data.currency)}</strong><p>Income less expenses</p></article>
      <article className="metric-card accent"><span className="metric-icon"><PiggyBank /></span><small>Budget remaining</small><strong>{data.budget ? currency(data.budget.remaining, data.currency) : "Not set"}</strong><p>{data.budget ? `${percentage(data.budget.percentage_used)} used` : "Set a monthly intention"}</p></article>
    </section>
    <div className="dashboard-grid">
      <Panel title="Monthly budget" subtitle="Your current spending pace" className="budget-panel">
        {data.budget ? <><div className="budget-summary"><strong>{currency(data.budget.spent, data.currency)}</strong><span>of {currency(data.budget.total_limit, data.currency)}</span><b>{percentage(data.budget.percentage_used)}</b></div><div className="progress large"><i className={Number(data.budget.percentage_used) > 100 ? "over" : ""} style={{ width: `${Math.min(Number(data.budget.percentage_used), 100)}%` }} /></div><p className="muted">{Number(data.budget.remaining) >= 0 ? `${currency(data.budget.remaining, data.currency)} available for the rest of the month.` : `${currency(Math.abs(Number(data.budget.remaining)), data.currency)} over your intention.`}</p></> : <Empty title="No budget for this month" body="Set one to understand your spending pace." />}
      </Panel>
      <Panel title="Where it went" subtitle="Top expense categories">
        {data.categories.length ? <div className="category-bars">{data.categories.slice(0, 6).map((item) => <div key={item.category_id}><div><span>{item.category_name}</span><strong>{currency(item.amount, data.currency)}</strong></div><div className="bar"><i style={{ width: `${(Number(item.amount) / categoryMax) * 100}%` }} /></div></div>)}</div> : <Empty title="No expenses yet" body="Expense categories will appear as you record transactions." />}
      </Panel>
      <Panel title="Six-month rhythm" subtitle="Income and expense side by side" className="trend-panel">
        <div className="trend-chart" aria-label="Monthly income and expense comparison">{data.trend.map((item) => <div className="trend-group" key={item.month}><div className="trend-bars"><i className="income" style={{ height: `${Math.max((Number(item.income) / trendMax) * 100, 2)}%` }} title={`Income ${currency(item.income, data.currency)}`} /><i className="expense" style={{ height: `${Math.max((Number(item.expense) / trendMax) * 100, 2)}%` }} title={`Expense ${currency(item.expense, data.currency)}`} /></div><span>{item.month.slice(5)}</span></div>)}</div><div className="chart-legend"><span><i className="income" />Income</span><span><i className="expense" />Expense</span></div>
      </Panel>
      <Panel title="Largest expenses" subtitle="Recent transactions worth a closer look">
        {data.largest_expenses.length ? <div className="compact-list">{data.largest_expenses.map((item) => <div key={item.id}><span className="list-icon">{categoryName(item.category_id).slice(0, 1)}</span><div><strong>{item.description}</strong><small>{categoryName(item.category_id)} · {accountName(item.account_id)} · {displayDate(item.effective_date)}</small></div><b>−{currency(item.amount, data.currency)}</b></div>)}</div> : <Empty title="Nothing to review" body="Your largest expenses will be listed here." />}
      </Panel>
      {data.recurring_due.length ? <Panel title="Expected now" subtitle="Recurring items waiting for action" className="full-panel"><div className="due-row">{data.recurring_due.slice(0, 4).map((item) => <article key={item.id}><CalendarClock size={18} /><div><strong>{item.description}</strong><small>Due {displayDate(item.next_due_on)}</small></div><b>{currency(item.amount, data.currency)}</b></article>)}</div></Panel> : null}
    </div>
  </div>;
}
