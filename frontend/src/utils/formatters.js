/**
 * Decimal-safe formatting and calculation utilities for Tamil Voice POS.
 * Never hardcodes currency symbols — always consumes backend /api/config values.
 */

export function formatCurrency(amount, currencySymbol = "Rs.") {
  const num = Number(amount || 0);
  if (Number.isNaN(num)) return `${currencySymbol} 0.00`;
  return `${currencySymbol} ${num.toLocaleString("en-LK", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatQuantity(qty) {
  const num = Number(qty || 0);
  if (Number.isNaN(num)) return "0";
  if (Number.isInteger(num)) return String(num);
  return parseFloat(num.toFixed(3)).toString();
}

export function computeLineSubtotal(quantity, unitPrice) {
  // Integer cents calculation to avoid IEEE-754 floating-point drift
  const qtyMilli = Math.round(Number(quantity || 0) * 1000);
  const priceCents = Math.round(Number(unitPrice || 0) * 100);
  const subtotalCents = Math.round((qtyMilli * priceCents) / 1000);
  return subtotalCents / 100;
}

export function sumMoneyAmounts(amounts) {
  const totalCents = amounts.reduce(
    (acc, val) => acc + Math.round(Number(val || 0) * 100),
    0
  );
  return totalCents / 100;
}

export function formatDateTime(isoString) {
  if (!isoString) return "—";
  const dt = new Date(isoString);
  if (Number.isNaN(dt.getTime())) return isoString;
  return dt.toLocaleString("en-LK", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatShortDate(dateStr) {
  if (!dateStr) return "";
  const parts = dateStr.split("-");
  if (parts.length !== 3) return dateStr;
  const dt = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
  return dt.toLocaleDateString("en-LK", { month: "short", day: "numeric" });
}
