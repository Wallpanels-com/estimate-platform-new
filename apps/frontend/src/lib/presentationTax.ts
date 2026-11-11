export type PresentationTax = {
  enabled: boolean;
  mode: "percent" | "amount";
  rate: string;
  amount: string;
};
export type TaxSnapshot = {
  id: string;
  revision: string;
  options: PresentationTax;
  subtotal: string;
  tax: string;
  grand_total: string;
};

// Decimal cents and half-up rounding match the server, including 0.005 ties.
function scaled(value: string, places: number): bigint | null {
  if (!/^\d+(?:\.\d+)?$/.test(value)) return null;
  const [whole, fraction = ""] = value.split(".");
  if (fraction.slice(places).replace(/0/g, "")) return null;
  return (
    BigInt(whole) * 10n ** BigInt(places) +
    BigInt(fraction.slice(0, places).padEnd(places, "0"))
  );
}
function dollars(value: bigint) {
  return `${value / 100n}.${String(value % 100n).padStart(2, "0")}`;
}
export function taxPreview(subtotal: string, options: PresentationTax) {
  const base = scaled(subtotal, 2);
  if (base === null) return null;
  let tax = 0n;
  if (options.enabled) {
    if (options.mode === "percent") {
      const rate = scaled(options.rate, 4);
      if (rate === null || rate > 1000000n) return null;
      tax = (base * rate + 500000n) / 1000000n;
    } else {
      const value = scaled(options.amount, 2);
      if (value === null || value > 99999999999999n) return null;
      tax = value;
    }
  }
  return {
    subtotal: dollars(base),
    tax: dollars(tax),
    grand_total: dollars(base + tax),
  };
}
