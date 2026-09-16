import { createBrowserRouter } from "react-router-dom";

import { AppShell } from "../components/layout/app-shell";
import { LandingRoute } from "../routes/landing";
import { LoginRoute } from "../routes/login";
import { NotFoundRoute } from "../routes/not-found";

export const router = createBrowserRouter([
  { path: "/", element: <LandingRoute /> },
  { path: "/login", element: <LoginRoute /> },
  {
    path: "/app",
    element: <AppShell />,
    children: [
      { index: true, lazy: async () => ({ Component: (await import("../routes/dashboard")).DashboardRoute }) },
      { path: "transactions", lazy: async () => ({ Component: (await import("../routes/transactions")).TransactionsRoute }) },
      { path: "transactions/new", lazy: async () => ({ Component: (await import("../routes/transactions")).TransactionsRoute }) },
      { path: "accounts", lazy: async () => ({ Component: (await import("../routes/accounts")).AccountsRoute }) },
      { path: "categories", lazy: async () => ({ Component: (await import("../routes/categories")).CategoriesRoute }) },
      { path: "budgets", lazy: async () => ({ Component: (await import("../routes/budgets")).BudgetsRoute }) },
      { path: "recurring", lazy: async () => ({ Component: (await import("../routes/recurring")).RecurringRoute }) },
      { path: "reports", lazy: async () => ({ Component: (await import("../routes/reports")).ReportsRoute }) },
      { path: "settings", lazy: async () => ({ Component: (await import("../routes/settings")).SettingsRoute }) },
    ],
  },
  { path: "*", element: <NotFoundRoute /> },
]);
