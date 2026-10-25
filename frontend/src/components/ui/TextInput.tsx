import type { InputHTMLAttributes } from "react";

export interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
  variant?: "field" | "prompt";
}

export function TextInput({ variant = "field", className = "", ...rest }: TextInputProps) {
  const look =
    variant === "prompt"
      ? "rounded-pill border-field bg-field px-4 py-2 text-ink-inverse placeholder:text-ink-faint"
      : "rounded-sm border-line-200 bg-surface-200 px-3 py-1_5 text-ink placeholder:text-ink-faint";
  return <input className={`w-full border text-[14px] leading-5 ${look} ${className}`} {...rest} />;
}
