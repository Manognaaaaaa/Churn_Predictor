import type { ButtonHTMLAttributes } from "react";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
}

const VARIANT: Record<string, string> = {
  primary: "bg-cyan-strong text-ink-inverse border-transparent enabled:hover:shadow-glow-cyan",
  secondary: "bg-surface-200 text-ink border-line-200 enabled:hover:bg-surface-300",
  ghost: "bg-transparent text-cyan border-transparent",
};

export function Button({ variant = "secondary", className = "", type = "button", ...rest }: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-block rounded-sm border px-3 py-1_5 text-[14px] font-semibold leading-5 disabled:cursor-not-allowed disabled:opacity-50 ${VARIANT[variant]} ${className}`}
      {...rest}
    />
  );
}
