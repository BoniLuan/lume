import { BarChart3, CalendarClock, CreditCard, LayoutDashboard, LogOut, Settings, Tags, WalletCards } from "lucide-react";
import { NavLink, Navigate, Outlet, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";

import { api, setCsrfToken } from "../../api/client";
import { queryClient } from "../../app/query-client";
import { useSession } from "../../app/session-provider";
import { QuickAdd } from "../../features/transactions/quick-add";
import { Button } from "../ui/button";
import { Loading } from "../ui/states";

const navigation = [
  ["/app", "Overview", LayoutDashboard],
  ["/app/transactions", "Transactions", CreditCard],
  ["/app/accounts", "Accounts", WalletCards],
  ["/app/budgets", "Budgets", BarChart3],
  ["/app/recurring", "Recurring", CalendarClock],
  ["/app/categories", "Categories", Tags],
  ["/app/reports", "Reports", BarChart3],
  ["/app/settings", "Settings", Settings],
] as const;

export function AppShell() {
  const { session, loading } = useSession();
  const navigate = useNavigate();
  const logout = useMutation({
    mutationFn: () => api<void>("/api/v1/auth/session", { method: "DELETE" }),
    onSuccess: () => {
      setCsrfToken(null);
      queryClient.clear();
      void navigate("/login", { replace: true });
    },
  });

  if (loading) return <main className="center-page"><Loading label="Opening Lume" /></main>;
  if (!session) return <Navigate to="/login" replace />;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink to="/app" className="brand"><img src="/lume-mark.svg" alt="" /><span>Lume</span></NavLink>
        <nav aria-label="Main navigation">
          {navigation.map(([to, label, Icon]) => <NavLink key={to} to={to} end={to === "/app"}><Icon size={19} /><span>{label}</span></NavLink>)}
        </nav>
        <div className="sidebar-footer"><span className="avatar">{session.user.display_name.slice(0, 1).toUpperCase()}</span><div><strong>{session.user.display_name}</strong><small>{session.user.email}</small></div><Button variant="ghost" size="icon" aria-label="Sign out" onClick={() => logout.mutate()}><LogOut size={18} /></Button></div>
      </aside>
      <main className="app-main">
        <header className="mobile-header"><NavLink to="/app" className="brand"><img src="/lume-mark.svg" alt="" /><span>Lume</span></NavLink><QuickAdd /></header>
        <Outlet />
      </main>
      <nav className="bottom-nav" aria-label="Mobile navigation">
        {navigation.slice(0, 4).map(([to, label, Icon]) => <NavLink key={to} to={to} end={to === "/app"}><Icon size={20} /><span>{label}</span></NavLink>)}
        <NavLink to="/app/settings"><Settings size={20} /><span>More</span></NavLink>
      </nav>
      <QuickAdd compact />
    </div>
  );
}
