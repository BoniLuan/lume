import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, LogOut, ShieldCheck, Smartphone } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, setCsrfToken } from "../api/client";
import type { SessionItem, User } from "../api/types";
import { useSession } from "../app/session-provider";
import { PageHeader, Panel } from "../components/layout/page";
import { Button } from "../components/ui/button";
import { Field, Input } from "../components/ui/field";
import { ErrorNotice, Loading } from "../components/ui/states";

export function SettingsRoute() {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [name, setName] = useState(session?.user.display_name ?? "");
  const [passwords, setPasswords] = useState({ current: "", next: "", confirm: "" });
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: () => api<SessionItem[]>("/api/v1/auth/sessions") });
  const update = useMutation({ mutationFn: () => api<User>("/api/v1/users/me", { method: "PATCH", body: { display_name: name } }), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["session"] }); } });
  const revoke = useMutation({ mutationFn: (id: string) => api<void>(`/api/v1/auth/sessions/${id}`, { method: "DELETE" }), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions"] }) });
  const passwordError = passwords.next && passwords.next.length < 12 ? "Use at least 12 characters." : passwords.confirm && passwords.next !== passwords.confirm ? "The new passwords do not match." : null;
  const changePassword = useMutation({
    mutationFn: () => api<void>("/api/v1/users/me/password", { method: "PUT", body: { current_password: passwords.current, new_password: passwords.next } }),
    onSuccess: () => {
      setCsrfToken(null);
      queryClient.clear();
      void navigate("/login", { replace: true });
    },
  });
  return <div className="page"><PageHeader eyebrow="Preferences & security" title="Settings" description="Manage the identity and sessions connected to Lume." /><div className="settings-grid"><Panel title="Profile" subtitle="Your display preferences"><form className="settings-form" onSubmit={(event) => { event.preventDefault(); update.mutate(); }}><Field label="Display name"><Input value={name} onChange={(event) => setName(event.target.value)} /></Field><Field label="Email"><Input disabled value={session?.user.email ?? ""} /></Field><div className="readonly-row"><span>Base currency</span><strong>{session?.user.base_currency}</strong></div><div className="readonly-row"><span>Timezone</span><strong>{session?.user.timezone}</strong></div>{update.error ? <ErrorNotice message={update.error.message} /> : null}<Button type="submit" disabled={update.isPending || !name.trim()}>{update.isPending ? "Saving…" : "Save profile"}</Button></form></Panel><Panel title="Active sessions" subtitle="Revoke access you no longer recognize">{sessions.isPending ? <Loading /> : sessions.error ? <ErrorNotice message={sessions.error.message} /> : <div className="session-list">{sessions.data.map((item) => <div key={item.id}><span className="session-icon">{item.current ? <ShieldCheck /> : <Smartphone />}</span><div><strong>{item.device_label ?? item.transport}</strong><small>{item.current ? "This session" : `Last active ${new Date(item.last_seen_at).toLocaleDateString("en")}`}</small></div>{!item.current ? <Button variant="ghost" size="sm" onClick={() => revoke.mutate(item.id)}><LogOut size={15} /> Revoke</Button> : <span className="status-pill">Current</span>}</div>)}</div>}</Panel><Panel title="Change password" subtitle="All devices will be signed out after the change" className="full-panel"><form className="password-form" onSubmit={(event) => { event.preventDefault(); if (!passwordError) changePassword.mutate(); }}><span className="password-icon"><KeyRound /></span><Field label="Current password"><Input type="password" autoComplete="current-password" value={passwords.current} onChange={(event) => setPasswords({ ...passwords, current: event.target.value })} /></Field><Field label="New password"><Input type="password" autoComplete="new-password" value={passwords.next} onChange={(event) => setPasswords({ ...passwords, next: event.target.value })} /></Field><Field label="Confirm new password" error={passwordError ?? undefined}><Input type="password" autoComplete="new-password" value={passwords.confirm} onChange={(event) => setPasswords({ ...passwords, confirm: event.target.value })} /></Field>{changePassword.error ? <ErrorNotice message={changePassword.error.message} /> : null}<Button type="submit" disabled={changePassword.isPending || !passwords.current || !passwords.next || !passwords.confirm || Boolean(passwordError)}>{changePassword.isPending ? "Changing…" : "Change password"}</Button></form></Panel></div></div>;
}
