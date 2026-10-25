import type { Band, Customer } from "../api";

export function customerName(c: Pick<Customer, "surname" | "gender" | "customer_id">): string {
  if (!c.surname) return `Customer ${c.customer_id}`;
  const g = (c.gender ?? "").toLowerCase();
  return `${g === "male" ? "Mr " : g === "female" ? "Ms " : ""}${c.surname}`;
}
export const initials = (c: Pick<Customer, "surname">) => (c.surname ?? "?").slice(0, 2).toUpperCase();
export const pronoun = (c: Pick<Customer, "gender">) => ((c.gender ?? "").toLowerCase() === "male" ? "He" : (c.gender ?? "").toLowerCase() === "female" ? "She" : "They");
export const possessive = (c: Pick<Customer, "gender">) => ((c.gender ?? "").toLowerCase() === "male" ? "his" : (c.gender ?? "").toLowerCase() === "female" ? "her" : "their");

export const BAND_WORD: Record<Band, string> = { red: "High risk", amber: "Medium risk", green: "Low risk" };
/** Risk is shown by blue lightness plus the word, never colour alone. */
export const BAND_VAR: Record<Band, string> = { red: "var(--blue-100)", amber: "var(--blue-300)", green: "var(--blue-400)" };

export function posterFor(country: string | null | undefined): { bg: string; glow: string } {
  switch (country) {
    case "France": return { bg: "var(--poster-fr)", glow: "var(--glow-fr)" };
    case "Spain": return { bg: "var(--poster-es)", glow: "var(--glow-es)" };
    default: return { bg: "var(--poster-de)", glow: "var(--glow-de)" };
  }
}

const OFFERS: Record<string, { label: string; desc: (c: Pick<Customer, "gender">) => string }> = {
  value_discount: { label: "Better savings rate", desc: (c) => `A higher interest rate on ${possessive(c)} balance for 6 months.` },
  fee_waiver: { label: "Waive account fees", desc: () => "No account fees for a year." },
  service_call: { label: "Call from relationship manager", desc: (c) => `A personal review of ${possessive(c)} accounts and products.` },
  retention_bonus: { label: "Loyalty bonus", desc: () => "A cash bonus for staying with the bank." },
  loyalty_email: { label: "Personal email from the bank", desc: () => "A short personal note about what the bank can do for them." },
};
export function offerLabel(code: string): string {
  return OFFERS[code]?.label ?? code.replace(/_/g, " ").replace(/^./, (s) => s.toUpperCase());
}
export function offerDesc(code: string, c: Pick<Customer, "gender">): string {
  return OFFERS[code]?.desc(c) ?? "";
}
const OFFER_COLOR: Record<string, string> = {
  value_discount: "var(--offer-1)", fee_waiver: "var(--offer-3)", service_call: "var(--offer-5)",
  retention_bonus: "var(--offer-2)", loyalty_email: "var(--offer-4)",
};
export const offerColor = (code: string) => OFFER_COLOR[code] ?? "var(--offer-4)";

const base = (raw: string) => raw.replace(/\s*\([+-]?[\d.]+ sd\)/, "").replace(/\s*#\d+\s*$/, "").trim();
function label(raw: string): string {
  const b = base(raw);
  if (b.startsWith("Geography_")) return `Customers in ${b.slice(10).replace(/_/g, " ")}`;
  if (b === "zero_balance") return /\(-[\d.]+ sd\)/.test(raw) ? "Customers with a balance" : "Customers with no balance";
  return b.replace(/_/g, " ");
}
/** Readable group names: Geography_Germany (+1.7 sd) #7 becomes "Customers in Germany (group B)". Letters follow list order. */
export function segmentLabeler(names: string[]): (raw: string | null | undefined) => string {
  const groups = new Map<string, string[]>();
  for (const n of names) groups.set(label(n), [...(groups.get(label(n)) ?? []), n]);
  return (raw) => {
    if (!raw) return "–";
    const l = label(raw);
    const g = groups.get(l) ?? [];
    return g.length > 1 && g.includes(raw) ? `${l} (group ${String.fromCharCode(65 + g.indexOf(raw))})` : l;
  };
}

/** Plain name for a model feature at a value, e.g. NumOfProducts=4 becomes "Holds 4 bank products". */
export function featureLabel(feature: string, value: number | null): string {
  const n = value == null ? null : Math.round(value);
  switch (feature) {
    case "NumOfProducts": return n == null ? "Number of bank products" : `Holds ${n} bank product${n === 1 ? "" : "s"}`;
    case "IsActiveMember": return n === 0 ? "Not an active member" : "Active member";
    case "Age": return n == null ? "Age" : `Age ${n}`;
    case "Tenure": return n == null ? "Years with the bank" : n === 1 ? "1 year with the bank" : `${n} years with the bank`;
    case "CreditScore": return n == null ? "Credit score" : `Credit score ${n}`;
    case "Balance": return n === 0 ? "Empty account" : "Account balance";
    case "zero_balance": return n === 1 ? "Empty account" : "Money held with the bank";
    case "HasCrCard": return n === 1 ? "Has a credit card" : "No credit card";
    case "customer_value": return "Yearly value";
    case "balance_value_ratio": return "Balance compared with yearly value";
    case "Gender_Female": return n === 1 ? "Female customer" : "Not a female customer";
    case "Gender_Male": return n === 1 ? "Male customer" : "Not a male customer";
    default:
      if (feature.startsWith("Geography_")) {
        const c = feature.slice(10);
        return n === 1 ? `Based in ${c}` : `Not based in ${c}`;
      }
      return feature.replace(/_/g, " ").replace(/^./, (s) => s.toUpperCase());
  }
}
