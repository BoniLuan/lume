import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { api, setCsrfToken } from "../api/client";
import type { Session } from "../api/types";
import { queryClient } from "../app/query-client";
import { useSession } from "../app/session-provider";
import { Button } from "../components/ui/button";
import { Field, Input } from "../components/ui/field";
import { ErrorNotice } from "../components/ui/states";

const schema = z.object({ email: z.email("Enter a valid email"), password: z.string().min(8, "Password must have at least 8 characters") });
type Values = z.infer<typeof schema>;

export function LoginRoute() {
  const { session, loading } = useSession();
  const navigate = useNavigate();
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: "", password: "" } });
  const login = useMutation({
    mutationFn: (values: Values) => api<Session>("/api/v1/auth/sessions", { method: "POST", body: { ...values, transport: "cookie", device_label: "Lume web" } }),
    onSuccess: async (data) => { setCsrfToken(data.csrf_token); queryClient.setQueryData(["session"], data); await queryClient.invalidateQueries({ queryKey: ["session"] }); void navigate("/app", { replace: true }); },
  });
  if (!loading && session) return <Navigate to="/app" replace />;
  return <main className="login-page"><section className="login-aside"><Link to="/" className="brand brand-light"><img src="/lume-mark.svg" alt="" /><span>Lume</span></Link><div><span className="eyebrow">Welcome back</span><h1>A clearer month starts with one honest look.</h1><p>Your accounts, budget, and daily spending in one focused place.</p></div><blockquote>“What gets measured gets easier to shape.”</blockquote></section><section className="login-form-wrap"><Link to="/" className="back-link"><ArrowLeft size={17} /> Back home</Link><form className="login-form" onSubmit={(event) => void form.handleSubmit((values) => login.mutate(values))(event)}><div><span className="eyebrow">Private access</span><h2>Sign in to Lume</h2><p>Registration is closed. Use your operator-created account.</p></div><Field label="Email" error={form.formState.errors.email?.message}><Input autoComplete="email" inputMode="email" placeholder="you@example.com" {...form.register("email")} /></Field><Field label="Password" error={form.formState.errors.password?.message}><Input type="password" autoComplete="current-password" placeholder="Your password" {...form.register("password")} /></Field>{login.error ? <ErrorNotice message={login.error.message} /> : null}<Button type="submit" size="lg" disabled={login.isPending}>{login.isPending ? "Signing in…" : "Sign in"}</Button></form></section></main>;
}
