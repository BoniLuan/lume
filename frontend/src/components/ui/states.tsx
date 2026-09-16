import { LoaderCircle } from "lucide-react";

export function Loading({ label = "Loading" }: { label?: string }) {
  return <div className="loading"><LoaderCircle aria-hidden="true" className="spin" size={20} />{label}</div>;
}

export function Empty({ title, body }: { title: string; body: string }) {
  return <div className="empty"><strong>{title}</strong><p>{body}</p></div>;
}

export function ErrorNotice({ message }: { message: string }) {
  return <div className="error-notice" role="alert">{message}</div>;
}
