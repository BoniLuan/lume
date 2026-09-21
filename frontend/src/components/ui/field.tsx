import { clsx } from "clsx";
import { forwardRef, type InputHTMLAttributes, type SelectHTMLAttributes } from "react";

import { sanitizeMoneyInput } from "../../lib/money-input";

export function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {error ? <span className="field-error">{error}</span> : null}
    </label>
  );
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...props },
  ref,
) {
  return <input ref={ref} className={clsx("input", className)} {...props} />;
});


export const MoneyInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { allowNegative?: boolean }>(function MoneyInput(
  { allowNegative = false, onChange, ...props },
  ref,
) {
  return <Input
    {...props}
    ref={ref}
    type="text"
    inputMode="decimal"
    pattern={allowNegative ? "-?\\d+(?:\\.\\d{1,2})?" : "\\d+(?:\\.\\d{1,2})?"}
    onChange={(event) => {
      event.currentTarget.value = sanitizeMoneyInput(event.currentTarget.value, allowNegative);
      onChange?.(event);
    }}
  />;
});

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select(
  { className, ...props },
  ref,
) {
  return <select ref={ref} className={clsx("input", className)} {...props} />;
});
