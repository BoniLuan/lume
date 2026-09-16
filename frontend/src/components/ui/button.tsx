import { cva, type VariantProps } from "class-variance-authority";
import { clsx } from "clsx";
import { forwardRef, type ButtonHTMLAttributes } from "react";

const styles = cva("button", {
  variants: {
    variant: { primary: "button-primary", secondary: "button-secondary", ghost: "button-ghost", danger: "button-danger" },
    size: { sm: "button-sm", md: "button-md", lg: "button-lg", icon: "button-icon" },
  },
  defaultVariants: { variant: "primary", size: "md" },
});

type Props = ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof styles>;

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { className, variant, size, ...props },
  ref,
) {
  return <button ref={ref} className={clsx(styles({ variant, size }), className)} {...props} />;
});
