import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useState } from "react";

import { api } from "../api/client";
import type { Dashboard } from "../api/types";
import { PageHeader, Panel } from "../components/layout/page";
import { Input } from "../components/ui/field";
import { Empty, ErrorNotice, Loading } from "../components/ui/states";
import { currency } from "../lib/currency";
import { currentMonth, monthLabel } from "../lib/dates";

export function ReportsRoute() {
  const [month, setMonth] = useState(currentMonth());
  const [year, monthNumber] = month.split("-").map(Number);
  const lastDay = new Date(Date.UTC(year ?? 2000, monthNumber ?? 1, 0)).getUTCDate();
  const exportUrl = `/api/v1/reports/transactions.csv?start_date=${month}-01&end_date=${month}-${String(lastDay).padStart(2, "0")}`;
  const report = useQuery({
    queryKey: ["dashboard", month],
    queryFn: () => api<Dashboard>(`/api/v1/dashboard?month=${month}`),
  });

  return (
    <div className="page">
      <PageHeader
        eyebrow="Analysis"
        title="Reports"
        description="Compare the month and see which categories carried the most weight."
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
      {report.isPending ? (
        <Loading />
      ) : report.error ? (
        <ErrorNotice message={report.error.message} />
      ) : (
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
      )}
    </div>
  );
}
